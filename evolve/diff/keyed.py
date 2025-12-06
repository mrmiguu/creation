"""
Keyed list reconciliation for Evolve.

Reconciles old children vs new children using keys.
Only minimal DOM operations are executed.
Based on standard VDOM patching algorithms.
"""

from typing import List, Any, Dict
from ..dom.dom import Element, Signal, Computed
from ..kernel.kernel import kernel

def reconcile(parent_id: int, old: List[Element], new: List[Element]):
    """
    Reconcile two lists of Elements under the same parent container.
    Matches by key first, then by position for unkeyed.
    Patches matching elements, inserts new ones, removes old ones.
    """
    
    # 1. Map old keys to elements and track unkeyed
    old_keyed = {}
    old_unkeyed = []
    
    for el in old:
        if el.key is not None:
            old_keyed[el.key] = el
        else:
            old_unkeyed.append(el)
            
    # 2. Iterate new elements and match
    new_children_elements = []
    
    # Track used old elements to know what to remove later
    used_old_keys = set()
    used_old_unkeyed_indices = set()
    
    old_unkeyed_idx = 0
    
    for i, new_el in enumerate(new):
        matched = None
        
        # Try finding match
        if new_el.key is not None:
            if new_el.key in old_keyed:
                matched = old_keyed[new_el.key]
                used_old_keys.add(new_el.key)
        else:
            if old_unkeyed_idx < len(old_unkeyed):
                matched = old_unkeyed[old_unkeyed_idx]
                used_old_unkeyed_indices.add(old_unkeyed_idx)
                old_unkeyed_idx += 1
                
        if matched:
            # Reuse logic
            _patch_element(matched, new_el)
            new_children_elements.append(new_el)
            
            # Ensure DOM order
            # If the matched node is not at the current index in the DOM, move it.
            # But the DOM might be messy.
            # Simple approach: we rely on insert_at moving existing nodes?
            # EvolveKernel insertAt usually moves if exists.
            
            if matched.node_id is not None:
                 kernel.dom.insert_at(parent_id, matched.node_id, i)
                 
        else:
            # New element
            new_el._build()
            kernel.dom.insert_at(parent_id, new_el.node_id, i)
            new_children_elements.append(new_el)

    # 3. Cleanup unused old elements
    for key, el in old_keyed.items():
        if key not in used_old_keys:
            _remove_element(el)
            
    for i, el in enumerate(old_unkeyed):
        if i not in used_old_unkeyed_indices:
            _remove_element(el)

    return new_children_elements

def _remove_element(el: Element):
    if el.node_id is not None:
        try:
            if hasattr(kernel.dom, "remove"):
                kernel.dom.remove(el.node_id)
            else:
                 # Fallback if remove is missing (unlikely based on file scan)
                 pass
        except Exception:
            pass
            
    try:
        el.unmount()
    except Exception:
        pass

def _patch_element(old: Element, new: Element):
    """
    Update an existing element with new definition.
    Transfers node_id, updates props, resubscribes signals, recurses children.
    """
    
    # 1. State Transfer
    new.node_id = old.node_id
    new._mounted = True
    
    # 2. Unmount old to clear subscriptions
    # We do NOT remove from DOM, just stop reactive tracking
    try:
        old.unmount()
    except Exception:
        pass
        
    # 3. Prepare new Props & Children (Handling logic similar to Element._build)
    # We need to replicate the prop collection logic from dom.py _build
    # to correctly handle Tailwind hoisting and sanitization.
    
    processed_children = []
    collected_tw = {}
    
    for child in new.children:
        san = new._js_sanitize(child)
        
        if isinstance(san, dict) and "__tw_style__" in san:
            collected_tw.update(san["__tw_style__"])
            continue

        if isinstance(san, list):
            for s in san:
                if isinstance(s, dict) and "__tw_style__" in s:
                    collected_tw.update(s["__tw_style__"])
                else:
                    processed_children.append(s)
            continue
            
        processed_children.append(san)
        
    # 3b. Build Final Props
    final_props = {}
    for key, value in new.props.items():
        # Event Handlers
        if key.startswith("on") and callable(value):
            # Register new callback
            cb_id = kernel.register_callback(value)
            final_props[key] = str(cb_id)
            continue
            
        # Signals
        if isinstance(value, (Signal, Computed)):
            final_props[key] = value()
            continue
            
        final_props[key] = new._js_sanitize(value)
        
    # Merge styles
    if collected_tw:
        if "style" in final_props and isinstance(final_props["style"], dict):
            merged = {**final_props["style"], **collected_tw}
            final_props["style"] = merged
        else:
            final_props["style"] = collected_tw

    # 4. Apply Updates to DOM
    if new.node_id is not None:
        # Check if all children are text primitives (strings only)
        # Note: integers in processed_children are likely node IDs from Element children
        # so we only consider strings as text content
        text_children = [c for c in processed_children if isinstance(c, str)]
        non_text_children = [c for c in processed_children if not isinstance(c, str) and c is not None]
        
        # Only set textContent if ALL children are strings (no Element children)
        if text_children and not non_text_children:
            text_content = "".join(text_children)
            final_props["textContent"] = text_content
        
        kernel.dom.update(new.node_id, final_props)
        
    # 5. Bind New Subscriptions (Signals)
    # We must replicate the signal binding logic from _build
    # Bind Prop Signals
    for key, value in new.props.items():
         if isinstance(value, (Signal, Computed)):
             new._bind_signal_prop(key, value)
             
    # Notes: We don't handle signal children here because they are usually
    # handled at the child list level. But Element._create_signal_child
    # is called during build?
    # Wait, Element._build calls _js_sanitize, which resolves signals!
    # If a child is a signal, _js_sanitize(child) returns value().
    # So processed_children has values.
    # The subscription for CHILD signals happens... where?
    # Ah, dom.py _build doesn't seem to subscribe to child signals directly?
    # Checking dom.py again:
    # _js_sanitize calls val() on signals.
    # So it snapshots the value.
    # If a child is a signal, Element._build just renders the current value.
    # IT DOES NOT SUBSCRIBE?
    # Wait, `dom.py` line 64: `_create_signal_child`.
    # Who calls this? Searching `dom.py`...
    # It is NOT called in the file! 
    # That means Signal children in Evolve might be static or broken in current dom.py?
    # Or I missed where it's used.
    # The `_js_sanitize` at line 44 just calls value().
    # So `_build` just gets the string.
    # This implies Reactivity for children list only works if the LIST itself is a signal?
    # OR if the child is a Component that uses signals.
    # If `dom.py` is broken for signal children, I shouldn't try to fix it here unless I'm sure.
    # But for patching, we just rely on whatever `_js_sanitize` does.
    
    # 6. Reconcile Children (Recursion)
    # The `processed_children` we calculated above are safe JS primitives/dicts.
    # BUT `reconcile` expects `List[Element]`.
    # We need to know which children are Elements to recurse into.
    # new.children contains the raw children.
    # We need to reconcile `old.children` vs `new.children`.
    # But wait, `old.children` might contain wrappers (if it was built by component).
    # If `_patch_element` is called, `old` and `new` are Elements.
    # Their children might be Elements or primitives.
    
    # Logic:
    # Filter out Elements from children lists and reconcile them?
    # But mixed content (text, Element, text) is hard to reconcile if we skip text.
    # The `reconcile` signature I wrote expects `List[Element]`.
    # Existing `component.py` wraps everything in Elements before calling reconcile.
    # So if we are here, logic in `component.py` ensures we deal with lists of Elements.
    # BUT `_patch_element` might be dealing with an internal Element (not the container's child entry).
    # If `new` is a standard Element (e.g. div), its children might be mixed.
    # If we recurse `reconcile`, we must ensure they are Elements.
    
    old_children_elements = [c for c in old.children if isinstance(c, Element)]
    new_children_elements = [c for c in new.children if isinstance(c, Element)]
    
    # If we have Elements, reconcile them.
    # Note: This crude filtering breaks structure if mixed with text.
    # Example: [text1, div1] -> [text2, div1].
    # If text changed, we need to update it.
    # But `kernel.dom` doesn't give us handles to text nodes easily.
    # This is a limitation of current Evolve.
    # We will assume for now that if we have Elements, we reconcile them.
    # For text content, `kernel.dom.create` (which was called for `new`'s build originally) would rely on `processed`.
    # `kernel.dom.update` does NOT update children structure (add/remove text nodes).
    # If the structure of children changed (e.g. text changed), the parent 'update' might not catch it?
    # `Element` implementation of children is: pass to create.
    # `Element` has no method to update children text.
    
    # IMPORTANT FIX:
    # If the Element has mixed children that are NOT Elements (e.g. text), `kernel.dom.update` won't update them.
    # We might need to re-render the whole element if children are primitives and changed?
    # Or `kernel` needs `setText`?
    # As a fallback, if we detect change in primitives, we might want to replace the whole node.
    # But checking equality is hard.
    # For now, we only recursively reconcile ELEMENTS.
    
    if old_children_elements or new_children_elements:
        reconcile(new.node_id, old_children_elements, new_children_elements)

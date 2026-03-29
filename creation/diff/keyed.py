"""
Keyed list reconciliation for Creation.

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
    # Also track current positions to avoid unnecessary DOM moves
    old_keyed = {}
    old_unkeyed = []
    old_positions = {}  # node_id -> current index
    
    for i, el in enumerate(old):
        if el.node_id is not None:
            old_positions[el.node_id] = i
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
            
            # Only move if position changed (optimization)
            if matched.node_id is not None:
                old_pos = old_positions.get(matched.node_id, -1)
                if old_pos != i:
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
    
    # 2. Unmount old to clear subscriptions and callbacks
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
        # Use create_reactive=True for signal children
        san = new._js_sanitize(child, create_reactive=True)
        
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
            # Register new callback and track for cleanup
            cb_id = kernel.register_callback(value)
            new._callback_ids.append(cb_id)
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
        # Note: integers in processed_children are node IDs from Element children
        text_children = [c for c in processed_children if isinstance(c, str)]
        non_text_children = [c for c in processed_children if not isinstance(c, str) and c is not None]
        
        # Only set textContent if ALL children are strings (no Element children)
        if text_children and not non_text_children:
            text_content = "".join(text_children)
            final_props["textContent"] = text_content
        
        kernel.dom.update(new.node_id, final_props)
        
    # 5. Bind New Signal Props for reactivity
    for key, value in new.props.items():
         if isinstance(value, (Signal, Computed)):
             new._bind_signal_prop(key, value)
    
    # 6. Reconcile Children (Recursion)
    # Filter Element children and reconcile them
    old_children_elements = [c for c in old.children if isinstance(c, Element)]
    new_children_elements = [c for c in new.children if isinstance(c, Element)]
    
    if old_children_elements or new_children_elements:
        reconcile(new.node_id, old_children_elements, new_children_elements)


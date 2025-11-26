# evolve/component.py
"""
Component system for Evolve.

Features:
- @component decorator for function components
- ComponentInstance lifecycle: mount, rerender, unmount
- render_component(entry_component, selector) to mount root component
- Uses the dom.Element contract (Element._build(), Element.unmount())
- Attempts kernel.dom.remove(nodeId) if available; otherwise hides node as fallback.

Notes / limitations:
- A component's render function must return an Element (from evolve.dom) or a primitive.
- Re-render strategy: re-run render(), build new Element tree, replace previous child(s).
- Cleanup: Element.unmount() is called to remove subscriptions. Real DOM removal depends on kernel.dom.remove.
"""

from typing import Any, Callable
from ..dom.dom import Element, div
from ..kernel.kernel import kernel
from ..reactive.reactive import effect
import functools
import inspect

#   utils  
def _is_element(x: Any) -> bool:
    return isinstance(x, Element)

def _ensure_element(x: Any) -> Element:
    # If user returns a primitive, wrap it in a span
    if _is_element(x):
        return x
    return div(x)  # wrap primitive in a div/span (div used for simplicity)


#   ComponentInstance  
class ComponentInstance:
    """
    Manages a single instance of a function component.
    - `fn` is the component function (fn(props, *children) -> Element)
    - `props` is a dict of props
    - `children` is list of children passed by caller
    """
    def __init__(self, fn: Callable[..., Any], props: dict[str, Any] | None = None, children: list[Any] | None = None):
        self.fn = fn
        self.props = props or {}
        self.children = children or []

        # container Element that holds component's root DOM node(s)
        # we create a lightweight container to manage replacement easily
        self.container: Element = div()  # empty wrapper
        self._mounted_child: Element | None = None
        self._render_runner = None  # effect runner for reactive re-rendering
        self._is_mounted = False

    # create an effect that re-renders when dependencies change
    def _render_effect(self):
        # call the component function to get its element tree
        out = self.fn(self.props, *self.children) if self._accepts_props() else self.fn(*self.children)
        # normalize to Element
        new_elem = _ensure_element(out)
        self._apply_rendered(new_elem)

       
        

    def _accepts_props(self) -> bool:
        # simple heuristic: function expects at least one arg => likely props
        try:
            sig = inspect.signature(self.fn)
            return len(sig.parameters) >= 1
        except Exception:
            return False

    def mount_to(self, parent_selector: str = "#app"):
        """Mount the container under a parent selector in real DOM."""
        parent_q = kernel.dom.query(parent_selector)
        if not parent_q.get("ok"):
            raise RuntimeError(f"Query failed: {parent_q.get('error')}")
        parent_id = parent_q["value"]
        if parent_id is None:
            raise RuntimeError(f"No DOM element matches {parent_selector}")
        # ensure container Element built
        # build container ONCE
        self._container_id = self.container._build()
        kernel.dom.append(parent_id, self._container_id)

        # NOW start effect
        # create effect: this collects dependencies and re-runs automatically
        # store runner so we could call or dispose if needed
        self._render_runner = effect(self._render_effect)

        self._is_mounted = True

        # initial render already run by effect during construction; effect will have called _apply_rendered

    def _apply_rendered(self, new_elem: Element):
        """
        Replace the mounted child with new_elem.
        - Unmount old Element (cleanup subscriptions).
        - Build new element and append to container.
        - Remove prior DOM child if kernel supports it; otherwise we try to hide / best-effort removal.
        """
        # If nothing mounted earlier: simply append
        if self._mounted_child is None:
            nid = new_elem._build()
            kernel.dom.append(self.container._build(), nid)
            self._mounted_child = new_elem
            return

        # There is an existing mounted child: unmount it, remove DOM node, then append new one
        old = self._mounted_child

        # capture old node id (if available) to remove
        old_node_id = old.node_id

        # Unmount (cleanup subscriptions)
        try:
            old.unmount()
        except Exception:
            # safe to ignore cleanup errors but log
            kernel.log("error", f"error during unmount of component child: {old}")

        # Try to remove old DOM node from parent
        if old_node_id is not None:
            # prefer kernel.dom.remove if implemented
            try:
                if hasattr(kernel.dom, "remove"):
                    # typed call to kernel.dom.remove
                    kernel.dom.remove(old_node_id)
                else:
                    # fallback: hide old node (not ideal but safe)
                    kernel.dom.update(old_node_id, {"style": {"display": "none"}})
            except Exception:
                # swallow; we still append new node
                kernel.log("error", f"failed to remove old child node {old_node_id}")

        # Now append new
        new_id = new_elem._build()
        kernel.dom.append(self.container._build(), new_id)
        self._mounted_child = new_elem

    def unmount(self):
        """Unmount component and its children. Dispose effect if needed."""
        # Stop re-render: (no explicit dispose for effect currently) — we rely on unmounting child subscriptions
        try:
            if self._mounted_child:
                self._mounted_child.unmount()
            # attempt to remove container DOM node itself
            if self.container.node_id is not None:
                try:
                    if hasattr(kernel.dom, "remove"):
                        kernel.dom.remove(self.container.node_id)
                    else:
                        kernel.dom.update(self.container.node_id, {"style": {"display": "none"}})
                except Exception:
                    pass
        finally:
            self._is_mounted = False


#   decorator  
def component(fn: Callable[..., Any]) -> Callable[..., ComponentInstance]:
    """
    Decorator to turn a function into a component factory.
    Usage:
        @component
        def Counter(props):
            return div("...")

        c = Counter({"initial": 0})    # returns ComponentInstance
        c.mount_to("#app")
    Or:
        c = Counter()  # no props
    """
    @functools.wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> ComponentInstance:
        # If first arg is a dict-like props, pass as props; else use kwargs
        props = {}
        children = []

        # If only kwargs provided, treat as props
        if kwargs:
            props = kwargs
        # If args given and the first arg is a dict, treat it as props
        elif args:
            first = args[0]
            if isinstance(first, dict):
                props = first
                children = list(args[1:])
            else:
                children = list(args)

        inst = ComponentInstance(fn, props, children)
        return inst

    return wrapper


#   top-level render helper  
def render_component(comp_inst: ComponentInstance, selector: str = "#app"):
    """
    Mounts a ComponentInstance into the document.
    """
    comp_inst.mount_to(selector)

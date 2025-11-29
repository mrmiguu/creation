# evolve/component.py
"""
Component system for Evolve.

Supports:
- Function components
- Reactive re-render via effect()
- Lifecycle hooks (on_mount, on_cleanup)
- Clean DOM unmounting
"""

from typing import Any, Callable
from ..dom.dom import Element, div
from ..kernel.kernel import kernel
from ..reactive.reactive import effect
from ..core.lifecycle import push_component, pop_component
from ..context.context import ProviderWrapper
from ..context.context import _CONTEXTS as _CONTEXT_STACKS
from ..diff.keyed import reconcile
import functools
import inspect


def _is_element(x: Any) -> bool:
    return isinstance(x, Element)


def _ensure_element(x: Any) -> Element:
    if _is_element(x):
        return x
    return div(x)


class ComponentInstance:
    def __init__(
        self,
        fn: Callable[..., Any],
        props: dict[str, Any] | None = None,
        children: list[Any] | None = None,
    ):
        self.fn = fn
        self.props = props or {}
        self.children = children or []

        # lifecycle
        self._mount_callbacks: list[Callable] = []
        self._cleanup_callbacks: list[Callable] = []

        # rendering
        self.container: Element = div()
        self._mounted_child: Element | None = None
        self._render_runner = None
        self._is_mounted = False
        self._container_id: int | None = None

    #
    # EFFECT: called whenever dependencies change
    #
    def _render_effect(self):
        if self._is_mounted is False and self._container_id is not None:
            # if unmounted , skip
            return
        push_component(self)

        try:
            # Support ProviderWrapper
            if isinstance(self.fn, ProviderWrapper):
                ctx = self.fn.ctx
                val = self.fn.value

                # push value
                stack = _CONTEXT_STACKS[ctx._key]
                stack.append(val)

                try:
                    out = div(*self.fn.children)
                finally:
                    stack.pop()

            else:
                try:
                    if self._accepts_props():
                        out = self.fn(self.props, *self.children)
                    else:
                        out = self.fn(*self.children)
                except Exception as e:
                    # Check if parent is an ErrorBoundaryWrapper
                    # NOTE: fn may be a ProviderWrapper or a plain function, but ErrorBoundaryWrapper has `_error_signal`
                    if hasattr(self.fn, "_error_signal"):
                        self.fn._error_signal.set(e)
                        out = self.fn.fallback(e)
                    else:
                        # no boundary above → full crash (or later we can add global handler)
                        raise


        finally:
            pop_component()

        new_elem = _ensure_element(out)
        self._apply_rendered(new_elem)

    def _accepts_props(self) -> bool:
        try:
            sig = inspect.signature(self.fn)
            # accept if function takes >=1 positional or keyword-only parameter
            return len(sig.parameters) >= 1
        except Exception:
            return False

    #
    # Mount Component to DOM
    #
    def mount_to(self, parent_selector: str = "body"):
        parent_q = kernel.dom.query(parent_selector)
        if not parent_q.get("ok"):
            raise RuntimeError(f"Query failed: {parent_q.get('error')}")

        parent_id = parent_q["value"]
        if parent_id is None:
            raise RuntimeError(f"No DOM element matches {parent_selector}")

        # Create container
        self._container_id = self.container._build()
        kernel.dom.append(parent_id, self._container_id)

        # Start effect loop
        self._render_runner = effect(self._render_effect)

        self._is_mounted = True

        #
        # RUN on_mount callbacks
        #
        for fn in self._mount_callbacks:
            try:
                fn()
            except Exception as e:
                kernel.log("error", f"on_mount error: {e}")

    #
    # Replace old DOM with new rendered DOM
    #
    def _apply_rendered(self, new_elem: Element):
        # first render
        if self._mounted_child is None:
            nid = new_elem._build()
            kernel.dom.append(self._container_id, nid)
            self._mounted_child = new_elem
            return

        # If both are Elements with children lists → attempt keyed reconciliation
        if (
            isinstance(self._mounted_child, Element)
            and isinstance(new_elem, Element)
            and isinstance(self._mounted_child.children, list)
            and isinstance(new_elem.children, list)
        ):
            # Ensure children are Element instances (wrap primitives)
            def _ensure_list_of_elements(lst):
                out: list[Element] = []
                for ch in lst:
                    if isinstance(ch, Element):
                        out.append(ch)
                    else:
                        # convert primitive or other into Element via _ensure_element
                        out.append(_ensure_element(ch))
                return out

            old_children = _ensure_list_of_elements(self._mounted_child.children)
            new_children = _ensure_list_of_elements(new_elem.children)

            # reconcile returns a list of Element instances in final DOM order
            new_order = reconcile(self._container_id, old_children, new_children)

            # attach the new ordered children to the mounted element so future diffs use correct structure
            self._mounted_child.children = new_order

            # if the element identity (tag/props) changed we should still replace the whole node.
            # To keep it simple: if tags differ, fallback to full replace
            if getattr(self._mounted_child, "tag", None) != getattr(
                new_elem, "tag", None
            ):
                # full replace fallback
                old = self._mounted_child
                old_node_id = old.node_id
                try:
                    old.unmount()
                except Exception:
                    kernel.log("error", "error during unmount of previous element")
                if old_node_id is not None:
                    try:
                        if hasattr(kernel.dom, "remove"):
                            kernel.dom.remove(old_node_id)
                        else:
                            kernel.dom.update(
                                old_node_id, {"style": {"display": "none"}}
                            )
                    except Exception:
                        pass
                new_id = new_elem._build()
                kernel.dom.append(self._container_id, new_id)
                self._mounted_child = new_elem
            else:
                # Keep mounted element but update its props if any changed.
                # For simplicity we can update attributes by calling dom.update with new_elem.props
                try:
                    if getattr(new_elem, "props", None):
                        kernel.dom.update(self._mounted_child.node_id, new_elem.props)
                except Exception:
                    pass

            return

        #  FULL REPLACE PATH
        old = self._mounted_child
        old_node_id = old.node_id

        # CLEANUP the old child
        try:
            old.unmount()
        except Exception:
            kernel.log("error", "error during unmount of previous element")

        # DOM removal
        if old_node_id is not None:
            try:
                if hasattr(kernel.dom, "remove"):
                    kernel.dom.remove(old_node_id)
                else:
                    kernel.dom.update(old_node_id, {"style": {"display": "none"}})
            except Exception:
                pass

        # mount new dom node
        new_id = new_elem._build()
        kernel.dom.append(self._container_id, new_id)
        self._mounted_child = new_elem

    #
    # Unmount Component
    #
    def unmount(self):
        # run cleanup lifecycle
        for fn in self._cleanup_callbacks:
            try:
                fn()
            except Exception as e:
                kernel.log("error", f"on_cleanup error: {e}")

        self._cleanup_callbacks.clear()
        self._mount_callbacks.clear()

        # remove child
        if self._mounted_child:
            self._mounted_child.unmount()

        # remove container
        if self._container_id is not None:
            try:
                if hasattr(kernel.dom, "remove"):
                    kernel.dom.remove(self._container_id)
                else:
                    kernel.dom.update(
                        self._container_id, {"style": {"display": "none"}}
                    )
            except Exception:
                pass

        self._is_mounted = False


#
# @component decorator
#
def component(fn: Callable[..., Any]) -> Callable[..., ComponentInstance]:
    @functools.wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> ComponentInstance:
        props = {}
        children = []

        if kwargs:
            props = kwargs
        elif args:
            first = args[0]
            if isinstance(first, dict):
                props = first
                children = list(args[1:])
            else:
                children = list(args)

        return ComponentInstance(fn, props, children)

    return wrapper


#
# Manual mount helper (router uses this indirectly)
#
def render_component(comp_inst: ComponentInstance, selector: str = "body"):
    comp_inst.mount_to(selector)
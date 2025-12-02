# evolve/components/component.py
"""
Component system for Evolve.

Supports:
- Function components
- Reactive re-render via effect()
- Lifecycle hooks (on_mount, on_cleanup)
- Clean DOM unmounting

Important:
- render() is implemented as a *pure snapshot* (non-reactive). It temporarily
  disables reactive dependency tracking so it can be safely called during DOM
  construction (by dom._make_element) without creating subscriptions or causing
  render cycles.
"""
from typing import Any, Callable
from ..dom.dom import Element, div
from ..kernel.kernel import kernel
from ..reactive.reactive import effect, Signal, Computed, _current_effect_stack
from ..core.lifecycle import push_component, pop_component
from ..context.context import ProviderWrapper
from ..context.context import _CONTEXTS as _CONTEXT_STACKS
from ..diff.keyed import reconcile
import functools
import inspect


def _is_element(x: Any) -> bool:
    return isinstance(x, Element)


def _ensure_element(x: Any) -> Element:
    """
    Ensure the value is an Element. If it's a list/tuple of children,
    wrap them in a div so the rest of the pipeline always gets a single Element.
    """
    if isinstance(x, Element):
        return x
    if isinstance(x, (list, tuple)):
        return div(*x)
    # primitives / other -> wrap as text inside a div
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

        # guard against re-entrant rendering
        self._is_rendering: bool = False

    # ============================================================
    # Public render() — PURE SNAPSHOT (non-reactive)
    # ============================================================
    def render(self) -> Any:
        """
        Public render method intended to be a pure snapshot suitable for
        calling during DOM building.

        NOTE: This deliberately disables reactive dependency tracking so that
        reads of Signal()/Computed() inside a component used as a child
        do NOT register subscriptions to the caller and do NOT cause
        render cycles while DOM tree is being constructed.
        """
        # Save and clear the current reactive effect stack so no dependencies are tracked.
        saved_stack = list(_current_effect_stack)
        try:
            _current_effect_stack.clear()  # disable tracking temporarily
            return self._render_effect_for_child()
        finally:
            # restore previous stack exactly as it was
            _current_effect_stack.clear()
            _current_effect_stack.extend(saved_stack)

    # ============================================================
    # Normalize Component output to Element/primitives/lists
    # ============================================================
    def _normalize(self, value):
        """
        Recursively convert user component output into valid renderable structure:
        - Element -> keep
        - ComponentInstance -> call its render() and normalize again
        - list/tuple -> normalize each child
        - primitives -> keep
        """
        from ..dom.dom import Element as DomElement

        # Element (good)
        if isinstance(value, DomElement):
            return value

        # ComponentInstance -> unwrap by calling public render()
        if isinstance(value, ComponentInstance):
            child_out = value.render()
            return self._normalize(child_out)

        # list/tuple -> normalize each item and flatten nested lists
        if isinstance(value, (list, tuple)):
            normalized = []
            for item in value:
                out = self._normalize(item)
                if isinstance(out, (list, tuple)):
                    normalized.extend(out)
                else:
                    normalized.append(out)
            return normalized

        # primitives allowed
        if value is None or isinstance(value, (str, int, float, bool)):
            return value

        # fallback -> stringify
        return str(value)

    # ============================================================
    # Render child component ONCE without touching DOM
    # (used by render() which temporarily disables tracking)
    # ============================================================
    def _render_effect_for_child(self):
        """Render helper used by normalization or by parent when unwrapping children."""
        if isinstance(self.fn, ProviderWrapper):
            ctx = self.fn.ctx
            val = self.fn.value
            stack = _CONTEXT_STACKS[ctx._key]
            stack.append(val)
            try:
                return div(*self.fn.children)
            finally:
                stack.pop()

        if self._accepts_props():
            return self.fn(self.props, *self.children)
        else:
            return self.fn(*self.children)

    #
    # EFFECT: called whenever dependencies change (mount-time runner)
    #
    def _render_effect(self):
        # Prevent re-entrant renders overlapping
        if getattr(self, "_is_rendering", False):
            return
        self._is_rendering = True

        try:
            # If not mounted yet (or unmounted) skip
            if self._is_mounted is False and self._container_id is not None:
                return

            push_component(self)

            try:
                # Provider wrapper
                if isinstance(self.fn, ProviderWrapper):
                    ctx = self.fn.ctx
                    val = self.fn.value
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
                        if hasattr(self.fn, "_error_signal"):
                            self.fn._error_signal.set(e)
                            out = self.fn.fallback(e)
                        else:
                            raise

                # Debug log
                try:
                    from js import window as _win
                    _win.__last_vdom__ = getattr(out, "__dict__", None) or str(out)
                    kernel.log("log", f"Component output: {type(out).__name__}")
                except Exception:
                    pass

                # callable → invalid
                if callable(out) and not isinstance(out, (Element, ProviderWrapper)):
                    kernel.log("error", "Component returned callable; ignoring.")
                    out = div()

                normalized = self._normalize(out)
                new_elem = _ensure_element(normalized)

                self._apply_rendered(new_elem)

            finally:
                pop_component()

        finally:
            self._is_rendering = False

    def _accepts_props(self) -> bool:
        try:
            sig = inspect.signature(self.fn)
            return len(sig.parameters) >= 1
        except Exception:
            return False

    #
    # Mount Component to DOM
    #
    def mount_to(self, parent_selector: str = "body"):
        sel = parent_selector
        if not sel.startswith("#") and not sel.startswith(".") and sel != "body":
            sel = "#" + sel

        parent_q = kernel.dom.query(sel)
        if not parent_q.get("ok"):
            raise RuntimeError(f"Query failed: {parent_q.get('error')}")

        parent_id = parent_q.get("value")
        if parent_id is None:
            raise RuntimeError(f"No DOM element matches {sel!r}")

        self._container_id = self.container._build()
        kernel.dom.append(parent_id, self._container_id)

        try:
            kernel.log("log", f"Mounted component container {self._container_id}")
        except Exception:
            pass

        self._render_runner = effect(self._render_effect)
        self._is_mounted = True

        for fn in self._mount_callbacks:
            try:
                fn()
            except Exception as e:
                kernel.log("error", f"on_mount error: {e}")

    #
    # Replace old DOM with new rendered DOM
    #
    def _apply_rendered(self, new_elem: Element):
        if self._mounted_child is None:
            nid = new_elem._build()
            kernel.dom.append(self._container_id, nid)
            self._mounted_child = new_elem
            return

        # keyed diff path
        if (
            isinstance(self._mounted_child, Element)
            and isinstance(new_elem, Element)
            and isinstance(self._mounted_child.children, list)
            and isinstance(new_elem.children, list)
        ):
            def _ensure_list(lst):
                out = []
                for ch in lst:
                    if isinstance(ch, Element):
                        out.append(ch)
                    else:
                        out.append(_ensure_element(ch))
                return out

            old_list = _ensure_list(self._mounted_child.children)
            new_list = _ensure_list(new_elem.children)

            new_order = reconcile(self._container_id, old_list, new_list)
            self._mounted_child.children = new_order

            if getattr(self._mounted_child, "tag", None) != getattr(
                new_elem, "tag", None
            ):
                old = self._mounted_child
                old_id = old.node_id
                try:
                    old.unmount()
                except Exception:
                    kernel.log("error", "error during unmount()")

                if old_id is not None:
                    try:
                        kernel.dom.remove(old_id)
                    except Exception:
                        pass

                new_id = new_elem._build()
                kernel.dom.append(self._container_id, new_id)
                self._mounted_child = new_elem
            else:
                try:
                    if getattr(new_elem, "props", None):
                        kernel.dom.update(self._mounted_child.node_id, new_elem.props)
                except Exception:
                    pass

            return

        # full replace
        old = self._mounted_child
        old_id = old.node_id

        try:
            old.unmount()
        except Exception:
            kernel.log("error", "error during unmount prev")

        if old_id is not None:
            try:
                kernel.dom.remove(old_id)
            except Exception:
                pass

        new_id = new_elem._build()
        kernel.dom.append(self._container_id, new_id)
        self._mounted_child = new_elem

    #
    # Unmount Component
    #
    def unmount(self):
        for fn in self._cleanup_callbacks:
            try:
                fn()
            except Exception as e:
                kernel.log("error", f"cleanup error: {e}")

        self._cleanup_callbacks.clear()
        self._mount_callbacks.clear()

        if self._mounted_child:
            self._mounted_child.unmount()

        if self._container_id is not None:
            try:
                kernel.dom.remove(self._container_id)
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
# Manual mount helper
#
def render_component(comp_inst: ComponentInstance, selector: str = "body"):
    comp_inst.mount_to(selector)

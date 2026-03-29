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

        self._mount_callbacks: list[Callable] = []
        self._cleanup_callbacks: list[Callable] = []

        self.container: Element = div()
        self._mounted_child: Element | None = None
        self._render_runner = None
        self._is_mounted = False
        self._container_id: int | None = None

        self._is_rendering: bool = False
        
        # Pre-initialize hook storage to avoid hasattr() checks during renders
        self._hook_signals: list = []
        self._hook_computeds: list = []
        self._hook_effects: list = []
        self._hook_memos: list = []
        self._hook_refs: list = []
        
        # Hook indices (reset each render cycle)
        self._hook_index = 0
        self._hook_computed_index = 0
        self._hook_effect_index = 0
        self._hook_memo_index = 0
        self._hook_ref_index = 0

    def render(self) -> Any:
        """
        Public render method intended to be a pure snapshot suitable for
        calling during DOM building.

        NOTE: This deliberately disables reactive dependency tracking so that
        reads of Signal()/Computed() inside a component used as a child
        do NOT register subscriptions to the caller and do NOT cause
        render cycles while DOM tree is being constructed.
        """
        saved_stack = list(_current_effect_stack)
        try:
            _current_effect_stack.clear()  # disable tracking temporarily
            return self._render_effect_for_child()
        finally:
            _current_effect_stack.clear()
            _current_effect_stack.extend(saved_stack)

    def _normalize(self, value):
        """
        Recursively convert user component output into valid renderable structure:
        - Element -> keep
        - ComponentInstance -> call its render() and normalize again
        - list/tuple -> normalize each child
        - primitives -> keep
        """
        from ..dom.dom import Element as DomElement

        if isinstance(value, DomElement):
            return value

        if isinstance(value, ComponentInstance):
            child_out = value.render()
            return self._normalize(child_out)

        if isinstance(value, (list, tuple)):
            normalized = []
            for item in value:
                out = self._normalize(item)
                if isinstance(out, (list, tuple)):
                    normalized.extend(out)
                else:
                    normalized.append(out)
            return normalized

        if value is None or isinstance(value, (str, int, float, bool)):
            return value

        return str(value)

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
            return self.fn(*self.children, **self.props)

    def _render_effect(self):
        if getattr(self, "_is_rendering", False):
            return
        self._is_rendering = True

        try:
            # Skip rendering if component was unmounted after initial mount
            # Note: On first render, _is_mounted is False but _container_id is set
            # We should only skip if we were mounted before and then unmounted
            if self._is_mounted is False and self._container_id is None:
                return

            push_component(self)
            
            # Reset ALL hook indices for this render cycle
            self._hook_index = 0
            self._hook_computed_index = 0
            self._hook_effect_index = 0
            self._hook_memo_index = 0
            self._hook_ref_index = 0

            try:
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
                            # Props-style: fn(props_dict, *children)
                            out = self.fn(self.props, *self.children)
                        else:
                            # Python-style: fn(*children, **props)
                            out = self.fn(*self.children, **self.props)
                    except Exception as e:
                        if hasattr(self.fn, "_error_signal"):
                            self.fn._error_signal(e)
                            out = self.fn.fallback(e)
                        else:
                            raise

                try:
                    from js import window as _win
                    _win.__last_vdom__ = getattr(out, "__dict__", None) or str(out)
                    kernel.log("log", f"Component output: {type(out).__name__}")
                except Exception:
                    pass

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
        """
        Check if component function expects a 'props' dict as first argument.
        Uses cached value from @component decorator when available.
        """
        # Use cached value if available (set by @component decorator)
        if hasattr(self, "_cached_accepts_props"):
            return self._cached_accepts_props
        
        # Fallback for non-decorated components (expensive, but rare)
        try:
            sig = inspect.signature(self.fn)
            params = list(sig.parameters.values())
            if not params:
                return False
            return params[0].name == "props"
        except Exception:
            return False

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

    def _apply_rendered(self, new_elem: Element):
        if self._mounted_child is None:
            nid = new_elem._build()
            kernel.dom.append(self._container_id, nid)
            self._mounted_child = new_elem
            return

        if (
            isinstance(self._mounted_child, Element)
            and isinstance(new_elem, Element)
            and isinstance(self._mounted_child.children, list)
            and isinstance(new_elem.children, list)
        ):
            from evolve.diff.keyed import _patch_element
            
            def _ensure_list(lst):
                out = []
                for ch in lst:
                    if isinstance(ch, Element):
                        out.append(ch)
                    else:
                        out.append(_ensure_element(ch))
                return out

            # If same tag, patch the root element and reconcile children
            if getattr(self._mounted_child, "tag", None) == getattr(new_elem, "tag", None):
                # Patch root element (updates props, styles, etc.)
                _patch_element(self._mounted_child, new_elem)
                
                # Reconcile children using mounted_child's node_id as parent
                old_list = _ensure_list(self._mounted_child.children)
                new_list = _ensure_list(new_elem.children)
                
                # Use the MOUNTED element's node_id, not the container
                parent_id = new_elem.node_id  # _patch_element transferred node_id to new_elem
                new_order = reconcile(parent_id, old_list, new_list)
                new_elem.children = new_order
                
                self._mounted_child = new_elem
            else:
                # Tag changed - full replace
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

            return

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


def component(fn: Callable[..., Any]) -> Callable[..., ComponentInstance]:
    # Cache signature check at decoration time (ONCE per component definition)
    try:
        sig = inspect.signature(fn)
        params = list(sig.parameters.values())
        accepts_props = bool(params and params[0].name == "props")
    except Exception:
        accepts_props = False
    
    @functools.wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> ComponentInstance:
        # For Python-style components: positional args are children, kwargs are props
        # This allows: FeatureCard("title", "subtitle", cta_text="Click")
        # where args become children passed to fn, and kwargs become props
        props = kwargs if kwargs else {}
        children = list(args)
        
        inst = ComponentInstance(fn, props, children)
        inst._cached_accepts_props = accepts_props  # Use cached value
        return inst

    return wrapper


def render_component(comp_inst: ComponentInstance, selector: str = "body"):
    comp_inst.mount_to(selector)

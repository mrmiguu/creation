"""
DOM builder layer for Evolve.
Fully reactive: supports Signal & Computed values in
- children
- props (like textContent, value, etc.)
Handles subscription storage + unmounting.
"""

from typing import Any
from ..kernel.kernel import kernel
from ..reactive.reactive import Signal, Computed


class Element:
    """
    Represents a virtual DOM element. The user never sees node_ids,
    subscriptions, or kernel internals.
    """

    def __init__(self, tag: str, props: dict[str, Any], children: list[Any]):
        self.tag = tag
        self.props = props
        self.children = children

        self.node_id: int | None = None
        self._subscriptions: list[
            tuple[Signal | Computed, int]
        ] = []  # (signal, sub_id)
        self._callback_ids: list[int] = []  # Track registered callback IDs for cleanup
        self._mounted: bool = False
        self.key = props.pop("key", None)

    def _js_sanitize(self, value, create_reactive=False):
        """
        Convert Python-side values to safe JS primitives.
        Prevents PyProxy leaks & prevents Callables as children.
        
        Args:
            create_reactive: If True, Signal/Computed children become reactive spans
        """
        from ..components.component import ComponentInstance
        
        # Handle ComponentInstance - render and sanitize the result
        if isinstance(value, ComponentInstance):
            rendered = value.render()
            return self._js_sanitize(rendered, create_reactive)

        if callable(value) and not isinstance(value, (Signal, Computed, Element)):
            try:
                value = value()
            except Exception:
                pass

        if isinstance(value, (Signal, Computed)):
            if create_reactive:
                # Create a reactive text span that updates when signal changes
                return self._create_signal_child(value)
            return value()

        if isinstance(value, Element):
            return value._build()

        if isinstance(value, dict) and "__tw_style__" in value:
            return value

        if isinstance(value, dict):
            out = {}
            for k, v in value.items():
                out[k] = self._js_sanitize(v, create_reactive)
            return out

        if isinstance(value, (list, tuple)):
            return [self._js_sanitize(v, create_reactive) for v in value]

        return value

    def _create_signal_child(self, sig: Signal | Computed) -> int:
        initial = sig()
        res = kernel.dom.create("span", {"textContent": str(initial)})
        if not res.get("ok"):
            raise RuntimeError(f"Signal child creation failed: {res.get('error')}")

        text_id = int(res["value"])

        def _update(val):
            kernel.dom.update(text_id, {"textContent": str(val)})

        sub_id = sig.subscribe(_update)
        self._subscriptions.append((sig, sub_id))
        return text_id

    def _bind_signal_prop(self, key: str, sig: Signal | Computed):
        initial = sig()
        kernel.dom.update(self.node_id, {key: str(initial)})

        def _update(val):
            kernel.dom.update(self.node_id, {key: str(val)})

        sub_id = sig.subscribe(_update)
        self._subscriptions.append((sig, sub_id))

    def _build(self) -> int:
        if self.node_id is not None:
            return self.node_id

        processed = []
        collected_tw = {}

        for child in self.children:
            # Use create_reactive=True to make Signal children reactive
            san = self._js_sanitize(child, create_reactive=True)

            if isinstance(san, dict) and "__tw_style__" in san:
                collected_tw.update(san["__tw_style__"])
                continue

            if isinstance(san, list):
                for s in san:
                    if isinstance(s, dict) and "__tw_style__" in s:
                        collected_tw.update(s["__tw_style__"])
                    else:
                        processed.append(s)
                continue

            processed.append(san)

        final_props = {}
        for key, value in self.props.items():

            if key.startswith("on") and callable(value):
                cb_id = kernel.register_callback(value)
                self._callback_ids.append(cb_id)  # Track for cleanup
                final_props[key] = str(cb_id)
                continue

            if isinstance(value, (Signal, Computed)):
                final_props[key] = value()
                continue

            final_props[key] = self._js_sanitize(value)

        if collected_tw:
            if "style" in final_props and isinstance(final_props["style"], dict):
                merged = {**final_props["style"], **collected_tw}
                final_props["style"] = merged
            else:
                final_props["style"] = collected_tw

        res = kernel.dom.create(self.tag, final_props, processed)
        if not res.get("ok"):
            err = res.get("error")
            kernel.log("error", f"DOM create failed for {self.tag}: {err}")
            raise RuntimeError(f"DOM create failed: {err}")

        self.node_id = int(res["value"])

        for key, value in self.props.items():
            if isinstance(value, (Signal, Computed)):
                self._bind_signal_prop(key, value)

        self._mounted = True
        return self.node_id

    def unmount(self):
        if not self._mounted:
            return
        # Clean up signal subscriptions
        for sig, sid in self._subscriptions:
            sig.unsubscribe(sid)
        self._subscriptions.clear()
        
        # Clean up registered callbacks to prevent memory leaks
        for cb_id in self._callback_ids:
            kernel.unregister_callback(cb_id)
        self._callback_ids.clear()
        
        self._mounted = False


def _make_element(tag: str, *children: Any, **props: Any) -> Element:
    from ..components.component import ComponentInstance

    fixed = []
    for c in children:
        if isinstance(c, ComponentInstance):
            out = c.render()
            if isinstance(out, list):
                fixed.extend(out)
            else:
                fixed.append(out)
        else:
            fixed.append(c)

    return Element(tag, props, list(fixed))


def div(*children, **props): return _make_element("div", *children, **props)
def span(*children, **props): return _make_element("span", *children, **props)
def button(*children, **props): return _make_element("button", *children, **props)
def p(*children, **props): return _make_element("p", *children, **props)
def h1(*children, **props): return _make_element("h1", *children, **props)
def h2(*children, **props): return _make_element("h2", *children, **props)
def h3(*children, **props): return _make_element("h3", *children, **props)
def input(*children, **props): return _make_element("input", *children, **props)
def img(*children, **props): return _make_element("img", *children, **props)


def mount(element: Element, selector: str = "#app"):
    parent = kernel.dom.query(selector)
    if not parent.get("ok"):
        raise RuntimeError(parent.get("error"))

    pid = parent["value"]
    if pid is None:
        raise RuntimeError(f"No DOM element matches {selector}")

    node_id = element._build()
    kernel.dom.append(pid, node_id)

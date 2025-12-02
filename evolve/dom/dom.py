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
        self._mounted: bool = False
        self.key = props.pop("key", None)

    # ---------------------------------------------------------
    # SANITIZATION (safe values for JS)
    # ---------------------------------------------------------
    def _js_sanitize(self, value):
        """
        Convert Python-side values to safe JS primitives.
        Prevents PyProxy leaks & prevents Callables as children.
        """

        # 1) If value is a callable (e.g. lambda: cnt()), call once
        #    → This fixes the CounterWidget <function ...> bug.
        if callable(value) and not isinstance(value, (Signal, Computed, Element)):
            try:
                value = value()
            except Exception:
                pass

        # 2) Signals → unwrap
        if isinstance(value, (Signal, Computed)):
            return value()

        # 3) Element → return built DOM node
        if isinstance(value, Element):
            return value._build()

        # 4) TW style marker → leave it intact
        if isinstance(value, dict) and "__tw_style__" in value:
            return value

        # 5) Dict → sanitize recursively
        if isinstance(value, dict):
            out = {}
            for k, v in value.items():
                out[k] = self._js_sanitize(v)
            return out

        # 6) List / tuple
        if isinstance(value, (list, tuple)):
            return [self._js_sanitize(v) for v in value]

        # 7) Primitives
        return value

    # ---------------------------------------------------------
    # SIGNAL CHILD
    # ---------------------------------------------------------
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

    # ---------------------------------------------------------
    # SIGNAL PROP
    # ---------------------------------------------------------
    def _bind_signal_prop(self, key: str, sig: Signal | Computed):
        initial = sig()
        kernel.dom.update(self.node_id, {key: str(initial)})

        def _update(val):
            kernel.dom.update(self.node_id, {key: str(val)})

        sub_id = sig.subscribe(_update)
        self._subscriptions.append((sig, sub_id))

    # ---------------------------------------------------------
    # BUILD
    # ---------------------------------------------------------
    def _build(self) -> int:
        if self.node_id is not None:
            return self.node_id

        # --- 1) Process children ---
        processed = []
        collected_tw = {}

        for child in self.children:
            san = self._js_sanitize(child)

            # tw-style marker
            if isinstance(san, dict) and "__tw_style__" in san:
                collected_tw.update(san["__tw_style__"])
                continue

            # flatten lists
            if isinstance(san, list):
                for s in san:
                    if isinstance(s, dict) and "__tw_style__" in s:
                        collected_tw.update(s["__tw_style__"])
                    else:
                        processed.append(s)
                continue

            processed.append(san)

        # --- 2) Process props ---
        final_props = {}
        for key, value in self.props.items():

            # events
            if key.startswith("on") and callable(value):
                cb_id = kernel.register_callback(value)
                final_props[key] = str(cb_id)
                continue

            # reactive props
            if isinstance(value, (Signal, Computed)):
                final_props[key] = value()
                continue

            final_props[key] = self._js_sanitize(value)

        # merge tw(...) style
        if collected_tw:
            if "style" in final_props and isinstance(final_props["style"], dict):
                merged = {**final_props["style"], **collected_tw}
                final_props["style"] = merged
            else:
                final_props["style"] = collected_tw

        # --- 3) CREATE DOM NODE ---
        res = kernel.dom.create(self.tag, final_props, processed)
        if not res.get("ok"):
            raise RuntimeError(f"DOM create failed: {res.get('error')}")

        self.node_id = int(res["value"])

        # --- 4) Bind reactive props now ---
        for key, value in self.props.items():
            if isinstance(value, (Signal, Computed)):
                self._bind_signal_prop(key, value)

        self._mounted = True
        return self.node_id

    # ---------------------------------------------------------
    # UNMOUNT
    # ---------------------------------------------------------
    def unmount(self):
        if not self._mounted:
            return
        for sig, sid in self._subscriptions:
            sig.unsubscribe(sid)
        self._subscriptions.clear()
        self._mounted = False


# ---------------------------------------------------------
# ELEMENT FACTORY
# ---------------------------------------------------------
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


# ---------------------------------------------------------
# HTML TAG HELPERS
# ---------------------------------------------------------
def div(*children, **props): return _make_element("div", *children, **props)
def span(*children, **props): return _make_element("span", *children, **props)
def button(*children, **props): return _make_element("button", *children, **props)
def p(*children, **props): return _make_element("p", *children, **props)
def h1(*children, **props): return _make_element("h1", *children, **props)
def h2(*children, **props): return _make_element("h2", *children, **props)
def h3(*children, **props): return _make_element("h3", *children, **props)
def input(*children, **props): return _make_element("input", *children, **props)
def img(*children, **props): return _make_element("img", *children, **props)


# ---------------------------------------------------------
# MOUNT
# ---------------------------------------------------------
def mount(element: Element, selector: str = "#app"):
    parent = kernel.dom.query(selector)
    if not parent.get("ok"):
        raise RuntimeError(parent.get("error"))

    pid = parent["value"]
    if pid is None:
        raise RuntimeError(f"No DOM element matches {selector}")

    node_id = element._build()
    kernel.dom.append(pid, node_id)

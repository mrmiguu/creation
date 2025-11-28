"""
DOM builder layer for Evolve.
Fully reactive: supports Signal & Computed values in
- children
- props (like textContent, value, etc.)
Handles subscription storage + unmounting.

"""

from typing import Any
from collections.abc import Callable
from .kernel import kernel
from .reactive import Signal, Computed


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


    #
    # Internal helper: create child node for Signal/Computed
    #
    def _create_signal_child(self, sig: Signal | Computed) -> int:
        # Initial value
        initial = sig()
        res = kernel.dom.create("span", {"textContent": str(initial)})

        if not res.get("ok"):
            raise RuntimeError(f"Signal child creation failed: {res.get('error')}")

        text_id = int(res["value"])

        # Subscribe to updates
        def _update(val):
            kernel.dom.update(text_id, {"textContent": str(val)})

        sub_id = sig.subscribe(_update)
        self._subscriptions.append((sig, sub_id))

        return text_id

    #
    # Internal helper: handle Signal/Computed props
    #
    def _bind_signal_prop(self, key: str, sig: Signal | Computed):
        # Apply initial value
        initial = sig()
        # Normal props: textContent, id, class, value, etc.
        kernel.dom.update(self.node_id, {key: str(initial)})

        # Subscribe to updates
        def _update(val):
            kernel.dom.update(self.node_id, {key: str(val)})

        sub_id = sig.subscribe(_update)
        self._subscriptions.append((sig, sub_id))

    #
    # Build node in DOM
    #
    def _build(self) -> int:
        if self.node_id is not None:
            return self.node_id

        processed_children: list[Any] = []

        # Handle children (primitive / Element / Signal)
        for child in self.children:
            # Nested Element
            if isinstance(child, Element):
                processed_children.append(child._build())
                continue

            # Signal as child
            if isinstance(child, (Signal, Computed)):
                node_id = self._create_signal_child(child)
                processed_children.append(node_id)
                continue

            # Primitive (text)
            processed_children.append(child)

        # Handle props (callbacks, signals, normal props)
        final_props: dict[str, Any] = {}

        for key, value in self.props.items():
            # Event handler: onClick, oninput, etc.
            if key.startswith("on") and callable(value):
                cb_id = kernel.register_callback(value)
                final_props[key] = str(cb_id)
                continue

            # Signal prop
            if isinstance(value, (Signal, Computed)):
                # We'll bind after node is created
                final_props[key] = str(value())
                continue

            # Normal prop
            final_props[key] = value

        # Create node now
        res = kernel.dom.create(self.tag, final_props, processed_children)

        if not res.get("ok"):
            raise RuntimeError(f"DOM create failed: {res.get('error')}")

        self.node_id = int(res["value"])

        # Now bind signal props (requires node_id)
        for key, value in self.props.items():
            if isinstance(value, (Signal, Computed)):
                self._bind_signal_prop(key, value)

        self._mounted = True
        return self.node_id

    #
    # UNMOUNT: remove subscriptions cleanly
    #
    def unmount(self):
        """Detach subscriptions. DOM removal is handled externally."""
        if not self._mounted:
            return

        for sig, sid in self._subscriptions:
            sig.unsubscribe(sid)

        self._subscriptions.clear()
        self._mounted = False


#
# Element factory
#


def _make_element(tag: str, *children: Any, **props: Any) -> Element:
    return Element(tag, props, list(children))


# Common HTML elements
def div(*children, **props):
    return _make_element("div", *children, **props)


def span(*children, **props):
    return _make_element("span", *children, **props)


def button(*children, **props):
    return _make_element("button", *children, **props)


def p(*children, **props):
    return _make_element("p", *children, **props)


def h1(*children, **props):
    return _make_element("h1", *children, **props)


def h2(*children, **props):
    return _make_element("h2", *children, **props)


def h3(*children, **props):
    return _make_element("h3", *children, **props)


def input(*children, **props):
    return _make_element("input", *children, **props)


def img(*children, **props):
    return _make_element("img", *children, **props)


#
# MOUNT
#


def mount(element: Element, selector: str = "#app"):
    """Mount an Element in the real DOM under a selector."""
    parent = kernel.dom.query(selector)
    if not parent.get("ok"):
        raise RuntimeError(f"Query failed: {parent.get('error')}")

    parent_id = parent["value"]

    if parent_id is None:
        raise RuntimeError(f"No DOM element matches {selector}")

    node_id = element._build()
    kernel.dom.append(parent_id, node_id)

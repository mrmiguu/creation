"""
High-level HTML API for Evolve.

Adds:
- tw("...") utility for Tailwind-like inline CSS
- Clean element factories
- Prop normalization (class_, for_, data_*, aria_*)
"""

from typing import Any
from ..dom.dom import _make_element


#
# Tailwind-like translator
#

_TW_MAP = {
    "flex": {"display": "flex"},
    "inline-flex": {"display": "inline-flex"},
    "grid": {"display": "grid"},
    "items-center": {"align-items": "center"},
    "items-start": {"align-items": "flex-start"},
    "items-end": {"align-items": "flex-end"},
    "justify-center": {"justify-content": "center"},
    "justify-between": {"justify-content": "space-between"},
    "justify-around": {"justify-content": "space-around"},
    # Gap utilities (example)
    "gap-1": {"gap": "0.25rem"},
    "gap-2": {"gap": "0.5rem"},
    "gap-3": {"gap": "0.75rem"},
    "gap-4": {"gap": "1rem"},
    "gap-6": {"gap": "1.5rem"},
    # Padding (example scale)
    "p-1": {"padding": "0.25rem"},
    "p-2": {"padding": "0.5rem"},
    "p-3": {"padding": "0.75rem"},
    "p-4": {"padding": "1rem"},
    "pt-2": {"padding-top": "0.5rem"},
    "pb-2": {"padding-bottom": "0.5rem"},
    "pl-2": {"padding-left": "0.5rem"},
    "pr-2": {"padding-right": "0.5rem"},
    # Margin (optional for now)
    "m-2": {"margin": "0.5rem"},
    "mx-2": {"margin-left": "0.5rem", "margin-right": "0.5rem"},
    "my-2": {"margin-top": "0.5rem", "margin-bottom": "0.5rem"},
    # Colors (just a few examples)
    "text-white": {"color": "white"},
    "bg-red-500": {"background-color": "#ef4444"},
    "bg-blue-500": {"background-color": "#3b82f6"},
    "bg-gray-800": {"background-color": "#1f2937"},
    # Border radius
    "rounded": {"border-radius": "0.25rem"},
    "rounded-lg": {"border-radius": "0.5rem"},
}




def _tw_to_style(classes: str) -> dict[str, str]:
    """Convert Tailwind-like classes to inline style dict."""
    style: dict[str, str] = {}

    for cls in classes.split():
        if cls in _TW_MAP:
            style.update(_TW_MAP[cls])
        else:
            # ignore unsupported utilities silently
            pass

    return style


def tw(classes: str) -> dict[str, Any]:
    """Return a special marker dict for tw styles."""
    if ":" in classes:
        # future support for variants
        pass
    return {"__tw_style__": _tw_to_style(classes)}


#
# Prop normalization utilities
#


def _kebab_from_underscore(s: str) -> str:
    return s.replace("_", "-")


def _normalize_prop_key(k: str) -> str:
    if k == "class_":
        return "class"
    if k == "for_":
        return "for"

    if k.startswith("data_"):
        return "data-" + _kebab_from_underscore(k[5:])
    if k.startswith("aria_"):
        return "aria-" + _kebab_from_underscore(k[5:])

    if k.startswith("on_"):
        return "on" + k[3:].replace("_", "")

    return k


def _normalize_props(props: dict[str, Any]) -> dict[str, Any]:
    final: dict[str, Any] = {}

    for k, v in props.items():
        nk = _normalize_prop_key(k)
        final[nk] = v

    return final


#
# Children flattening
#


def _flatten_children(children):
    out = []
    for c in children:
        if c is None:
            continue
        if isinstance(c, (list, tuple)):
            out.extend(_flatten_children(c))
        else:
            out.append(c)
    return out


#
# Factory builder
#


def _make_factory(tag: str):
    def factory(*children: Any, **props: Any):
        flat = _flatten_children(children)
        norm_props = _normalize_props(props)

        # Extract key (NOT a DOM prop)
        key = norm_props.pop("key", None)

        # merge tw() styles if present
        tw_style: dict[str, str] = {}
        new_children: list[Any] = []

        for c in flat:
            if isinstance(c, dict) and "__tw_style__" in c:
                tw_style.update(c["__tw_style__"])
            else:
                new_children.append(c)

        if tw_style:
            if "style" in norm_props and isinstance(norm_props["style"], dict):
                merged = {**norm_props["style"], **tw_style}
                norm_props["style"] = merged
            else:
                norm_props["style"] = tw_style

        # Create Element
        elem = _make_element(tag, *new_children, **norm_props)

        # Assign key for keyed diffing
        elem.key = key

        return elem

    factory.__name__ = tag
    return factory


# create all HTML tag functions
_TAGS = [
    "div",
    "span",
    "p",
    "button",
    "input",
    "img",
    "form",
    "label",
    "select",
    "option",
    "ul",
    "li",
    "ol",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "a",
    "nav",
    "header",
    "footer",
    "main",
    "section",
    "article",
    "aside",
    "textarea",
    "pre",
    "code",
    "table",
    "thead",
    "tbody",
    "tr",
    "td",
    "th",
]

globals_dict = globals()
for t in _TAGS:
    globals_dict[t] = _make_factory(t)

__all__ = _TAGS + ["tw"]

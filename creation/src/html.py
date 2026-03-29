"""
High-level HTML API for Creation.

Adds:
- tw("...") utility for Tailwind-like inline CSS
- Clean element factories
- Prop normalization (class_, for_, data_*, aria_*)
"""

from typing import Any
from ..dom.dom import _make_element



_TW_MAP = {
    # Display
    "flex": {"display": "flex"},
    "inline-flex": {"display": "inline-flex"},
    "block": {"display": "block"},
    "inline-block": {"display": "inline-block"},
    "inline": {"display": "inline"},
    "hidden": {"display": "none"},
    "grid": {"display": "grid"},
    
    # Flex Direction
    "flex-row": {"flex-direction": "row"},
    "flex-col": {"flex-direction": "column"},
    "flex-row-reverse": {"flex-direction": "row-reverse"},
    "flex-col-reverse": {"flex-direction": "column-reverse"},
    
    # Flex Wrap
    "flex-wrap": {"flex-wrap": "wrap"},
    "flex-nowrap": {"flex-wrap": "nowrap"},
    
    # Flex Grow/Shrink
    "flex-1": {"flex": "1 1 0%"},
    "flex-auto": {"flex": "1 1 auto"},
    "flex-none": {"flex": "none"},
    "grow": {"flex-grow": "1"},
    "grow-0": {"flex-grow": "0"},
    "shrink": {"flex-shrink": "1"},
    "shrink-0": {"flex-shrink": "0"},
    
    # Align Items
    "items-center": {"align-items": "center"},
    "items-start": {"align-items": "flex-start"},
    "items-end": {"align-items": "flex-end"},
    "items-stretch": {"align-items": "stretch"},
    "items-baseline": {"align-items": "baseline"},
    
    # Justify Content
    "justify-center": {"justify-content": "center"},
    "justify-start": {"justify-content": "flex-start"},
    "justify-end": {"justify-content": "flex-end"},
    "justify-between": {"justify-content": "space-between"},
    "justify-around": {"justify-content": "space-around"},
    "justify-evenly": {"justify-content": "space-evenly"},
    
    # Gap
    "gap-0": {"gap": "0"},
    "gap-1": {"gap": "0.25rem"},
    "gap-2": {"gap": "0.5rem"},
    "gap-3": {"gap": "0.75rem"},
    "gap-4": {"gap": "1rem"},
    "gap-5": {"gap": "1.25rem"},
    "gap-6": {"gap": "1.5rem"},
    "gap-8": {"gap": "2rem"},
    "gap-10": {"gap": "2.5rem"},
    "gap-12": {"gap": "3rem"},
    
    # Padding
    "p-0": {"padding": "0"},
    "p-1": {"padding": "0.25rem"},
    "p-2": {"padding": "0.5rem"},
    "p-3": {"padding": "0.75rem"},
    "p-4": {"padding": "1rem"},
    "p-5": {"padding": "1.25rem"},
    "p-6": {"padding": "1.5rem"},
    "p-8": {"padding": "2rem"},
    "p-10": {"padding": "2.5rem"},
    "p-12": {"padding": "3rem"},
    "px-1": {"padding-left": "0.25rem", "padding-right": "0.25rem"},
    "px-2": {"padding-left": "0.5rem", "padding-right": "0.5rem"},
    "px-3": {"padding-left": "0.75rem", "padding-right": "0.75rem"},
    "px-4": {"padding-left": "1rem", "padding-right": "1rem"},
    "px-6": {"padding-left": "1.5rem", "padding-right": "1.5rem"},
    "px-8": {"padding-left": "2rem", "padding-right": "2rem"},
    "py-1": {"padding-top": "0.25rem", "padding-bottom": "0.25rem"},
    "py-2": {"padding-top": "0.5rem", "padding-bottom": "0.5rem"},
    "py-3": {"padding-top": "0.75rem", "padding-bottom": "0.75rem"},
    "py-4": {"padding-top": "1rem", "padding-bottom": "1rem"},
    "py-6": {"padding-top": "1.5rem", "padding-bottom": "1.5rem"},
    "py-8": {"padding-top": "2rem", "padding-bottom": "2rem"},
    "pt-2": {"padding-top": "0.5rem"},
    "pb-2": {"padding-bottom": "0.5rem"},
    "pl-2": {"padding-left": "0.5rem"},
    "pr-2": {"padding-right": "0.5rem"},
    
    # Margin
    "m-0": {"margin": "0"},
    "m-1": {"margin": "0.25rem"},
    "m-2": {"margin": "0.5rem"},
    "m-3": {"margin": "0.75rem"},
    "m-4": {"margin": "1rem"},
    "m-6": {"margin": "1.5rem"},
    "m-8": {"margin": "2rem"},
    "m-auto": {"margin": "auto"},
    "mx-auto": {"margin-left": "auto", "margin-right": "auto"},
    "mx-2": {"margin-left": "0.5rem", "margin-right": "0.5rem"},
    "mx-4": {"margin-left": "1rem", "margin-right": "1rem"},
    "my-2": {"margin-top": "0.5rem", "margin-bottom": "0.5rem"},
    "my-4": {"margin-top": "1rem", "margin-bottom": "1rem"},
    "mt-2": {"margin-top": "0.5rem"},
    "mt-4": {"margin-top": "1rem"},
    "mb-2": {"margin-bottom": "0.5rem"},
    "mb-4": {"margin-bottom": "1rem"},
    "ml-2": {"margin-left": "0.5rem"},
    "ml-4": {"margin-left": "1rem"},
    "mr-2": {"margin-right": "0.5rem"},
    "mr-4": {"margin-right": "1rem"},
    
    # Width & Height
    "w-full": {"width": "100%"},
    "w-screen": {"width": "100vw"},
    "w-auto": {"width": "auto"},
    "w-1/2": {"width": "50%"},
    "w-1/3": {"width": "33.333%"},
    "w-2/3": {"width": "66.666%"},
    "w-1/4": {"width": "25%"},
    "w-3/4": {"width": "75%"},
    "h-full": {"height": "100%"},
    "h-screen": {"height": "100vh"},
    "h-auto": {"height": "auto"},
    "min-h-screen": {"min-height": "100vh"},
    "min-w-full": {"min-width": "100%"},
    "max-w-xl": {"max-width": "36rem"},
    "max-w-2xl": {"max-width": "42rem"},
    "max-w-4xl": {"max-width": "56rem"},
    "max-w-6xl": {"max-width": "72rem"},
    
    # Position
    "relative": {"position": "relative"},
    "absolute": {"position": "absolute"},
    "fixed": {"position": "fixed"},
    "sticky": {"position": "sticky"},
    "static": {"position": "static"},
    "inset-0": {"top": "0", "right": "0", "bottom": "0", "left": "0"},
    "top-0": {"top": "0"},
    "right-0": {"right": "0"},
    "bottom-0": {"bottom": "0"},
    "left-0": {"left": "0"},
    
    # Z-Index
    "z-0": {"z-index": "0"},
    "z-10": {"z-index": "10"},
    "z-20": {"z-index": "20"},
    "z-50": {"z-index": "50"},
    
    # Colors (Text)
    "text-white": {"color": "white"},
    "text-black": {"color": "black"},
    "text-gray-300": {"color": "#d1d5db"},
    "text-gray-400": {"color": "#9ca3af"},
    "text-gray-500": {"color": "#6b7280"},
    "text-gray-600": {"color": "#4b5563"},
    "text-gray-700": {"color": "#374151"},
    "text-red-500": {"color": "#ef4444"},
    "text-green-500": {"color": "#10b981"},
    "text-blue-500": {"color": "#3b82f6"},
    "text-purple-500": {"color": "#8b5cf6"},
    
    # Colors (Background)
    "bg-white": {"background-color": "white"},
    "bg-black": {"background-color": "black"},
    "bg-transparent": {"background-color": "transparent"},
    "bg-gray-50": {"background-color": "#f9fafb"},
    "bg-gray-100": {"background-color": "#f3f4f6"},
    "bg-gray-200": {"background-color": "#e5e7eb"},
    "bg-gray-800": {"background-color": "#1f2937"},
    "bg-gray-900": {"background-color": "#111827"},
    "bg-red-500": {"background-color": "#ef4444"},
    "bg-green-500": {"background-color": "#10b981"},
    "bg-blue-500": {"background-color": "#3b82f6"},
    "bg-blue-600": {"background-color": "#2563eb"},
    "bg-purple-500": {"background-color": "#8b5cf6"},
    
    # Typography
    "text-xs": {"font-size": "0.75rem"},
    "text-sm": {"font-size": "0.875rem"},
    "text-base": {"font-size": "1rem"},
    "text-lg": {"font-size": "1.125rem"},
    "text-xl": {"font-size": "1.25rem"},
    "text-2xl": {"font-size": "1.5rem"},
    "text-3xl": {"font-size": "1.875rem"},
    "text-4xl": {"font-size": "2.25rem"},
    "font-light": {"font-weight": "300"},
    "font-normal": {"font-weight": "400"},
    "font-medium": {"font-weight": "500"},
    "font-semibold": {"font-weight": "600"},
    "font-bold": {"font-weight": "700"},
    "text-center": {"text-align": "center"},
    "text-left": {"text-align": "left"},
    "text-right": {"text-align": "right"},
    "uppercase": {"text-transform": "uppercase"},
    "lowercase": {"text-transform": "lowercase"},
    "capitalize": {"text-transform": "capitalize"},
    "underline": {"text-decoration": "underline"},
    "line-through": {"text-decoration": "line-through"},
    "no-underline": {"text-decoration": "none"},
    
    # Border Radius
    "rounded-none": {"border-radius": "0"},
    "rounded-sm": {"border-radius": "0.125rem"},
    "rounded": {"border-radius": "0.25rem"},
    "rounded-md": {"border-radius": "0.375rem"},
    "rounded-lg": {"border-radius": "0.5rem"},
    "rounded-xl": {"border-radius": "0.75rem"},
    "rounded-2xl": {"border-radius": "1rem"},
    "rounded-full": {"border-radius": "9999px"},
    
    # Border
    "border": {"border-width": "1px", "border-style": "solid"},
    "border-0": {"border-width": "0"},
    "border-2": {"border-width": "2px"},
    "border-gray-200": {"border-color": "#e5e7eb"},
    "border-gray-300": {"border-color": "#d1d5db"},
    
    # Shadow
    "shadow-sm": {"box-shadow": "0 1px 2px rgba(0,0,0,0.05)"},
    "shadow": {"box-shadow": "0 1px 3px rgba(0,0,0,0.1), 0 1px 2px rgba(0,0,0,0.06)"},
    "shadow-md": {"box-shadow": "0 4px 6px rgba(0,0,0,0.1), 0 2px 4px rgba(0,0,0,0.06)"},
    "shadow-lg": {"box-shadow": "0 10px 15px rgba(0,0,0,0.1), 0 4px 6px rgba(0,0,0,0.05)"},
    "shadow-xl": {"box-shadow": "0 20px 25px rgba(0,0,0,0.1), 0 10px 10px rgba(0,0,0,0.04)"},
    "shadow-none": {"box-shadow": "none"},
    
    # Overflow
    "overflow-hidden": {"overflow": "hidden"},
    "overflow-auto": {"overflow": "auto"},
    "overflow-scroll": {"overflow": "scroll"},
    "overflow-visible": {"overflow": "visible"},
    
    # Cursor
    "cursor-pointer": {"cursor": "pointer"},
    "cursor-default": {"cursor": "default"},
    "cursor-not-allowed": {"cursor": "not-allowed"},
    
    # Opacity
    "opacity-0": {"opacity": "0"},
    "opacity-50": {"opacity": "0.5"},
    "opacity-75": {"opacity": "0.75"},
    "opacity-100": {"opacity": "1"},
    
    # Transitions
    "transition": {"transition": "all 0.15s ease"},
    "transition-all": {"transition": "all 0.15s ease"},
    "transition-colors": {"transition": "color 0.15s, background-color 0.15s, border-color 0.15s"},
    "transition-opacity": {"transition": "opacity 0.15s ease"},
    "duration-150": {"transition-duration": "150ms"},
    "duration-300": {"transition-duration": "300ms"},
    "duration-500": {"transition-duration": "500ms"},
    
    # Grid
    "grid-cols-1": {"grid-template-columns": "repeat(1, minmax(0, 1fr))"},
    "grid-cols-2": {"grid-template-columns": "repeat(2, minmax(0, 1fr))"},
    "grid-cols-3": {"grid-template-columns": "repeat(3, minmax(0, 1fr))"},
    "grid-cols-4": {"grid-template-columns": "repeat(4, minmax(0, 1fr))"},
    "grid-cols-6": {"grid-template-columns": "repeat(6, minmax(0, 1fr))"},
    "grid-cols-12": {"grid-template-columns": "repeat(12, minmax(0, 1fr))"},
    
    # Misc
    "space-y-2": {"display": "flex", "flex-direction": "column", "gap": "0.5rem"},
    "space-y-4": {"display": "flex", "flex-direction": "column", "gap": "1rem"},
    "space-y-6": {"display": "flex", "flex-direction": "column", "gap": "1.5rem"},
    "space-x-2": {"display": "flex", "gap": "0.5rem"},
    "space-x-4": {"display": "flex", "gap": "1rem"},
    "truncate": {"overflow": "hidden", "text-overflow": "ellipsis", "white-space": "nowrap"},
    "whitespace-nowrap": {"white-space": "nowrap"},
    "break-words": {"word-wrap": "break-word"},
}




def _tw_to_style(classes: str) -> dict[str, str]:
    """Convert Tailwind-like classes to inline style dict."""
    style: dict[str, str] = {}

    for cls in classes.split():
        if cls in _TW_MAP:
            style.update(_TW_MAP[cls])
        else:
            pass

    return style


def tw(classes: str) -> dict[str, Any]:
    """Return a special marker dict for tw styles."""
    # Note: Pseudo-classes like hover: are not yet supported
    return {"__tw_style__": _tw_to_style(classes)}




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




def _make_factory(tag: str):
    def factory(*children: Any, **props: Any):
        flat = _flatten_children(children)
        norm_props = _normalize_props(props)

        key = norm_props.pop("key", None)

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

        elem = _make_element(tag, *new_children, **norm_props)

        elem.key = key

        return elem

    factory.__name__ = tag
    return factory


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

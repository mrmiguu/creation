"""
High-level HTML api for evolve.

Adds:
- Clean element factory
- tw("...") Tailwind-like inline css utility
- props normalization(data_,class_,for_,aria_)

"""

from typing import Any, Callable
from .dom import dom as dom_


# Tailwind-like translator

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


def _tw_to_style(classes:str)->dict[str,str]:
    """
    Converts tw string to inline style dict
    """
    
    style = dict[str, str]
    
    for cls in classes.split():
        if cls in _TW_MAP:
            style.update(_TW_MAP[cls])
        else:
            pass
        
    return style
    
    
    
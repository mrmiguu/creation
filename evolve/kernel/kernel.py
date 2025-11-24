"""
Python wrapper for the window.EvolveKernel JS object (Pyodide environment).

Usage:
    from evolve.kernel import kernel

    node_id = kernel.dom.create("div", {"textContent": "hello"})
    kernel.log("info", "created node %s" % node_id)

    # Register a python callback:
    def on_click(ev):
        print("clicked", ev)
    cb_id = kernel.register_callback(on_click)
    kernel.dom.update(node_id, {"onclick": str(cb_id)})

Notes:
- This module expects Pyodide (pyodide.create_proxy) and `window.EvolveKernel` to exist.
- Keep references to callbacks if you plan to unregister later (this module does that for you).
"""
from collections.abc import Callable
from js import EvolveKernel
from pyodide import createproxy
import asyncio

# string callback_proxies and pyfunction in dict , so Garbage collector wont remove them
_callback_proxies: dict[int,any] = {}
# reverse mapping fromm callback ID-->callback Function
_callback_pyfuncs:dict[int,Callable] = {}

def _to_py(js_value:any) -> any:
    
    """
    Converts JS --> Python for objects that support to_py()
    """
    try:
        if hasattr(js_value,"to_py"):
            return js_value.to_py()
    except Exception:
        pass
    return js_value


# LOGGING

def log(level:str, msg:str)->dict[str,any]:
    try:
        
        res = EvolveKernel.log(level,msg)
        return _to_py(res)
    except Exception as e:
        return{"ok":False, "error":str(e)}
    
# DOM WRAPPERS

class _Dom:
    @staticmethod
    def create(tag:str, props:dict[str,any] | None = None, children:list[any] | None= None) ->dict[str, any] :
        
        

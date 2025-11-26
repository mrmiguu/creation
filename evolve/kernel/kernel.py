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

from typing import Any, Callable
from js import EvolveKernel
from pyodide import create_proxy
import asyncio

# string callback_proxies and pyfunction in dict , so Garbage collector wont remove them
_callback_proxies: dict[int, Any] = {}
# reverse mapping fromm callback ID-->callback Function
_callback_pyfuncs: dict[int, Callable] = {}


def _to_py(js_value: Any) -> Any:
    """
    Converts JS --> Python for objects that support to_py()
    """
    try:
        if hasattr(js_value, "to_py"):
            return js_value.to_py()
    except Exception:
        pass
    return js_value


# LOGGING


def log(level: str, msg: str) -> dict[str, Any]:
    try:
        res = EvolveKernel.log(level, msg)
        return _to_py(res)
    except Exception as e:
        return {"ok": False, "error": str(e)}


# DOM WRAPPERS


class _Dom:
    @staticmethod
    def create(
        tag: str, props: dict[str, Any] | None = None, children: list[Any] | None = None) -> dict[str, Any]:
        props = props or {}
        children = children or []

        try:
            res = EvolveKernel.dom.create(tag, props, children)
            return _to_py(res)
        except Exception as e:
            return {"ok": False, "error": str(e)}
        
    @staticmethod
    def remove(node_id: int) -> dict[str, Any]:
        try:
            res = EvolveKernel.dom.remove(int(node_id))
            return _to_py(res)
        except Exception as e:
            return {"ok": False, "error": str(e)}

    @staticmethod
    def update(nodeID: int, props: dict[str, Any] | None = None) -> dict[str, Any]:
        props = props or {}
        try:
            res = EvolveKernel.dom.update(nodeID, props)
            return _to_py(res)
        except Exception as e:
            return {"ok": False, "error": str(e)}

    @staticmethod
    def append(parentID: int, nodeID: int) -> dict[str, Any]:
        try:
            res = EvolveKernel.dom.append(parentID, nodeID)
            return _to_py(res)
        except Exception as e:
            return {"ok": False, "error": str(e)}

    @staticmethod
    def query(selector: str) -> dict[str, Any]:
        try:
            res = EvolveKernel.dom.query(selector)

            return _to_py(res)
        except Exception as e:
            return {"ok": False, "error": str(e)}


# exposing public interface as kernel.dom.method instead of kernel._DOM.method
# just making it look good.
dom = _Dom()


# FILE SYSTEM WRAPPERS


class _FS:
    
    @staticmethod
    def read(path: str) -> dict[str, Any]:
        try:
            res = EvolveKernel.fs.read(path)
            return _to_py(res)
        except Exception as e:
            return {"ok": False, "error": str(e)}

    @staticmethod
    def write(path: str, contents: Any) -> dict[str, Any]:
        try:
            res = EvolveKernel.fs.write(path, contents)
            return _to_py(res)
        except Exception as e:
            return {"ok": False, "error": str(e)}


fs = _FS()


# NETWORK WRAPPER (ASYNC)


class _NET:
    @staticmethod
    async def fetch(url: str, options: dict[str,Any] | None = None) -> dict[str, Any]:
        options = options or {}

        try:
            res = await EvolveKernel.net.fetch(url, options)
            return _to_py(res)
        except Exception as e:
            return {"ok": False, "error": str(e)}


net = _NET()


# CALLBACK REGISTRATION


def register_callback(py_fun: Callable) -> int:
    """
    Registers python function as JS-callable callback
    """

    if not callable(py_fun):
        raise TypeError("register_callback expects a callable function")

    # create proxy for JS to call python functions
    # *a- accept Any number of arguments
    # **k- accept Any number of keyword arguments
    # then call _call_python_callback function with these arguments
    proxy = create_proxy(lambda *a, **k: _call_python_callback(py_fun, a, k))

    try:
        res = EvolveKernel.registerCallback(proxy)
        res_py = _to_py(res)
        if not res_py.get("ok", False):
            proxy.destroy()
            raise RuntimeError(f"registerCallback failed: {res_py.get('error')}")

        cb_id = int(res_py["value"])
        _callback_proxies[cb_id] = proxy
        _callback_pyfuncs[cb_id] = py_fun
        return cb_id
    except Exception as e:
        try:
            proxy.destroy()
        except Exception:
            pass
        raise e


def _call_python_callback(py_fun: Callable, args: tuple, kargs: dict) -> Any:
    """
    JS --> Python callaback handlers
    """

    py_args = tuple(_to_py(a) for a in args)
    py_kargs = {k: _to_py(v) for k, v in kargs.items()}

    try:
        result = py_fun(*py_args, **py_kargs)
        if asyncio.iscoroutine(result):
            asyncio.ensure_future(result)
        return result
    except Exception as e:
        log("error", f"callback error:{e}")
        return {"ok": False, "error": str(e)}


def unregister_callback(cb_id: int) -> dict[str, Any]:
    cb_id = int(cb_id)

    proxy = _callback_proxies.pop(cb_id, None)
    _callback_pyfuncs.pop(cb_id, None)

    if proxy:
        try:
            proxy.destroy()

        except Exception:
            pass

    try:
        res = EvolveKernel.unregisterCallback(cb_id)
        return _to_py(res)
    except Exception as e:
        return {"ok": False, "error": str(e)}


# KERNEL FACADE
# Public interface for accessibility


class KernelFacade:
    dom = dom
    fs = fs
    net = net
    log = staticmethod(log)
    register_callback = staticmethod(register_callback)
    unregister_callback = staticmethod(unregister_callback)


kernel = KernelFacade()

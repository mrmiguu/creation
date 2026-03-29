"""
Python wrapper for the window.CreationKernel JS object (Pyodide environment).

Usage:
    from creation.kernel import kernel

    node_id = kernel.dom.create("div", {"textContent": "hello"})
    kernel.log("info", "created node %s" % node_id)

    def on_click(ev):
        print("clicked", ev)
    cb_id = kernel.register_callback(on_click)
    kernel.dom.update(node_id, {"onclick": str(cb_id)})

Notes:
- This module expects Pyodide (pyodide.create_proxy) and `window.CreationKernel` to exist.
- Keep references to callbacks if you plan to unregister later (this module does that for you).
"""

from typing import Any, Callable
from js import CreationKernel
from pyodide.ffi import create_proxy, to_js
import asyncio

_callback_proxies: dict[int, Any] = {}
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




def log(level: str, msg: str) -> dict[str, Any]:
    try:
        res = CreationKernel.log(level, msg)
        return _to_py(res)
    except Exception as e:
        return {"ok": False, "error": str(e)}






def _deep_sanitize(v):
    """
    Convert PyProxies to plain Python values (via to_py()) and recursively
    sanitize dicts/lists so that to_js receives only normal Python primitives/containers.
    """
    # Fast path for common primitives - no processing needed
    if v is None or isinstance(v, (str, int, float, bool)):
        return v
    
    # Handle PyProxy objects
    try:
        if hasattr(v, "to_py"):
            try:
                return v.to_py()
            except Exception:
                pass
    except Exception:
        pass

    if isinstance(v, dict):
        out = {}
        for k, vv in v.items():
            out[k] = _deep_sanitize(vv)
        return out

    if isinstance(v, (list, tuple)):
        return [_deep_sanitize(i) for i in v]

    return v


class _Dom:
    def create(self, tag, props=None, children=None):
        props = props or {}
        children = children or []

        try:
            safe_props = _deep_sanitize(props)
            safe_children = _deep_sanitize(children)

            js_props = to_js(safe_props, dict_converter=dict)
            js_children = to_js(safe_children)


            res = CreationKernel.dom.create(tag, js_props, js_children)
            return _to_py(res)
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def update(self, nodeID, props=None):
        props = props or {}
        try:
            safe_props = _deep_sanitize(props)
            js_props = to_js(safe_props, dict_converter=dict)


            res = CreationKernel.dom.update(nodeID, js_props)
            return _to_py(res)
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def remove(self, node_id):
        try:
            res = CreationKernel.dom.remove(int(node_id))
            return _to_py(res)
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def insert_at(self, parentID, nodeID, index):
        try:
            res = CreationKernel.dom.insertAt(int(parentID), int(nodeID), int(index))
            return _to_py(res)
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def append(self, parentID, nodeID):
        try:
            res = CreationKernel.dom.append(parentID, nodeID)
            return _to_py(res)
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def query(self, selector):
        try:
            res = CreationKernel.dom.query(selector)
            return _to_py(res)
        except Exception as e:
            return {"ok": False, "error": str(e)}


dom = _Dom()




class _FS:
    @staticmethod
    def read(path: str) -> dict[str, Any]:
        try:
            res = CreationKernel.fs.read(path)
            return _to_py(res)
        except Exception as e:
            return {"ok": False, "error": str(e)}

    @staticmethod
    def write(path: str, contents: Any) -> dict[str, Any]:
        try:
            res = CreationKernel.fs.write(path, contents)
            return _to_py(res)
        except Exception as e:
            return {"ok": False, "error": str(e)}


fs = _FS()




class _NET:
    @staticmethod
    async def fetch(url: str, options: dict[str, Any] | None = None) -> dict[str, Any]:
        options = options or {}

        try:
            res = await CreationKernel.net.fetch(url, options)
            return _to_py(res)
        except Exception as e:
            return {"ok": False, "error": str(e)}


net = _NET()




class _Location:
    @staticmethod
    def get_path() -> str:
        try:
            return _to_py(CreationKernel.location.getPath())
        except Exception:
            return "/"

    @staticmethod
    def push(path: str) -> dict[str, Any]:
        try:
            return _to_py(CreationKernel.location.push(path))
        except Exception as e:
            return {"ok": False, "error": str(e)}

    @staticmethod
    def replace(path: str) -> dict[str, Any]:
        try:
            return _to_py(CreationKernel.location.replace(path))
        except Exception as e:
            return {"ok": False, "error": str(e)}

    @staticmethod
    def on_change(py_callback: Callable) -> dict[str, Any]:
        """
        Registers a python function to be called on browser popstate
        """
        try:
            cb_id = register_callback(py_callback)
            return _to_py(CreationKernel.location.onChange(cb_id))
        except Exception as e:
            return {"ok": False, "error": str(e)}


location = _Location()



def register_callback(py_fun: Callable) -> int:
    """
    Registers python function as JS-callable callback
    """

    if not callable(py_fun):
        raise TypeError("register_callback expects a callable function")

    proxy = create_proxy(lambda *a, **k: _call_python_callback(py_fun, a, k))

    try:
        res = CreationKernel.registerCallback(proxy)
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
    JS --> Python callback handlers.
    Gracefully handles argument mismatch (e.g., lambda with no params receiving event).
    """

    py_args = tuple(_to_py(a) for a in args)
    py_kargs = {k: _to_py(v) for k, v in kargs.items()}

    try:
        # Try calling with provided arguments first
        result = py_fun(*py_args, **py_kargs)
    except TypeError as te:
        # If argument mismatch, try calling without arguments
        # This handles `lambda: ...` style callbacks that don't need event
        if "positional argument" in str(te) or "takes 0" in str(te):
            try:
                result = py_fun()
            except Exception as e2:
                log("error", f"callback error:{e2}")
                return {"ok": False, "error": str(e2)}
        else:
            log("error", f"callback error:{te}")
            return {"ok": False, "error": str(te)}
    except Exception as e:
        log("error", f"callback error:{e}")
        return {"ok": False, "error": str(e)}
    
    if asyncio.iscoroutine(result):
        asyncio.ensure_future(result)
    return result


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
        res = CreationKernel.unregisterCallback(cb_id)
        return _to_py(res)
    except Exception as e:
        return {"ok": False, "error": str(e)}




class KernelFacade:
    dom = dom
    fs = fs
    net = net
    location = location
    log = staticmethod(log)
    register_callback = staticmethod(register_callback)
    unregister_callback = staticmethod(unregister_callback)


kernel = KernelFacade()

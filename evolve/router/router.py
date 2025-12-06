"""
Evolve router system.
- @page("/") decorator
- History API routing
- Dynamic route params (/user/:id)
- clean mounting and unmounting
- Navigate() function
"""

from typing import Callable, Any
import re
from ..components.component import ComponentInstance
from ..kernel.kernel import kernel
from ..dom.dom import div, Element


from ..src.html import _flatten_children, _normalize_props, a
from ..components.component import component




def Link(to: str, *children, **props) -> Element:
    """
    Link("/path", child1, child2, ..., tw("..."), class_="...")

    Behaves like <a>, but prevents default navigation and uses router.navigate().
    """
    from .router import navigate  # local import to avoid circular

    flat = _flatten_children(children)

    final_children = []
    tw_style = {}

    for ch in flat:
        if isinstance(ch, dict) and "__tw_style__" in ch:
            tw_style.update(ch["__tw_style__"])
        else:
            final_children.append(ch)

    norm = _normalize_props(props)

    if tw_style:
        if "style" in norm and isinstance(norm["style"], dict):
            norm["style"] = {**norm["style"], **tw_style}
        else:
            norm["style"] = tw_style

    norm["href"] = to

    def _on_click(ev):
        try:
            ev.preventDefault()
        except Exception:
            pass

        navigate(to)

    norm["on_click"] = _on_click

    return a(*final_children, **norm)




class Route:
    def __init__(self, pattern: str, component_fn: Callable):
        self.pattern = pattern
        self.component_fn = component_fn
        self.regex, self.param_names = self._compile(pattern)

    def _compile(self, pattern: str):
        """
        Convert '/user/:id' → regex ^/user/([^/]+)$ with param name ['id']
        """

        parts = pattern.split("/")

        regex_parts = []
        param_names = []

        for part in parts:
            if part.startswith(":"):
                param_names.append(part[1:])
                regex_parts.append("([^/]+)")
            else:
                regex_parts.append(part)

        regex_str = "^" + "/".join(regex_parts) + "$"
        return re.compile(regex_str), param_names

    def match(self, path: str):
        m = self.regex.match(path)
        if not m:
            return None

        params = {}
        if self.param_names:
            for name, value in zip(self.param_names, m.groups()):
                params[name] = value
        return params


ROUTES: list[Route] = []




def page(pattern: str):
    def decorator(fn: Callable):
        comp_fn = component(fn)   # wrap into ComponentInstance factory
        ROUTES.append(Route(pattern, comp_fn))
        return comp_fn
    return decorator


def navigate(path: str):
    kernel.location.push(path)
    Router.instance()._on_path_change()


class Router:
    _instance = None

    @staticmethod
    def instance():
        if Router._instance is None:
            Router._instance = Router()

            return Router._instance

    def __init__(self):
        self.current_component = None
        self.root_id = None

        q = kernel.dom.query("#app")
        existing = q.get("value")

        if existing:
            self.root_id = existing
        else:
            res = kernel.dom.create("div", {"id": "app"}, [])
            if not res.get("ok"):
                raise RuntimeError(f"Failed to create root: {res.get('error')}")
            self.root_id = res.get("value")

            body_id = kernel.dom.query("body")["value"]
            kernel.dom.append(body_id, self.root_id)

        kernel.location.on_change(self._on_path_change)

        self._on_path_change()




    def match_route(self, path: str):
        for route in ROUTES:
            params = route.match(path)

            if params is not None:
                return route, params

        return None, None


    def _on_path_change(self):
        path = kernel.location.get_path()

        route, params = self.match_route(path)

        if route is None:
            @component
            def NotFound():
                return div(
                    div(
                        "404",
                        style={"fontSize": "4rem", "fontWeight": "bold", "color": "#ef4444"}
                    ),
                    div("Page Not Found", style={"fontSize": "1.25rem", "color": "#6b7280"}),
                    div(
                        f"The path '{path}' does not exist.",
                        style={"fontSize": "0.875rem", "color": "#9ca3af", "marginTop": "0.5rem"}
                    ),
                    style={
                        "display": "flex",
                        "flexDirection": "column",
                        "alignItems": "center",
                        "justifyContent": "center",
                        "height": "100vh",
                        "fontFamily": "sans-serif"
                    }
                )
            self._render(NotFound(), {})
            return

        try:
            component_fn = route.component_fn
            comp_inst = component_fn(params) if params else component_fn()
            self._render(comp_inst, params)
        except Exception as e:
            # Render error page instead of crashing
            kernel.log("error", f"Route error: {e}")
            
            @component
            def RouteError():
                return div(
                    div("⚠️", style={"fontSize": "3rem"}),
                    div("Something went wrong", style={"fontSize": "1.5rem", "fontWeight": "bold", "color": "#ef4444"}),
                    div(
                        str(e),
                        style={
                            "fontSize": "0.875rem",
                            "color": "#6b7280",
                            "marginTop": "1rem",
                            "padding": "1rem",
                            "background": "#f3f4f6",
                            "borderRadius": "0.5rem",
                            "maxWidth": "500px",
                            "wordBreak": "break-word"
                        }
                    ),
                    style={
                        "display": "flex",
                        "flexDirection": "column",
                        "alignItems": "center",
                        "justifyContent": "center",
                        "height": "100vh",
                        "fontFamily": "sans-serif"
                    }
                )
            self._render(RouteError(), {})


    def _render(self, comp_inst: ComponentInstance, params: dict[str, Any]):
        if self.current_component:
            self.current_component.unmount()

        comp_inst.mount_to("#app")

        self.current_component = comp_inst



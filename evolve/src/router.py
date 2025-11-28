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
from kernel.kernel import kernel
from dom.dom import div, Element


from .html import _flatten_children, _normalize_props, a


def Link(to: str, *children, **props) -> Element:
    """
    Link("/path", child1, child2, ..., tw("..."), class_="...")

    Behaves like <a>, but prevents default navigation and uses router.navigate().
    """
    from .router import navigate  # local import to avoid circular

    # Flatten children (Card(...), "Text", tw(...))
    flat = _flatten_children(children)

    # Extract tw() style dicts or other dict children
    final_children = []
    tw_style = {}

    for ch in flat:
        # tw() children are dicts with __tw_style__
        if isinstance(ch, dict) and "__tw_style__" in ch:
            tw_style.update(ch["__tw_style__"])
        else:
            final_children.append(ch)

    # Normalize standard props (class_, data_*, etc.)
    norm = _normalize_props(props)

    # Merge tw style
    if tw_style:
        if "style" in norm and isinstance(norm["style"], dict):
            norm["style"] = {**norm["style"], **tw_style}
        else:
            norm["style"] = tw_style

    # Add the link href (for SEO, middle-click, long press on mobile)
    norm["href"] = to

    # Add the on_click handler
    def _on_click(ev):
        # prevent default browser navigation
        try:
            ev.preventDefault()
        except Exception:
            pass

        # SPA navigation
        navigate(to)

    norm["on_click"] = _on_click

    # Return a standard <a> element
    return a(*final_children, **norm)


#  ROUTE REGISTRY


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


# @page decorator


def page(pattern: str):
    """
    @page("/") --> register route
    """

    def decorator(fn: Callable):
        ROUTES.append(Route(pattern, fn))
        return fn

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
        self.current_component: ComponentInstance | None = None
        self.root_id: int | None = None

        # create root dic automatically
        res = kernel.dom.create("div", {"id": "__evolve_root__"}, [])

        if not res.get("ok"):
            raise RuntimeError(f"failed to create a root :{res.get('error')}")

        self.root_id = int(res.get("value"))

        # append to body

        body_id = kernel.dom.query("body")["value"]

        kernel.dom.append(body_id, self.root_id)

        # Listen to pop_state (back/forward)
        kernel.location.on_change(self._on_path_change)

        # initial render
        self._on_path_change()

    # ROUTE MATCHING

    def match_route(self, path: str):
        for route in ROUTES:
            params = route.match(path)

            if params is not None:
                return route, params

        return None, None

    # RENDER + UNMOUNT

    def _on_path_change(self):
        path = kernel.location.get_path()

        route, params = self.match_route(path)

        if route is None:
            # render 404 page

            comp = div("404 - Page Not Found")

            self._render(comp, {})
            return

        component_fn = route.component_fn
        comp_elem = component_fn(params) if params else component_fn()

        if not isinstance(comp_elem, ComponentInstance):
            # convert it to component instance
            comp_elem = ComponentInstance(component_fn, props=params or {}, children=[])

        self._render(comp_elem, params)

    def _render(self, comp_inst: ComponentInstance, params: dict[str, Any]):
        # unmount previous component

        if self.current_component:
            self.current_component.unmount()

        # mount_new
        comp_inst.container._build()
        kernel.dom.remove(self.root_id)
        kernel.dom.append(self.root_id, comp_inst.container.node_id)
        self.current_component = comp_inst

from typing import Any, Callable
from .component import ComponentInstance 
from .html import div

# GLOBAL registry of context stacks
_CONTEXTS = {}

class Context:
    def __init__(self, default=None):
        self.default = default
        self._key = id(self)  # unique stack key
        _CONTEXTS[self._key] = []

    def provide(self, value, *children):
        """
        Wrap children in a context provider.
        This creates a special 'ProviderWrapper' component instance.
        """
        return ProviderWrapper(self, value, list(children))


def create_context(default=None) -> Context:
    return Context(default)


def use_context(ctx: Context) -> Any:
    stack = _CONTEXTS.get(ctx._key, [])
    return stack[-1] if stack else ctx.default


#   Provider Wrapper Component  

class ProviderWrapper:
    """
    This is not a DOM element; it's a component wrapper that:
    - pushes context value before children render
    - pops after render
    """
    def __init__(self, ctx: Context, value: Any, children: list[Any]):
        self.ctx = ctx
        self.value = value
        self.children = children

    def __call__(self, props=None):
        # This behaves like a component: return children
        return div(*self.children)

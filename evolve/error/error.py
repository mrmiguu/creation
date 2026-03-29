from typing import Any, Callable
from ..src.html import div
from ..components.component import ComponentInstance, _ensure_element
from ..reactive.reactive import signal

class ErrorBoundaryWrapper:
    """
    Internal wrapper that acts like a component:
    It tries to render children; if an error happens, shows fallback.
    """
    def __init__(self, fallback: Callable[[Exception], Any], children: list[Any], on_error=None):
        self.fallback = fallback
        self.children = children
        self.on_error = on_error
        self._error_signal = signal(None)

    def reset(self):
        """Reset error state."""
        self._error_signal(None, _sentinel=True)

    def __call__(self, props=None):
        err = self._error_signal()

        if err is not None:
            fallback_out = self.fallback(err)
            return _ensure_element(fallback_out)

        try:
            return div(*self.children)
        except Exception as e:
            self._error_signal(e)
            if callable(self.on_error):
                try:
                    self.on_error(e)
                except:
                    pass
            fallback_out = self.fallback(e)
            return _ensure_element(fallback_out)


def ErrorBoundary(*children, fallback, on_error=None):
    """
    Public API:
    ErrorBoundary(fallback=lambda err: div(...), children...)
    """
    return ComponentInstance(
        fn=ErrorBoundaryWrapper(fallback, list(children), on_error),
        props={},
        children=[]
    )

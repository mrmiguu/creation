"""
Evolve - A Python web framework powered by Pyodide.

Core APIs:
    - signal, computed, effect, batch - Reactive primitives
    - component, @page, Link - Component and routing
    - div, span, button, etc. - HTML elements with tw() styling
    - set_timeout, set_interval - Browser timers
    - create_store - Global state management
    - use_effect, use_memo, use_ref - React-like hooks

Note: Browser-only modules (kernel, dom, timers) are only imported at runtime
in Pyodide, not at CLI time.
"""

__version__ = "0.1.0"

# Only export version at module level
# All other exports are available via explicit imports:
#   from evolve.reactive.reactive import signal, computed, effect, batch
#   from evolve.components.component import component
#   from evolve.router.router import page, Link, navigate
#   from evolve.kernel.timers import set_timeout, set_interval
#   from evolve.store.store import create_store
#   from evolve.hooks.hooks import use_effect, use_memo, use_ref
#   from evolve.src.html import tw, div, span, button, ...

__all__ = ["__version__"]


def __getattr__(name):
    """
    Lazy import to avoid loading browser-only modules at CLI time.
    This allows the CLI to work while still providing convenient imports
    when running in Pyodide.
    """
    # Reactive (safe to import)
    if name in ("signal", "computed", "effect", "batch", "Signal", "Computed"):
        from .reactive.reactive import signal, computed, effect, batch, Signal, Computed
        return locals()[name]
    
    # Store (safe to import)
    if name in ("create_store", "init_store", "get_store"):
        from .store.store import create_store, init_store, get_store
        return locals()[name]
    
    # The following require browser environment (js module)
    # They will fail at CLI time but work in Pyodide
    
    if name == "component":
        from .components.component import component
        return component
    
    if name in ("page", "Link", "navigate"):
        from .router.router import page, Link, navigate
        return locals()[name]
    
    if name in ("set_timeout", "set_interval", "clear_timeout", "clear_interval"):
        from .kernel.timers import set_timeout, set_interval, clear_timeout, clear_interval
        return locals()[name]
    
    if name in ("use_effect", "use_memo", "use_ref", "use_callback"):
        from .hooks.hooks import use_effect, use_memo, use_ref, use_callback
        return locals()[name]
    
    if name in ("tw", "div", "span", "p", "button", "input", "a", "h1", "h2", "h3", "h4", "h5", "h6"):
        from .src.html import tw, div, span, p, button, input, a, h1, h2, h3, h4, h5, h6
        return locals()[name]
    
    if name == "ErrorBoundary":
        from .error.error import ErrorBoundary
        return ErrorBoundary
    
    if name in ("create_context", "use_context"):
        from .context.context import create_context, use_context
        return locals()[name]
    
    if name in ("on_mount", "on_cleanup"):
        from .core.lifecycle import on_mount, on_cleanup
        return locals()[name]
    
    raise AttributeError(f"module 'evolve' has no attribute '{name}'")

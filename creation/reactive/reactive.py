"""
Reactive system for Creation.

Provides:
- Signal: reactive state container
- Computed: derived reactive value
- effect: side effect that re-runs when dependencies change
- signal(): hook-style state that persists across component renders
- batch(): group multiple updates into single re-render
"""

from typing import Any, Callable, List, TypeVar, Generic
from contextlib import contextmanager

T = TypeVar("T")

_current_effect_stack: List["_Effect"] = []

# Batching system
_is_batching = False
_pending_effects: set = set()


@contextmanager
def batch():
    """
    Batch multiple signal updates into a single re-render.
    
    Example:
        with batch():
            count(count() + 1)
            name("New name")
            items([...])
        # Only ONE re-render happens here
    """
    global _is_batching, _pending_effects
    
    was_batching = _is_batching
    _is_batching = True
    
    try:
        yield
    finally:
        _is_batching = was_batching
        
        # If we're the outermost batch, flush pending effects
        if not _is_batching and _pending_effects:
            effects_to_run = list(_pending_effects)
            _pending_effects.clear()
            
            for eff in effects_to_run:
                eff.run()


class _Effect:
    def __init__(self, fn: Callable[[], Any]):
        self.fn = fn
        self.dependencies = set()
        self._is_running = False

    def run(self):
        if self._is_running:
            return
        self._is_running = True

        # Clean up old dependencies
        for sig in list(self.dependencies):
            sig._unsubscribe_effect(self)
        self.dependencies.clear()

        _current_effect_stack.append(self)
        try:
            self.fn()
        finally:
            _current_effect_stack.pop()
            self._is_running = False
    
    def schedule(self):
        """Schedule effect to run (immediate or batched)."""
        global _is_batching, _pending_effects
        
        if _is_batching:
            _pending_effects.add(self)
        else:
            self.run()

    def add_dependency(self, sig: "Signal"):
        self.dependencies.add(sig)


class Signal(Generic[T]):
    def __init__(self, value: T):
        self._value = value
        self._subscribers = set()  # Set of _Effects
        self._manual_subs = {}  # id -> fn
        self._next_id = 0

    def __call__(self, new_value: T = None, _sentinel: object = None) -> T:
        # If called with an argument, set the value
        if new_value is not None or _sentinel is not None:
            self.set(new_value)
            return self._value

        # Otherwise, read the value (with dependency tracking)
        if _current_effect_stack:
            eff = _current_effect_stack[-1]
            eff.add_dependency(self)
            self._subscribers.add(eff)
        return self._value

    def set(self, new_value: T):
        if self._value != new_value:
            self._value = new_value
            self._notify()

    def _notify(self):
        # Schedule effects (respects batching)
        for sub in list(self._subscribers):
            if isinstance(sub, _Effect):
                sub.schedule()

        # Notify manual subs (used by dom.py for prop bindings)
        for fn in self._manual_subs.values():
            try:
                fn(self._value)
            except Exception:
                pass

    def subscribe(self, fn: Callable[[T], None]) -> int:
        """Manual subscription used by dom.py"""
        sid = self._next_id
        self._next_id += 1
        self._manual_subs[sid] = fn
        return sid

    def unsubscribe(self, sid: int):
        if sid in self._manual_subs:
            del self._manual_subs[sid]

    def _unsubscribe_effect(self, eff: _Effect):
        if eff in self._subscribers:
            self._subscribers.remove(eff)


class Computed(Signal[T]):
    def __init__(self, fn: Callable[[], T]):
        super().__init__(None)
        self.fn = fn
        self._effect = _Effect(self._update)
        self._effect.run()

    def _update(self):
        new_val = self.fn()
        if self._value != new_val:
            self._value = new_val
            self._notify()

    def __call__(self) -> T:
        return super().__call__()


def effect(fn: Callable[[], Any]):
    e = _Effect(fn)
    e.run()
    return e


# =============================================================================
# Hook-style signal() that persists state across component re-renders
# =============================================================================

def signal(initial_value: T) -> Signal[T]:
    """
    Create or retrieve a cached Signal for the current component.
    
    Works like React's useState - the signal persists across re-renders.
    On first render: creates a new Signal with initial_value.
    On subsequent renders: returns the existing Signal (ignores initial_value).
    """
    from ..core.lifecycle import _CURRENT_COMPONENT_STACK
    
    # If not inside a component render, just create a standalone signal
    if not _CURRENT_COMPONENT_STACK:
        return Signal(initial_value)
    
    comp = _CURRENT_COMPONENT_STACK[-1]
    
    # Hook storage is pre-initialized in ComponentInstance.__init__
    idx = comp._hook_index
    comp._hook_index += 1
    
    # First render or new hook slot
    if idx >= len(comp._hook_signals):
        sig = Signal(initial_value)
        comp._hook_signals.append(sig)
        return sig
    
    # Subsequent render - return cached signal
    return comp._hook_signals[idx]


def computed(fn: Callable[[], T]) -> Computed[T]:
    """
    Create or retrieve a cached Computed for the current component.
    """
    from ..core.lifecycle import _CURRENT_COMPONENT_STACK
    
    if not _CURRENT_COMPONENT_STACK:
        return Computed(fn)
    
    comp = _CURRENT_COMPONENT_STACK[-1]
    
    # Hook storage is pre-initialized in ComponentInstance.__init__
    idx = comp._hook_computed_index
    comp._hook_computed_index += 1
    
    if idx >= len(comp._hook_computeds):
        c = Computed(fn)
        comp._hook_computeds.append(c)
        return c
    
    return comp._hook_computeds[idx]

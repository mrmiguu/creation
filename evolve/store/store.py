"""
Global State Store for Evolve.

Provides a simple, signal-based global state management system.
Similar to Zustand or Redux Toolkit's createSlice.
"""

from typing import Any, Callable, Dict, TypeVar, Generic
from ..reactive.reactive import Signal

T = TypeVar("T")


class Store(Generic[T]):
    """
    A global state store backed by signals.
    
    Example:
        # Create store
        store = create_store({
            "user": None,
            "theme": "dark",
            "count": 0,
        })
        
        # Get values (reactive)
        user = store.get("user")
        
        # Set values
        store.set("theme", "light")
        
        # Subscribe to changes
        store.subscribe("count", lambda val: print(f"Count: {val}"))
        
        # Get entire state
        state = store.state()
    """
    
    def __init__(self, initial_state: Dict[str, Any]):
        self._signals: Dict[str, Signal] = {}
        
        for key, value in initial_state.items():
            self._signals[key] = Signal(value)
    
    def get(self, key: str) -> Any:
        """
        Get a value from the store (reactive).
        Reading inside a component will track dependencies.
        """
        if key not in self._signals:
            raise KeyError(f"Store key '{key}' not found")
        return self._signals[key]()
    
    def set(self, key: str, value: Any):
        """Set a value in the store, triggering subscribers."""
        if key not in self._signals:
            # Dynamically add new keys
            self._signals[key] = Signal(value)
        else:
            self._signals[key](value)
    
    def update(self, key: str, updater: Callable[[Any], Any]):
        """
        Update a value using a function.
        
        Example:
            store.update("count", lambda c: c + 1)
        """
        current = self.get(key)
        new_value = updater(current)
        self.set(key, new_value)
    
    def subscribe(self, key: str, callback: Callable[[Any], None]) -> int:
        """
        Subscribe to changes on a specific key.
        Returns a subscription ID for unsubscribing.
        """
        if key not in self._signals:
            raise KeyError(f"Store key '{key}' not found")
        return self._signals[key].subscribe(callback)
    
    def unsubscribe(self, key: str, sub_id: int):
        """Unsubscribe from a key's changes."""
        if key in self._signals:
            self._signals[key].unsubscribe(sub_id)
    
    def state(self) -> Dict[str, Any]:
        """Get the entire state as a dict (snapshot, not reactive)."""
        return {key: sig() for key, sig in self._signals.items()}
    
    def keys(self) -> list:
        """Get all keys in the store."""
        return list(self._signals.keys())
    
    def signal(self, key: str) -> Signal:
        """
        Get the raw Signal for a key.
        Useful for advanced use cases.
        """
        if key not in self._signals:
            raise KeyError(f"Store key '{key}' not found")
        return self._signals[key]


def create_store(initial_state: Dict[str, Any]) -> Store:
    """
    Create a new global store with initial state.
    
    Example:
        app_store = create_store({
            "user": None,
            "todos": [],
            "settings": {"theme": "dark"},
        })
    """
    return Store(initial_state)


# Convenience: global app store (optional singleton pattern)
_global_store: Store = None


def get_store() -> Store:
    """Get the global app store (must be initialized first)."""
    global _global_store
    if _global_store is None:
        raise RuntimeError("Global store not initialized. Call init_store() first.")
    return _global_store


def init_store(initial_state: Dict[str, Any]) -> Store:
    """Initialize the global app store."""
    global _global_store
    _global_store = create_store(initial_state)
    return _global_store

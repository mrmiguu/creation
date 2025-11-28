from typing import Any, Dict, Callable
from ..reactive.reactive import signal

class Store:
    def __init__(self, initial: Dict[str, Any]):
        self._initial = initial.copy()
        self._signals = {k: signal(v) for k, v in initial.items()}

    #  READ 
    def __call__(self, key: str) -> Any:
        """Store('foo') -> reads the slice and subscribes reactively."""
        if key not in self._signals:
            raise KeyError(f"Store has no key '{key}'")
        return self._signals[key]()

    def get(self) -> Dict[str, Any]:
        """Non-reactive snapshot."""
        return {k: sig() for k, sig in self._signals.items()}

    #  WRITE 
    def set(self, key: str, value: Any):
        if key not in self._signals:
            raise KeyError(f"Store has no key '{key}'")
        self._signals[key].set(value)

    def update(self, patch: Dict[str, Any]):
        for k, v in patch.items():
            if k in self._signals:
                self._signals[k].set(v)

    def reset(self):
        for k, v in self._initial.items():
            self._signals[k].set(v)

    # convenience
    def toggle(self, key: str):
        if key not in self._signals:
            raise KeyError(f"Store has no key '{key}'")
        cur = self._signals[key]()
        if not isinstance(cur, bool):
            raise TypeError("toggle() works only for booleans")
        self._signals[key].set(not cur)


def create_store(initial: Dict[str, Any]) -> Store:
    return Store(initial)

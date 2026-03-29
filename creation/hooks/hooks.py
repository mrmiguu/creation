"""
React-like Hooks for Creation.

Provides common hook patterns for component lifecycle and optimization:
- use_effect: Side effects with cleanup
- use_memo: Memoized computed values
- use_ref: Persistent reference across renders
- use_callback: Memoized callback functions
"""

from typing import Any, Callable, List, Optional, TypeVar
from ..core.lifecycle import current_component, on_cleanup

T = TypeVar("T")


def use_effect(fn: Callable[[], Optional[Callable]], deps: Optional[List[Any]] = None):
    """
    Run a side effect when dependencies change.
    
    The function can optionally return a cleanup function that runs
    before the next effect or when the component unmounts.
    
    Args:
        fn: Effect function. Can return a cleanup function.
        deps: List of dependencies. Effect re-runs when any change.
              None means run every render. [] means run once on mount.
    
    Example:
        def MyComponent():
            count = signal(0)
            
            def subscribe():
                print("Subscribed!")
                return lambda: print("Cleanup!")
            
            use_effect(subscribe, [])  # Runs once on mount
            use_effect(lambda: print(f"Count: {count()}"), [count()])  # Runs when count changes
    """
    comp = current_component()
    
    # Hook storage is pre-initialized in ComponentInstance.__init__
    idx = comp._hook_effect_index
    comp._hook_effect_index += 1
    
    # Get previous state
    if idx >= len(comp._hook_effects):
        # First run - create new effect entry
        comp._hook_effects.append({
            "deps": None,
            "cleanup": None,
            "ran": False
        })
    
    effect_state = comp._hook_effects[idx]
    prev_deps = effect_state["deps"]
    
    # Determine if we should run
    should_run = False
    if deps is None:
        # No deps = run every render
        should_run = True
    elif not effect_state["ran"]:
        # First render
        should_run = True
    elif prev_deps is None:
        should_run = True
    elif len(deps) != len(prev_deps):
        should_run = True
    else:
        # Check if any dep changed
        for old, new in zip(prev_deps, deps):
            if old != new:
                should_run = True
                break
    
    if should_run:
        # Run cleanup from previous effect
        if effect_state["cleanup"] is not None:
            try:
                effect_state["cleanup"]()
            except Exception:
                pass
        
        # Run new effect
        cleanup = fn()
        effect_state["cleanup"] = cleanup
        effect_state["deps"] = deps[:] if deps is not None else None
        effect_state["ran"] = True
        
        # Register cleanup for unmount
        if cleanup is not None:
            on_cleanup(lambda cleanup=cleanup: cleanup())


def use_memo(fn: Callable[[], T], deps: List[Any]) -> T:
    """
    Memoize an expensive computation.
    
    Only recomputes when dependencies change.
    
    Args:
        fn: Function that computes the value
        deps: List of dependencies
    
    Returns:
        Memoized value
    
    Example:
        def MyComponent():
            items = signal([1, 2, 3, 4, 5])
            
            # Only recalculate when items change
            total = use_memo(lambda: sum(items()), [items()])
            
            return div(f"Total: {total}")
    """
    comp = current_component()
    
    # Hook storage is pre-initialized in ComponentInstance.__init__
    idx = comp._hook_memo_index
    comp._hook_memo_index += 1
    
    if idx >= len(comp._hook_memos):
        # First run
        value = fn()
        comp._hook_memos.append({
            "value": value,
            "deps": deps[:]
        })
        return value
    
    memo_state = comp._hook_memos[idx]
    prev_deps = memo_state["deps"]
    
    # Check if deps changed
    should_recompute = False
    if len(deps) != len(prev_deps):
        should_recompute = True
    else:
        for old, new in zip(prev_deps, deps):
            if old != new:
                should_recompute = True
                break
    
    if should_recompute:
        value = fn()
        memo_state["value"] = value
        memo_state["deps"] = deps[:]
        return value
    
    return memo_state["value"]


class Ref:
    """A mutable reference container."""
    def __init__(self, initial: Any = None):
        self.current = initial


def use_ref(initial: Any = None) -> Ref:
    """
    Create a mutable reference that persists across renders.
    
    Unlike signals, changing ref.current does NOT trigger re-render.
    Useful for storing DOM references, timers, or previous values.
    
    Args:
        initial: Initial value for the ref
    
    Returns:
        Ref object with .current property
    
    Example:
        def MyComponent():
            render_count = use_ref(0)
            render_count.current += 1
            
            timer_id = use_ref(None)
            
            def start_timer():
                timer_id.current = set_interval(tick, 1000)
            
            def stop_timer():
                if timer_id.current:
                    clear_interval(timer_id.current)
    """
    comp = current_component()
    
    # Hook storage is pre-initialized in ComponentInstance.__init__
    idx = comp._hook_ref_index
    comp._hook_ref_index += 1
    
    if idx >= len(comp._hook_refs):
        ref = Ref(initial)
        comp._hook_refs.append(ref)
        return ref
    
    return comp._hook_refs[idx]


def use_callback(fn: Callable, deps: List[Any]) -> Callable:
    """
    Memoize a callback function.
    
    Returns the same function reference unless dependencies change.
    Useful for preventing unnecessary re-renders of child components.
    
    Args:
        fn: The callback function
        deps: List of dependencies
    
    Returns:
        Memoized callback
    
    Example:
        def Parent():
            count = signal(0)
            
            # Same function reference unless count changes
            handle_click = use_callback(
                lambda: count(count() + 1),
                [count()]
            )
            
            return Child(on_click=handle_click)
    """
    return use_memo(lambda: fn, deps)

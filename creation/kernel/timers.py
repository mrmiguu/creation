"""
Browser-compatible Timer API for Creation.

Provides set_timeout, set_interval, and their clear functions.
Uses js.setTimeout/setInterval under the hood with proper proxy handling.
"""

from typing import Callable, Any
from pyodide.ffi import create_proxy


# Timer tracking
_timers = {}
_next_timer_id = 1


def set_timeout(callback: Callable[[], Any], delay_ms: int) -> int:
    """
    Schedule a callback to run once after delay_ms milliseconds.
    Returns a timer_id that can be used with clear_timeout.
    
    Example:
        timer_id = set_timeout(lambda: print("Hello"), 1000)
    """
    global _next_timer_id
    from js import setTimeout
    
    timer_id = _next_timer_id
    _next_timer_id += 1
    
    # Store reference before creating proxy
    _timers[timer_id] = {
        "proxy": None,
        "js_id": None,
        "type": "timeout"
    }
    
    def wrapped():
        try:
            callback()
        finally:
            # Cleanup after execution
            if timer_id in _timers:
                if _timers[timer_id]["proxy"]:
                    _timers[timer_id]["proxy"].destroy()
                del _timers[timer_id]
    
    # Create single proxy for the wrapped function
    wrapped_proxy = create_proxy(wrapped)
    _timers[timer_id]["proxy"] = wrapped_proxy
    
    js_id = setTimeout(wrapped_proxy, delay_ms)
    _timers[timer_id]["js_id"] = js_id
    
    return timer_id


def set_interval(callback: Callable[[], Any], interval_ms: int) -> int:
    """
    Schedule a callback to run repeatedly every interval_ms milliseconds.
    Returns a timer_id that can be used with clear_interval.
    
    Example:
        timer_id = set_interval(lambda: update_data(), 1500)
        # Later:
        clear_interval(timer_id)
    """
    global _next_timer_id
    from js import setInterval
    
    timer_id = _next_timer_id
    _next_timer_id += 1
    
    # Create proxy to prevent garbage collection
    proxy = create_proxy(callback)
    
    _timers[timer_id] = {
        "proxy": proxy,
        "js_id": None,
        "type": "interval"
    }
    
    js_id = setInterval(proxy, interval_ms)
    _timers[timer_id]["js_id"] = js_id
    
    return timer_id


def clear_timeout(timer_id: int) -> bool:
    """
    Cancel a timeout created by set_timeout.
    Returns True if cancelled, False if timer_id not found.
    """
    from js import clearTimeout
    
    if timer_id not in _timers:
        return False
    
    timer = _timers[timer_id]
    if timer["type"] != "timeout":
        return False
    
    if timer["js_id"] is not None:
        clearTimeout(timer["js_id"])
    
    timer["proxy"].destroy()
    del _timers[timer_id]
    return True


def clear_interval(timer_id: int) -> bool:
    """
    Cancel an interval created by set_interval.
    Returns True if cancelled, False if timer_id not found.
    """
    from js import clearInterval
    
    if timer_id not in _timers:
        return False
    
    timer = _timers[timer_id]
    if timer["type"] != "interval":
        return False
    
    if timer["js_id"] is not None:
        clearInterval(timer["js_id"])
    
    timer["proxy"].destroy()
    del _timers[timer_id]
    return True


def clear_all_timers():
    """Clear all active timers. Useful for cleanup."""
    from js import clearTimeout, clearInterval
    
    for timer_id, timer in list(_timers.items()):
        try:
            if timer["type"] == "timeout":
                clearTimeout(timer["js_id"])
            else:
                clearInterval(timer["js_id"])
            timer["proxy"].destroy()
        except Exception:
            pass
    
    _timers.clear()

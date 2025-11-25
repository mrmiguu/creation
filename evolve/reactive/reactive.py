"""
Reactive system for Evolve (signals, effects, computed).
Push-based dependency tracking similar to Solid.js.

"""

from collections.abc import Callable
import itertools
import traceback

# Global "currently running effect"  (support nested effects)
_current_effect_stack: list[Callable] = []

# unique id generator for debugging/tracking tools
_id_counter = itertools.count(1)


class Signal:
    """
    A reactive value.
    Read with s() or s.value, update with s.set(new)
    Subscriptions: subscribers are callables invoked with new_value
    
    """
    
    __slots__ = ("_id", "_value", "_subscribers")
    def __init__(self, intial:any):
        self._id:int = next(_id_counter)
        self._value:any = intial
        self._subscribers:dict[int,Callable[[any],None]] = {}
    
    # reading the signal registers dependency if inside an effect
    def __call__(self, *args, **kwds)->any:
        self._track_dependency()
        return self._value
    
    @property
    def value(self)->any:
        return self.__call__()
    
    def set(self,new:any)->None:
        # short circuit if equal (fast path) using python equality
        if new == self._value:
            return
        self._value=new
        # notify subscribers
        subs=list(self._subscribers.values())
        
        for fn in subs:
            try:
                fn(new)
            except Exception:
                # Dont break others, just log the trace
                traceback.print_exc()
                
    def _track_dependency(self):
        if not _current_effect_stack:
            
            return
        
        # Register top effect in this signal's subsccribers via effect id
        # pick latest effect
        eff = _current_effect_stack[-1]
        # effect function can carry .__effect_id attribute
        eff_id = getattr(eff,"__effect_id",None)
        if eff_id is None:
            # not an effect registered function; ignore
            return
        
        # If already subscribed, skip
        if eff_id in self._subscribers:
            return
        
        # create a wrapper subscriber that reruns effect
        def _subscriber(_new):
            try:
                eff()
            except Exception:
                traceback.print_exc()
                
        # attch it to eff_id so that we can remove it later if needed
        self._subscribers[eff_id] = _subscriber
        
    
    def subscribe(self, fn:Callable[[any],None])->int:
        """
        
        subscribe directly to changes. Returns subscription id
        """
        sid = next(_id_counter)    
        self._subscribers[sid] = fn
        return sid 
    
    def unsubscribe(self,sid:int)->None:
        self._subscribers.pop(sid,None)
        
    def __repr__(self)->str:
        return f"<Signal id={self._id} value={self._value!r} subs={len(self._subscribers)}>"
        
def signal(initial: any) -> Signal:
    """Factory for signals."""
    return Signal(initial)


# EFFECTS
    
def effect(fn:Callable[[],any])->Callable[[],None]:
    """
    Registers an effect. Effect is run immediately and then on each dependency change.
    Returns a runner function, so it can be stored or called manually.
    
    """
    if not Callable(fn):
        raise TypeError("effect expects callable")
    # Give effect an ID
    
    eff_id = next(_id_counter)
    
    
    def runner():
        
        try:
            # mark the runner with __eff_id so signals can register
            runner.__effect_id = eff_id
            _current_effect_stack.append(runner)
            
            # RUN the effect
            res = fn()
            return res
        finally:
            _current_effect_stack.pop()
            # runner.__effect_id remains for subscription identity.
            
    # Attach id for removal/inspection
    runner.__effect_id = eff_id
    # Run immediately to collect depedencies
    runner()
    return runner


    
    
    
    
        
        
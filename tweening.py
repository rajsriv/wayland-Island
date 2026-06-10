import time
import math
from gi.repository import GLib

class Easing:
    @staticmethod
    def out_expo(t):
        return 1.0 if t == 1.0 else 1.0 - math.pow(2.0, -10.0 * t)

    @staticmethod
    def in_out_sine(t):
        return -0.5 * (math.cos(math.pi * t) - 1.0)
        
    @staticmethod
    def out_quad(t):
        return t * (2 - t)

class Tween:
    def __init__(self, start_val, end_val, duration_ms, easing_func, on_update, on_complete=None, delay_ms=0):
        self.start_val = start_val
        self.end_val = end_val
        self.duration_sec = duration_ms / 1000.0
        self.delay_sec = delay_ms / 1000.0
        self.easing_func = easing_func
        self.on_update = on_update
        self.on_complete = on_complete
        
        self.start_time = 0
        self._timeout_id = None
        
    def start(self):
        self.stop()
        self.start_time = time.time() + self.delay_sec
        self._timeout_id = GLib.timeout_add(16, self._tick) # ~60fps
        
    def stop(self):
        if self._timeout_id is not None:
            GLib.source_remove(self._timeout_id)
            self._timeout_id = None

    def set_end_value(self, val):
        self.end_val = val
        self.start()

    def _tick(self):
        now = time.time()
        if now < self.start_time:
            return True # waiting for delay
            
        elapsed = now - self.start_time
        if self.duration_sec == 0:
            progress = 1.0
        else:
            progress = min(1.0, elapsed / self.duration_sec)
            
        eased_progress = self.easing_func(progress)
        
        # Interpolate
        current_val = self.start_val + (self.end_val - self.start_val) * eased_progress
        self.on_update(current_val)
        
        if progress >= 1.0:
            self._timeout_id = None
            if self.on_complete:
                self.on_complete()
            return False # Stop timer
            
        return True # Continue timer

class ParallelAnimationGroup:
    def __init__(self):
        self.tweens = []
        
    def add_animation(self, tween):
        self.tweens.append(tween)
        
    def start(self):
        for tween in self.tweens:
            tween.start()
            
    def stop(self):
        for tween in self.tweens:
            tween.stop()

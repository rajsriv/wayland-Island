import os
import glob
import time
import threading
from gi.repository import GLib

class KeyLockMonitor(threading.Thread):
    def __init__(self, callback, parent=None):
        super().__init__(daemon=True)
        self.callback = callback
        self._is_running = True
        
        self.caps_path = self._find_led_path("capslock")
        self.num_path = self._find_led_path("numlock")
        
        self.last_caps = self.get_caps_lock()
        self.last_num = self.get_num_lock()

    def _find_led_path(self, led_type):
        paths = glob.glob(f"/sys/class/leds/input*::{led_type}/brightness")
        return paths[0] if paths else None

    def _read_led(self, path):
        if not path:
            return False
        try:
            with open(path, 'r') as f:
                return f.read().strip() == '1'
        except:
            return False

    def get_caps_lock(self):
        return self._read_led(self.caps_path)

    def get_num_lock(self):
        return self._read_led(self.num_path)

    def run(self):
        while self._is_running:
            caps = self.get_caps_lock()
            if caps != self.last_caps:
                self.last_caps = caps
                if self.callback: GLib.idle_add(self.callback, "Caps Lock", caps)

            num = self.get_num_lock()
            if num != self.last_num:
                self.last_num = num
                if self.callback: GLib.idle_add(self.callback, "Num Lock", num)

            time.sleep(0.05)

    def stop(self):
        self._is_running = False
        if self.is_alive():
            self.join()

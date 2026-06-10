import psutil
import threading
import time
from gi.repository import GLib

class SystemMonitor(threading.Thread):
    def __init__(self, callback, interval_sec=1.5, parent=None):
        super().__init__(daemon=True)
        self.callback = callback
        self.interval_sec = interval_sec
        self._is_running = True

    def run(self):
        while self._is_running:
            try:
                # RAM
                vmem = psutil.virtual_memory()
                ram_total = vmem.total / (1024**3)
                ram_used = (vmem.total - vmem.available) / (1024**3)
                ram_free = vmem.available / (1024**3)

                # Swap
                swap = psutil.swap_memory()
                swap_total = swap.total / (1024**3)
                swap_used = swap.used / (1024**3)
                swap_free = swap.free / (1024**3)

                # CPU
                cpu_load = psutil.cpu_percent(interval=0.5)

                stats = {
                    "ram_used": f"{ram_used:.1f} GB",
                    "ram_free": f"{ram_free:.1f} GB",
                    "ram_total": f"{ram_total:.1f} GB",
                    "swap_used": f"{swap_used:.1f} GB",
                    "swap_free": f"{swap_free:.1f} GB",
                    "swap_total": f"{swap_total:.1f} GB",
                    "cpu_load": f"{cpu_load:.0f}%"
                }

                if self.callback:
                    GLib.idle_add(self.callback, stats)
                    
            except Exception as e:
                print("SystemMonitor Error:", e)

            for _ in range(int((self.interval_sec - 0.5) * 10)):
                if not self._is_running:
                    break
                time.sleep(0.1)

    def stop(self):
        self._is_running = False

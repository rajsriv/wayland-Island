import os
import time
import threading
from gi.repository import GLib

class BatteryMonitor(threading.Thread):
    def __init__(self, callback, interval_sec=2.0, parent=None):
        super().__init__(daemon=True)
        self.callback = callback
        self.interval_sec = interval_sec
        self._is_running = True
        
        # Auto-detect battery path (BAT0 or BAT1 usually)
        self.bat_path = None
        base_path = "/sys/class/power_supply"
        if os.path.exists(base_path):
            for dev in os.listdir(base_path):
                if dev.startswith("BAT"):
                    self.bat_path = os.path.join(base_path, dev)
                    break

        self.last_status = None
        self.last_capacity = -1

    def run(self):
        if not self.bat_path:
            print("BatteryMonitor: No battery found in /sys/class/power_supply")
            return

        while self._is_running:
            try:
                with open(os.path.join(self.bat_path, "status"), "r") as f:
                    status = f.read().strip()
                with open(os.path.join(self.bat_path, "capacity"), "r") as f:
                    capacity = int(f.read().strip())
                    
                time_str = ""
                try:
                    with open(os.path.join(self.bat_path, "charge_now"), "r") as f:
                        charge_now = int(f.read().strip())
                    with open(os.path.join(self.bat_path, "charge_full"), "r") as f:
                        charge_full = int(f.read().strip())
                    with open(os.path.join(self.bat_path, "current_now"), "r") as f:
                        current_now = int(f.read().strip())
                        
                    if current_now > 0:
                        if status == "Charging":
                            hours = (charge_full - charge_now) / current_now
                        else:
                            hours = charge_now / current_now
                        mins = int(hours * 60)
                        if mins > 0:
                            if mins > 60:
                                time_str = f"~{mins//60}h {mins%60}m"
                            else:
                                time_str = f"~{mins}m"
                except Exception:
                    pass
                
                if self.last_status is None:
                    # Initial state fetch
                    if self.callback:
                        GLib.idle_add(self.callback, status, capacity, time_str, True)
                elif status != self.last_status:
                    # Battery status changed (e.g. plugged in or unplugged)
                    if self.callback:
                        GLib.idle_add(self.callback, status, capacity, time_str, False)
                else:
                    # Periodic silent update for capacity and time
                    if self.callback:
                        GLib.idle_add(self.callback, status, capacity, time_str, True)
                
                self.last_status = status
                self.last_capacity = capacity
            except Exception as e:
                pass
                
            # Sleep in short intervals to allow quick exit on stop()
            for _ in range(int(self.interval_sec * 10)):
                if not self._is_running:
                    break
                time.sleep(0.1)

    def stop(self):
        self._is_running = False

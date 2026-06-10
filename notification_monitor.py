import asyncio
import threading
from gi.repository import GLib
from dbus_next.aio import MessageBus
from dbus_next.message import Message, MessageType

class NotificationMonitor(threading.Thread):
    def __init__(self, callback, parent=None):
        super().__init__(daemon=True)
        self.callback = callback
        self._is_running = True
        self.loop = None
        self.bus = None

    def run(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        try:
            self.loop.run_until_complete(self.monitor_notifications())
        except Exception as e:
            print("NotificationMonitor setup error:", e)

    async def monitor_notifications(self):
        try:
            self.bus = await MessageBus().connect()
            
            # Monitor method calls to Notify
            rule = "type='method_call',interface='org.freedesktop.Notifications',member='Notify'"
            await self.bus.call(
                Message(destination='org.freedesktop.DBus',
                        path='/org/freedesktop/DBus',
                        interface='org.freedesktop.DBus',
                        member='AddMatch',
                        signature='s',
                        body=[rule])
            )

            def message_handler(msg):
                if msg.message_type == MessageType.METHOD_CALL and msg.member == 'Notify':
                    if len(msg.body) >= 5:
                        app_name = str(msg.body[0])
                        summary = str(msg.body[3])
                        body = str(msg.body[4])
                        # Filter out our own notifications to prevent infinite loops
                        if app_name != "DynamicIsland":
                            if self.callback: GLib.idle_add(self.callback, app_name, summary, body)

            self.bus.add_message_handler(message_handler)

            while self._is_running:
                await asyncio.sleep(0.5)
        except Exception as e:
            print(f"Notification setup error: {e}")

    def stop(self):
        self._is_running = False
        if self.loop:
            self.loop.stop()
        if self.is_alive():
            self.join()

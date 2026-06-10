import asyncio
from media_monitor import MediaMonitor

class TestMonitor(MediaMonitor):
    def __init__(self):
        super().__init__(None, None, None)

    async def monitor_media(self):
        try:
            await super().monitor_media()
        except Exception as e:
            import traceback
            traceback.print_exc()

m = TestMonitor()
m.run()

import asyncio
import datetime
import re
import requests
import io
import time
from urllib.parse import unquote
import threading
from gi.repository import GLib
from PIL import Image, ImageFilter, ImageOps
from dbus_next.aio import MessageBus
from dbus_next.errors import DBusError

class MediaMonitor(threading.Thread):
    def __init__(self, media_callback, lyrics_callback, progress_callback=None, parent=None):
        super().__init__(daemon=True)
        self.media_callback = media_callback
        self.lyrics_callback = lyrics_callback
        self.progress_callback = progress_callback
        self._is_running = True
        self.loop = None
        self.bus = None
        
        self.lyrics = []
        self.last_lyric_sent = ""
        self.current_title = ""
        self.current_artist = ""
        self.last_state = "Idle"
        self.last_album_art = ""
        self.current_accent = "#000000"
        
        self.active_player_name = None
        self.last_update_time = time.time()
        self.last_position_us = 0
        self.current_length_us = 0
        self.current_trackid = ""
        self.is_playing = False

    def run(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        try:
            self.loop.run_until_complete(self.monitor_media())
        except Exception as e:
            print("MediaMonitor error:", e)

    async def monitor_media(self):
        try:
            self.bus = await MessageBus().connect()
        except Exception as e:
            print(f"Failed to connect to DBus: {e}")
            return

        while self._is_running:
            await self.update_media_info()
            await self.check_lyric_sync()
            await asyncio.sleep(0.5)

    async def get_active_player(self):
        try:
            reply = await self.bus.call(
                import_message('org.freedesktop.DBus', '/org/freedesktop/DBus', 'org.freedesktop.DBus', 'ListNames')
            )
            # We must import Message here to use it inline, or use another way to list names
            pass
        except:
            pass
            
        # Simplified: Use standard introspection or dbus-next proxy to get players
        # The easiest way without proxy generation is to ask DBus for names
        pass

    # A simpler way to list names in dbus_next
    async def list_players(self):
        from dbus_next.message import Message
        reply = await self.bus.call(
            Message(destination='org.freedesktop.DBus',
                    path='/org/freedesktop/DBus',
                    interface='org.freedesktop.DBus',
                    member='ListNames')
        )
        if reply and reply.body:
            names = reply.body[0]
            return [n for n in names if n.startswith('org.mpris.MediaPlayer2.')]
        return []

    async def get_player_property(self, player_name, prop_name):
        from dbus_next.message import Message
        reply = await self.bus.call(
            Message(destination=player_name,
                    path='/org/mpris/MediaPlayer2',
                    interface='org.freedesktop.DBus.Properties',
                    member='Get',
                    signature='ss',
                    body=['org.mpris.MediaPlayer2.Player', prop_name])
        )
        if reply and reply.body:
            val = reply.body[0]
            return val.value if hasattr(val, 'value') else val
        return None

    async def update_media_info(self):
        players = await self.list_players()
        if not players:
            self._set_idle()
            return

        best_player = None
        best_status = "Stopped"
        
        for p in players:
            status = await self.get_player_property(p, "PlaybackStatus")
            if status == "Playing":
                best_player = p
                best_status = "Playing"
                break
            elif status == "Paused":
                if not best_player:
                    best_player = p
                    best_status = "Paused"

        if not best_player or best_status == "Stopped":
            self._set_idle()
            return

        self.active_player_name = best_player
        self.is_playing = (best_status == "Playing")
        
        metadata = await self.get_player_property(best_player, "Metadata")
        if not metadata:
            self._set_idle()
            return
            
        title = metadata.get("xesam:title", "Unknown Title")
        if isinstance(title, getattr(getattr(metadata.get("xesam:title", None), '__class__', type), 'value', type)):
            # Handle DBus Variant
            title = title if isinstance(title, str) else str(title)
            
        artists = metadata.get("xesam:artist", [])
        artist = artists[0] if artists and isinstance(artists, list) else (artists if isinstance(artists, str) else "")
        
        art_url = metadata.get("mpris:artUrl", "")
        trackid = metadata.get("mpris:trackid", "")
        album = metadata.get("xesam:album", "")
        
        # Unpack Variant types from dbus_next if needed
        if hasattr(title, 'value'): title = title.value
        if hasattr(artist, 'value'): 
            artist = artist.value
            if isinstance(artist, list) and artist: artist = artist[0]
        if hasattr(art_url, 'value'): art_url = art_url.value
        if hasattr(trackid, 'value'): trackid = trackid.value
        if hasattr(album, 'value'): album = album.value

        title = str(title)
        artist = str(artist)
        album = str(album)
        art_url = str(art_url)
        self.current_trackid = str(trackid)

        # Try to get position for lyrics sync
        position = await self.get_player_property(best_player, "Position")
        if position is not None:
            if hasattr(position, 'value'): position = position.value
            self.last_position_us = int(position)
            self.last_update_time = time.time()
            
        # Try to get total length
        length = metadata.get("mpris:length", 0)
        if hasattr(length, 'value'): length = length.value
        self.current_length_us = int(length) if length else 0

        accent_color = self.current_accent

        # Extract accent color if art changed
        if art_url and art_url != self.last_album_art:
            self.last_album_art = art_url
            accent_color = await self.extract_accent_color(art_url)
            self.current_accent = accent_color

        if (best_status != self.last_state or title != self.current_title or artist != self.current_artist):
            self.current_title = title
            self.current_artist = artist
            self.current_album = album
            self.last_state = best_status
            self.lyrics = []
            self.last_lyric_sent = ""
            if self.lyrics_callback: GLib.idle_add(self.lyrics_callback, "")
            if title and title != "Unknown Title":
                asyncio.create_task(self.fetch_lyrics(artist, title))
            if self.media_callback: GLib.idle_add(self.media_callback, best_status, title, artist, accent_color, art_url, album)

        if self.is_playing and self.progress_callback:
            GLib.idle_add(self.progress_callback, self.last_position_us, self.current_length_us)

    def _set_idle(self):
        if self.last_state != "Idle":
            self.current_title = ""
            self.current_artist = ""
            self.last_state = "Idle"
            self.last_album_art = ""
            self.lyrics = []
            self.active_player_name = None
            self.current_trackid = ""
            self.is_playing = False
            if self.media_callback: GLib.idle_add(self.media_callback, "Idle", "", "", "#000000", "", "")

    def seek(self, target_us):
        if self.active_player_name and self.current_trackid and self.loop:
            asyncio.run_coroutine_threadsafe(self._do_seek(target_us), self.loop)
            
    async def _do_seek(self, target_us):
        try:
            from dbus_next.message import Message
            await self.bus.call(
                Message(destination=self.active_player_name,
                        path='/org/mpris/MediaPlayer2',
                        interface='org.mpris.MediaPlayer2.Player',
                        member='SetPosition',
                        signature='ox',
                        body=[self.current_trackid, int(target_us)])
            )
        except Exception as e:
            print("Seek error:", e)

    async def extract_accent_color(self, art_url):
        def do_extract():
            try:
                if art_url.startswith('file://'):
                    path = unquote(art_url[7:])
                    image = Image.open(path)
                elif art_url.startswith('http'):
                    resp = requests.get(art_url, timeout=5)
                    image = Image.open(io.BytesIO(resp.content))
                else:
                    return "#000000"
                    
                try:
                    rgb_img = image.convert("RGB")
                    rgb_img.resize((110, 110)).save("/tmp/dynamic_island_cover.png")
                    
                    bg_img = ImageOps.fit(rgb_img, (400, 140))
                    bg_img = bg_img.filter(ImageFilter.GaussianBlur(radius=60))
                    bg_img.save("/tmp/dynamic_island_bg.png")
                except: pass

                image = image.resize((32, 32))
                colors = image.getcolors(32 * 32)
                
                def get_saturation(rgb):
                    r, g, b = rgb[:3]
                    mx = max(r, g, b)
                    mn = min(r, g, b)
                    return (mx - mn) / mx if mx > 0 else 0

                def get_lightness(rgb):
                    r, g, b = rgb[:3]
                    return (max(r, g, b) + min(r, g, b)) / 2

                # Quantize the image to group gradient pixels into a single dominant bucket
                q_img = image.quantize(colors=4).convert("RGB")
                q_colors = q_img.getcolors(32 * 32)
                q_filtered = [c for c in q_colors if 50 < sum(c[1][:3]) < 700]
                
                if q_filtered:
                    dominant = max(q_filtered, key=lambda x: x[0])[1]
                else:
                    dominant = max(q_colors, key=lambda x: x[0])[1]
                accent = '#{:02x}{:02x}{:02x}'.format(dominant[0], dominant[1], dominant[2])
                
                # Highlight is the most saturated, vibrant color from the raw image
                filtered = [c for c in colors if 50 < sum(c[1][:3]) < 700]
                if filtered:
                    highlight = max(filtered, key=lambda x: get_saturation(x[1]) * x[0])[1]
                    light_accent = '#{:02x}{:02x}{:02x}'.format(highlight[0], highlight[1], highlight[2])
                else:
                    light_accent = accent
                    
                return f"{accent}|{light_accent}"

            except Exception as e:
                print(f"Color extract error: {e}")
                return "#000000"

        return await self.loop.run_in_executor(None, do_extract)

    async def check_lyric_sync(self):
        if not self.active_player_name or not self.lyrics or not self.is_playing:
            return
        
        try:
            now = time.time()
            delta_s = now - self.last_update_time
            # Position is in microseconds
            pos_sec = (self.last_position_us / 1_000_000.0) + delta_s + 1.0
            
            current_line = ""
            for ts, text in self.lyrics:
                if pos_sec >= ts:
                    current_line = text
                else:
                    break
            
            if current_line != self.last_lyric_sent:
                self.last_lyric_sent = current_line
                if self.lyrics_callback: GLib.idle_add(self.lyrics_callback, current_line)
        except Exception as e:
            print(f"Lyric sync error: {e}")

    async def fetch_lyrics(self, artist, title):
        if not artist or not title:
            return
            
        def do_fetch():
            try:
                url = "https://lrclib.net/api/get"
                params = {"artist_name": artist, "track_name": title}
                resp = requests.get(url, params=params, timeout=5)
                if resp.status_code == 200:
                    data = resp.json()
                    lrc = data.get("syncedLyrics")
                    if lrc:
                        return self.parse_lrc(lrc)
                    elif data.get("plainLyrics"):
                        return [(0, data.get("plainLyrics").split('\n')[0])]
                return []
            except Exception as e:
                print(f"Lyric fetch error: {e}")
                return []

        lyrics = await self.loop.run_in_executor(None, do_fetch)
        if lyrics:
            self.lyrics = lyrics
            await self.check_lyric_sync()

    def parse_lrc(self, lrc_text):
        lyrics = []
        for line in lrc_text.splitlines():
            match = re.search(r'\[(\d+):(\d+(?:\.\d+)?)\](.*)', line)
            if match:
                m, s, text = match.groups()
                timestamp = int(m) * 60 + float(s)
                lyrics.append((timestamp, text.strip()))
        return sorted(lyrics, key=lambda x: x[0])

    def toggle_play_pause(self):
        if self.active_player_name and self.loop:
            asyncio.run_coroutine_threadsafe(self._do_player_action("PlayPause"), self.loop)

    def next_track(self):
        if self.active_player_name and self.loop:
            asyncio.run_coroutine_threadsafe(self._do_player_action("Next"), self.loop)

    def prev_track(self):
        if self.active_player_name and self.loop:
            asyncio.run_coroutine_threadsafe(self._do_player_action("Previous"), self.loop)

    async def _do_player_action(self, action):
        try:
            from dbus_next.message import Message
            await self.bus.call(
                Message(destination=self.active_player_name,
                        path='/org/mpris/MediaPlayer2',
                        interface='org.mpris.MediaPlayer2.Player',
                        member=action)
            )
        except Exception as e:
            print(f"Player action {action} error: {e}")

    def stop(self):
        self._is_running = False
        if self.loop:
            self.loop.stop()
        if self.is_alive():
            self.join()

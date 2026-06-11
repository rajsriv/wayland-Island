import sys
import math
import cairo
import os
import json
import calendar
from datetime import datetime
import gi
gi.require_version('Gtk', '3.0')
gi.require_version('Pango', '1.0')
from gi.repository import Gtk, Gdk, GLib, Pango, GdkPixbuf

try:
    gi.require_version('GtkLayerShell', '0.1')
    from gi.repository import GtkLayerShell
    HAS_LAYER_SHELL = True
except ValueError:
    HAS_LAYER_SHELL = False

from tweening import Tween, Easing, ParallelAnimationGroup
from media_monitor import MediaMonitor
from notification_monitor import NotificationMonitor
from weather_monitor import WeatherMonitor
from app_styles import get_stylesheet
from event_monitor import KeyLockMonitor
from battery_monitor import BatteryMonitor
from system_monitor import SystemMonitor

class DynamicIsland(Gtk.Window):
    IDLE_W, IDLE_H = 180, 40
    COMPACT_W, COMPACT_H = 160, 40
    MEDIA_W, MEDIA_H = 400, 140
    NOTIFY_W, NOTIFY_H = 240, 44
    SYSTEM_W, SYSTEM_H = 305, 120
    BATTERY_W, BATTERY_H = 320, 44
    CALENDAR_W, CALENDAR_H = 400, 190
    SETTINGS_W, SETTINGS_H = 220, 390
    # Vertical pill for left/right sidebar: swap IDLE dims
    SIDEBAR_IDLE_W, SIDEBAR_IDLE_H = 40, 180
    # Square media card for left/right sidebar
    SIDEBAR_MEDIA_W, SIDEBAR_MEDIA_H = 200, 200

    def __init__(self):
        super().__init__(type=Gtk.WindowType.TOPLEVEL)
        
        self.config_path = os.path.expanduser("~/.config/dynamic_island_config.json")
        self.app_config = {
            "theme": "Frosted Black",
            "time_format": "24h",
            "position": "top"
        }
        self.load_config()
        
        if self.app_config.get("position", "top") in ("left", "right"):
            self.island_w = self.SIDEBAR_IDLE_W
            self.island_h = self.SIDEBAR_IDLE_H
            self.border_radius = self.SIDEBAR_IDLE_W / 2.0
        else:
            self.island_w = self.IDLE_W
            self.island_h = self.IDLE_H
            self.border_radius = self.IDLE_H / 2.0
            
        self.current_state = "Idle"
        self.current_accent = "#000000"
        self.target_accent = "#000000"
        self.target_light_accent = "#000000"
        
        self.old_cover_pixbuf = None
        self.cover_pixbuf = None
        self.old_bg_pixbuf = None
        self.bg_pixbuf = None
        self.art_alpha = 1.0
        
        self.video_cap = None
        self.video_timer = None
        self.current_video_pixbuf = None
        try:
            import cv2
            self.video_cap = cv2.VideoCapture("waguri.mp4")
            if not self.video_cap.isOpened():
                self.video_cap = None
        except Exception as e:
            print("Video init error:", e)
        self.bg_darkness = 0.7
        self.bg_opacity = 0.0
        
        self.current_progress = 0
        self.visual_progress = 0
        self.current_length = 0
        self.mesh_phase = 0.0
        self.wave_phase = 0.0
        GLib.timeout_add(33, self.on_mesh_tick)
        GLib.timeout_add_seconds(1, self.update_clock)
        
        # Setup Layer Shell
        if HAS_LAYER_SHELL and GtkLayerShell.is_supported():
            GtkLayerShell.init_for_window(self)
            GtkLayerShell.set_namespace(self, "dynamic-island")
            GtkLayerShell.set_layer(self, GtkLayerShell.Layer.TOP)
            GtkLayerShell.set_anchor(self, GtkLayerShell.Edge.TOP, True)
            GtkLayerShell.set_anchor(self, GtkLayerShell.Edge.BOTTOM, False)
            GtkLayerShell.set_anchor(self, GtkLayerShell.Edge.LEFT, False)
            GtkLayerShell.set_anchor(self, GtkLayerShell.Edge.RIGHT, False)
            GtkLayerShell.set_margin(self, GtkLayerShell.Edge.TOP, 10)
            GtkLayerShell.set_margin(self, GtkLayerShell.Edge.BOTTOM, 10)
            GtkLayerShell.set_margin(self, GtkLayerShell.Edge.LEFT, 10)
            GtkLayerShell.set_margin(self, GtkLayerShell.Edge.RIGHT, 10)
        
        self.set_visual(self.get_screen().get_rgba_visual())
        self.set_app_paintable(True)
        self.set_name("IslandWidget")
        self.add_events(Gdk.EventMask.SCROLL_MASK | Gdk.EventMask.ENTER_NOTIFY_MASK | Gdk.EventMask.LEAVE_NOTIFY_MASK | Gdk.EventMask.BUTTON_PRESS_MASK)
        self.connect("scroll-event", self.on_scroll)
        self.connect("enter-notify-event", self.on_hover_enter)
        self.connect("leave-notify-event", self.on_hover_leave)
        self.connect("button-press-event", self.on_button_press)
        
        self.is_hovered = False
        self.collapse_timer = None
        
        self.last_media_title = ""
        self.last_media_artist = ""
        
        self.apply_position()
        
        self.overlay = Gtk.Overlay()
        self.add(self.overlay)
        
        # Drawing Area for background
        self.drawing_area = Gtk.DrawingArea()
        self.drawing_area.set_size_request(self.IDLE_W, self.IDLE_H)
        self.drawing_area.connect("draw", self.on_draw)
        self.overlay.add(self.drawing_area)
        
        self.battery_status = "Unknown"
        self.battery_percent = 0
        self.battery_time = ""
        
        # Content box container
        self.content_opacity = 1.0
        self.content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.content_box.set_halign(Gtk.Align.CENTER)
        self.content_box.set_valign(Gtk.Align.START)
        self.content_box.set_margin_top(10)
        self.content_box.set_size_request(self.IDLE_W - 30, -1)
        
        # Stack for transitions
        self.stack = Gtk.Stack()
        self.stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        self.stack.set_transition_duration(300)
        self.stack.set_hhomogeneous(False)
        self.stack.set_vhomogeneous(False)
        self.content_box.pack_start(self.stack, True, True, 0)
        
        # 1. Idle/Notify Widget
        self.header_widget = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        self.header_widget.set_halign(Gtk.Align.CENTER)
        self.status_label = Gtk.Label(label="")
        self.status_label.set_name("TitleLabel")
        self.status_label.set_ellipsize(Pango.EllipsizeMode.END)
        self.status_label.set_max_width_chars(25)
        self.header_widget.pack_start(self.status_label, False, False, 0)
        self.stack.add_named(self.header_widget, "header")
        
        # 2. Premium Media Widget (2 Column Layout)
        self.media_widget = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=15)
        self.media_widget.set_halign(Gtk.Align.FILL)
        self.media_widget.set_valign(Gtk.Align.CENTER)
        
        # Col 1: Cover Art
        self.cover_art = Gtk.DrawingArea()
        self.cover_art.set_size_request(110, 110)
        self.cover_art.set_valign(Gtk.Align.CENTER)
        self.cover_art.connect("draw", self.on_draw_cover)
        
        # Col 2: Grid Layout for Texts, Play Button, and Seekbar
        self.media_grid = Gtk.Grid()
        self.media_grid.set_column_spacing(10)
        self.media_grid.set_row_spacing(2)
        self.media_grid.set_valign(Gtk.Align.FILL) # Stretch to 110px to match cover
        
        def create_crossfade_stack(name):
            stack = Gtk.Stack()
            stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
            stack.set_transition_duration(300)
            stack.set_hexpand(True)
            stack.set_valign(Gtk.Align.START)
            
            l1 = Gtk.Label(label="", xalign=0)
            l1.set_name(name)
            l1.set_ellipsize(Pango.EllipsizeMode.END)
            l1.set_max_width_chars(1)
            
            l2 = Gtk.Label(label="", xalign=0)
            l2.set_name(name)
            l2.set_ellipsize(Pango.EllipsizeMode.END)
            l2.set_max_width_chars(1)
            
            stack.add_named(l1, "1")
            stack.add_named(l2, "2")
            stack.set_visible_child_name("1")
            return stack, l1, l2
            
        self.title_stack, self.title_l1, self.title_l2 = create_crossfade_stack("TitleLabel")
        self.artist_stack, self.artist_l1, self.artist_l2 = create_crossfade_stack("SubtitleLabel")
        
        # Spacer to push seekbar to bottom
        self.media_spacer = Gtk.Box()
        self.media_spacer.set_vexpand(True)
        
        self.media_time_label = Gtk.Label(label="0:00 / 0:00", xalign=0.0)
        self.media_time_label.set_name("PerfLabel")
        self.media_time_label.set_margin_left(6)
        self.media_time_label.set_hexpand(True)
        self.media_time_label.set_valign(Gtk.Align.END)
        
        self.btn_play = Gtk.Button(label="▶")
        self.btn_play.set_name("ControlBall")
        self.btn_play.set_size_request(48, 48)
        self.btn_play.set_valign(Gtk.Align.CENTER)
        self.btn_play.set_halign(Gtk.Align.END)
        
        # Seekbar and Nav
        self.media_bottom = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        self.btn_prev = Gtk.Button(label="⏮")
        self.btn_next = Gtk.Button(label="⏭")
        for btn in [self.btn_prev, self.btn_next]: btn.set_name("NavButton")
        
        self.seekbar = Gtk.DrawingArea()
        self.seekbar.set_size_request(150, 20)
        self.seekbar.set_valign(Gtk.Align.CENTER)
        self.seekbar.add_events(Gdk.EventMask.BUTTON_PRESS_MASK | Gdk.EventMask.POINTER_MOTION_MASK)
        self.seekbar.connect("draw", self.on_draw_seekbar)
        self.seekbar.connect("button-press-event", self.on_seek_event)
        self.seekbar.connect("motion-notify-event", self.on_seek_event)
        
        self.media_bottom.pack_start(self.btn_prev, False, False, 0)
        self.media_bottom.pack_start(self.seekbar, True, True, 0)
        self.media_bottom.pack_end(self.btn_next, False, False, 0)
        self.media_bottom.set_margin_top(4)
        self.media_bottom.set_valign(Gtk.Align.END)
        
        # Attach to Grid
        self.media_grid.attach(self.title_stack, 0, 0, 1, 1)
        self.media_grid.attach(self.artist_stack, 0, 1, 1, 1)
        self.media_grid.attach(self.media_spacer, 0, 2, 1, 1) # Flexible space
        self.media_grid.attach(self.media_time_label, 0, 3, 1, 1)
        
        self.media_grid.attach(self.btn_play, 1, 0, 1, 4) # Spans 4 rows down to time label
        self.media_grid.attach(self.media_bottom, 0, 4, 2, 1) # Spans 2 columns at absolute bottom
        
        self.media_widget.pack_start(self.cover_art, False, False, 0)
        self.media_widget.pack_start(self.media_grid, True, True, 0)
        
        self.stack.add_named(self.media_widget, "media")
        
        # 3. Compact Media Widget
        self.compact_widget = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.compact_widget.set_halign(Gtk.Align.CENTER)
        self.compact_widget.set_valign(Gtk.Align.CENTER)
        
        self.compact_cover = Gtk.DrawingArea()
        self.compact_cover.set_size_request(24, 24)
        self.compact_cover.set_valign(Gtk.Align.CENTER)
        self.compact_cover.connect("draw", self.on_draw_compact_cover)
        
        vbox_compact = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        vbox_compact.set_valign(Gtk.Align.CENTER)
        
        self.compact_title = Gtk.Label(label="")
        self.compact_title.set_halign(Gtk.Align.START)
        self.compact_title.set_name("TitleLabel")
        self.compact_title.set_ellipsize(Pango.EllipsizeMode.END)
        self.compact_title.set_max_width_chars(15)
        
        self.compact_artist = Gtk.Label(label="")
        self.compact_artist.set_halign(Gtk.Align.START)
        self.compact_artist.set_name("SubtitleLabel")
        self.compact_artist.set_ellipsize(Pango.EllipsizeMode.END)
        self.compact_artist.set_max_width_chars(15)
        
        vbox_compact.pack_start(self.compact_title, False, False, 0)
        vbox_compact.pack_start(self.compact_artist, False, False, 0)
        
        self.compact_widget.pack_start(self.compact_cover, False, False, 0)
        self.compact_widget.pack_start(vbox_compact, False, False, 0)
        
        self.stack.add_named(self.compact_widget, "compact")
        
        # 4. System Details Widget
        self.system_widget = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=16)
        self.system_widget.set_halign(Gtk.Align.CENTER)
        self.system_widget.set_valign(Gtk.Align.CENTER)
        
        def create_sys_col(title, width=90):
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
            box.set_size_request(width, -1)
            header = Gtk.Label(label=title)
            header.set_name("TitleLabel")
            header.set_halign(Gtk.Align.START)
            box.pack_start(header, False, False, 0)
            return box
            
        self.sys_ram_col = create_sys_col("RAM", 90)
        self.sys_swap_col = create_sys_col("Swap", 90)
        self.sys_cpu_col = create_sys_col("CPU", 65)
        
        self.sys_labels = {}
        def add_stat(col, key, label_text):
            l = Gtk.Label(label=label_text)
            l.set_name("SubtitleLabel")
            l.set_halign(Gtk.Align.START)
            col.pack_start(l, False, False, 0)
            self.sys_labels[key] = l
            
        add_stat(self.sys_ram_col, "ram_used", "Used: -- GB")
        add_stat(self.sys_ram_col, "ram_free", "Free: -- GB")
        add_stat(self.sys_ram_col, "ram_total", "Total: -- GB")
        
        add_stat(self.sys_swap_col, "swap_used", "Used: -- GB")
        add_stat(self.sys_swap_col, "swap_free", "Free: -- GB")
        add_stat(self.sys_swap_col, "swap_total", "Total: -- GB")
        
        add_stat(self.sys_cpu_col, "cpu_load", "Load: --%")
        
        self.system_widget.pack_start(self.sys_ram_col, False, False, 0)
        self.system_widget.pack_start(self.sys_swap_col, False, False, 0)
        self.system_widget.pack_start(self.sys_cpu_col, False, False, 0)
        
        self.stack.add_named(self.system_widget, "system")
        
        # 5. Split Calendar/Weather Widget
        self.calendar_widget = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.calendar_widget.set_halign(Gtk.Align.CENTER)
        self.calendar_widget.set_valign(Gtk.Align.CENTER)
        
        # Left side: Weather (WeatherPanel)
        self.weather_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.weather_box.set_name("WeatherPanel")
        self.weather_box.set_size_request(130, 184)
        
        w_top = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.w_icon = Gtk.Label(label="☁")
        self.w_icon.set_name("WeatherDesc")
        self.w_desc = Gtk.Label(label="Cloudy")
        self.w_desc.set_name("WeatherDesc")
        w_top.pack_start(self.w_icon, False, False, 0)
        w_top.pack_start(self.w_desc, False, False, 0)
        w_top.set_margin_top(12)
        w_top.set_margin_left(12)
        
        self.w_temp = Gtk.Label(label="--°")
        self.w_temp.set_name("WeatherTemp")
        self.w_temp.set_halign(Gtk.Align.START)
        self.w_temp.set_margin_left(12)
        
        self.w_hl = Gtk.Label(label="L:--° H:--°")
        self.w_hl.set_name("WeatherHL")
        self.w_hl.set_halign(Gtk.Align.START)
        self.w_hl.set_margin_left(12)
        self.w_hl.set_margin_bottom(12)
        
        self.weather_box.pack_start(w_top, False, False, 0)
        self.weather_box.pack_start(self.w_temp, True, True, 0)
        self.weather_box.pack_start(self.w_hl, False, False, 0)
        
        # Right side: Calendar
        self.cal_right = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.cal_right.set_size_request(252, 184)
        
        # Top Header (Black background, white text)
        cal_header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        now = datetime.now()
        month_name = calendar.month_name[now.month].upper()
        
        pill_area = Gtk.DrawingArea()
        pill_area.set_size_request(16, 14)
        pill_area.set_valign(Gtk.Align.CENTER)
        pill_area.set_margin_left(4)
        
        def draw_pills(widget, cr):
            colors = [(0.66, 0.33, 0.96), (0.98, 0.60, 0.13), (0.20, 0.83, 0.75)]
            for i, color in enumerate(colors):
                cr.set_source_rgb(*color)
                x = i * 6
                r = 2
                cr.arc(x + r, r, r, math.pi, 2 * math.pi)
                cr.arc(x + r, 14 - r, r, 0, math.pi)
                cr.fill()
                
        pill_area.connect("draw", draw_pills)
        
        h_left = Gtk.Label(label=f"{month_name}")
        h_left.set_name("CalendarHeader")
        h_right = Gtk.Label(label=str(now.year))
        h_right.set_name("CalendarYear")
        
        cal_header.pack_start(pill_area, False, False, 0)
        cal_header.pack_start(h_left, False, False, 0)
        cal_header.pack_end(h_right, False, False, 0)
        
        # Bottom Body (CalendarPanel)
        cal_body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        cal_body.set_name("CalendarPanel")
        cal_body.set_size_request(252, 148)
        
        # Week grid
        grid = Gtk.Grid()
        grid.set_column_spacing(10)
        grid.set_row_spacing(2)
        grid.set_halign(Gtk.Align.CENTER)
        grid.set_margin_top(10)
        
        days = ["SUN", "MON", "TUE", "WED", "THU", "FRI", "SAT"]
        for i, day in enumerate(days):
            l = Gtk.Label(label=day)
            l.set_name("CalendarDayName")
            grid.attach(l, i, 0, 1, 1)
            
        import datetime as dt
        idx = (now.weekday() + 1) % 7
        start_of_week = now - dt.timedelta(days=idx)
        
        for i in range(7):
            d = start_of_week + dt.timedelta(days=i)
            l = Gtk.Label(label=str(d.day))
            if d.date() == now.date():
                l.set_name("ActiveDate")
            else:
                l.set_name("CalendarDate")
            grid.attach(l, i, 1, 1, 1)
            
            if i in (idx, idx+1):
                dot = Gtk.Label(label="•")
                dot.set_name("EventDot")
                grid.attach(dot, i, 2, 1, 1)
                
        cal_body.pack_start(grid, False, False, 0)
        
        sep = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        sep.set_name("EventSep")
        sep.set_margin_left(10)
        sep.set_margin_right(10)
        cal_body.pack_start(sep, False, False, 0)
        
        event_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        event_box.set_margin_left(12)
        event_box.set_margin_bottom(10)
        self.e_time = Gtk.Label(label=f"Today, {datetime.now().strftime('%H:%M')}")
        self.e_time.set_name("EventTime")
        self.e_time.set_halign(Gtk.Align.START)
        
        self.recent_apps_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.recent_apps_box.set_halign(Gtk.Align.START)
        
        event_box.pack_start(self.e_time, False, False, 0)
        event_box.pack_start(self.recent_apps_box, False, False, 0)
        
        cal_body.pack_start(event_box, True, True, 0)
        
        self.cal_right.pack_start(cal_header, False, False, 0)
        self.cal_right.pack_start(cal_body, True, True, 0)
        
        self.calendar_widget.pack_start(self.weather_box, False, False, 0)
        self.calendar_widget.pack_start(self.cal_right, False, False, 0)
        
        self.stack.add_named(self.calendar_widget, "calendar")
        
        # 6. Battery Widget (Expanded)
        self.battery_widget = Gtk.DrawingArea()
        self.battery_widget.set_valign(Gtk.Align.FILL)
        self.battery_widget.set_halign(Gtk.Align.FILL)
        self.battery_widget.connect("draw", self.on_draw_battery)
        self.stack.add_named(self.battery_widget, "battery")
        
        # 7. Compact Battery Widget
        self.compact_battery_widget = Gtk.DrawingArea()
        self.compact_battery_widget.set_size_request(46, self.COMPACT_H)
        self.compact_battery_widget.set_valign(Gtk.Align.FILL)
        self.compact_battery_widget.connect("draw", self.on_draw_compact_battery)
        self.stack.add_named(self.compact_battery_widget, "compact_battery")
        
        # 9. Sidebar Vertical Idle (for left/right positions)
        self.sidebar_idle_widget = Gtk.DrawingArea()
        self.sidebar_idle_widget.set_size_request(self.SIDEBAR_IDLE_W, self.SIDEBAR_IDLE_H)
        self.sidebar_idle_widget.set_valign(Gtk.Align.FILL)
        self.sidebar_idle_widget.connect("draw", self.on_draw_sidebar_idle)
        self.stack.add_named(self.sidebar_idle_widget, "sidebar_header")
        
        # 10. Sidebar Media Widget (square card: cover fills all, content overlaid)
        self.sidebar_cover_art = Gtk.DrawingArea()
        self.sidebar_cover_art.set_size_request(self.SIDEBAR_MEDIA_W, self.SIDEBAR_MEDIA_H)
        self.sidebar_cover_art.set_halign(Gtk.Align.FILL)
        self.sidebar_cover_art.set_valign(Gtk.Align.FILL)
        self.sidebar_cover_art.connect("draw", self.on_draw_sidebar_cover)
        
        self.sidebar_title_label = Gtk.Label(label="")
        self.sidebar_title_label.set_name("TitleLabel")
        self.sidebar_title_label.set_halign(Gtk.Align.CENTER)
        self.sidebar_title_label.set_ellipsize(Pango.EllipsizeMode.END)
        self.sidebar_title_label.set_max_width_chars(14)
        
        self.sidebar_artist_label = Gtk.Label(label="")
        self.sidebar_artist_label.set_name("SubtitleLabel")
        self.sidebar_artist_label.set_halign(Gtk.Align.CENTER)
        self.sidebar_artist_label.set_ellipsize(Pango.EllipsizeMode.END)
        self.sidebar_artist_label.set_max_width_chars(14)
        
        self.sidebar_seekbar = Gtk.DrawingArea()
        self.sidebar_seekbar.set_size_request(-1, 14)
        self.sidebar_seekbar.set_hexpand(True)
        self.sidebar_seekbar.add_events(
            Gdk.EventMask.BUTTON_PRESS_MASK | Gdk.EventMask.POINTER_MOTION_MASK)
        self.sidebar_seekbar.connect("draw", self.on_draw_seekbar)
        self.sidebar_seekbar.connect("button-press-event", self.on_seek_event)
        self.sidebar_seekbar.connect("motion-notify-event", self.on_seek_event)
        
        sidebar_controls = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        sidebar_controls.set_halign(Gtk.Align.CENTER)
        self.sidebar_btn_prev = Gtk.Button(label="\u23ee")
        self.sidebar_btn_prev.set_name("NavButton")
        self.sidebar_btn_play = Gtk.Button(label="\u25b6")
        self.sidebar_btn_play.set_name("ControlBall")
        self.sidebar_btn_play.set_size_request(40, 40)
        self.sidebar_btn_next = Gtk.Button(label="\u23ed")
        self.sidebar_btn_next.set_name("NavButton")
        sidebar_controls.pack_start(self.sidebar_btn_prev, False, False, 0)
        sidebar_controls.pack_start(self.sidebar_btn_play, False, False, 0)
        sidebar_controls.pack_start(self.sidebar_btn_next, False, False, 0)
        
        # Floating bottom content panel
        sidebar_content_panel = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        sidebar_content_panel.set_halign(Gtk.Align.FILL)
        sidebar_content_panel.set_valign(Gtk.Align.END)
        sidebar_content_panel.set_margin_bottom(10)
        sidebar_content_panel.set_margin_start(10)
        sidebar_content_panel.set_margin_end(10)
        sidebar_content_panel.pack_start(self.sidebar_title_label, False, False, 0)
        sidebar_content_panel.pack_start(self.sidebar_artist_label, False, False, 0)
        sidebar_content_panel.pack_start(self.sidebar_seekbar, False, False, 4)
        sidebar_content_panel.pack_start(sidebar_controls, False, False, 0)
        
        # Overlay: cover as base, content floating on top
        self.sidebar_media_widget = Gtk.Overlay()
        self.sidebar_media_widget.add(self.sidebar_cover_art)
        self.sidebar_media_widget.add_overlay(sidebar_content_panel)
        self.stack.add_named(self.sidebar_media_widget, "sidebar_media")
        
        # 8. Settings Widget
        self.settings_widget = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.settings_widget.set_halign(Gtk.Align.FILL)
        self.settings_widget.set_valign(Gtk.Align.START)
        self.settings_widget.set_margin_top(14)
        self.settings_widget.set_margin_bottom(14)
        self.settings_widget.set_margin_start(16)
        self.settings_widget.set_margin_end(16)
        
        # Header
        lbl_settings = Gtk.Label(label="Settings")
        lbl_settings.set_name("SettingsHeader")
        lbl_settings.set_halign(Gtk.Align.START)
        self.settings_widget.pack_start(lbl_settings, False, False, 0)
        
        # ── Section: Appearance ──────────────────────
        sep0 = Gtk.Separator(); sep0.set_name("SettingsSep")
        self.settings_widget.pack_start(sep0, False, False, 0)
        sec_lbl1 = Gtk.Label(label="APPEARANCE"); sec_lbl1.set_name("SettingsSectionLabel")
        sec_lbl1.set_halign(Gtk.Align.START)
        self.settings_widget.pack_start(sec_lbl1, False, False, 0)
        
        theme_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        theme_lbl = Gtk.Label(label="Frosted Black Theme"); theme_lbl.set_name("SettingsLabel")
        theme_lbl.set_halign(Gtk.Align.START)
        theme_box.pack_start(theme_lbl, True, True, 0)
        self.theme_switch = Gtk.Switch()
        self.theme_switch.set_active(self.app_config.get("theme", "Frosted Black") == "Frosted Black")
        self.theme_switch.connect("state-set", self.on_theme_toggled)
        theme_box.pack_start(self.theme_switch, False, False, 0)
        self.settings_widget.pack_start(theme_box, False, False, 0)
        
        # ── Section: Clock ──────────────────────────
        sep1 = Gtk.Separator(); sep1.set_name("SettingsSep")
        self.settings_widget.pack_start(sep1, False, False, 0)
        sec_lbl2 = Gtk.Label(label="CLOCK"); sec_lbl2.set_name("SettingsSectionLabel")
        sec_lbl2.set_halign(Gtk.Align.START)
        self.settings_widget.pack_start(sec_lbl2, False, False, 0)
        
        time_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        time_lbl = Gtk.Label(label="24-Hour Format"); time_lbl.set_name("SettingsLabel")
        time_lbl.set_halign(Gtk.Align.START)
        time_box.pack_start(time_lbl, True, True, 0)
        self.time_switch = Gtk.Switch()
        self.time_switch.set_active(self.app_config.get("time_format", "24h") == "24h")
        self.time_switch.connect("state-set", self.on_time_toggled)
        time_box.pack_start(self.time_switch, False, False, 0)
        self.settings_widget.pack_start(time_box, False, False, 0)
        
        # ── Section: Position ───────────────────────
        sep2 = Gtk.Separator(); sep2.set_name("SettingsSep")
        self.settings_widget.pack_start(sep2, False, False, 0)
        sec_lbl3 = Gtk.Label(label="POSITION"); sec_lbl3.set_name("SettingsSectionLabel")
        sec_lbl3.set_halign(Gtk.Align.START)
        self.settings_widget.pack_start(sec_lbl3, False, False, 0)
        
        pos_lbl = Gtk.Label(label="Panel Position"); pos_lbl.set_name("SettingsLabel")
        pos_lbl.set_halign(Gtk.Align.START)
        self.settings_widget.pack_start(pos_lbl, False, False, 0)
        
        self.position_combo = Gtk.ComboBoxText()
        self.position_combo.set_name("SettingsCombo")
        positions = ["top", "top-left", "top-right", "bottom", "bottom-left", "bottom-right", "left", "right"]
        for p in positions:
            self.position_combo.append_text(p)
        current_pos = self.app_config.get("position", "top")
        self.position_combo.set_active(positions.index(current_pos) if current_pos in positions else 0)
        self.settings_widget.pack_start(self.position_combo, False, False, 0)
        
        # Save button
        save_btn = Gtk.Button(label="Apply & Save")
        save_btn.set_name("SettingsSaveBtn")
        save_btn.connect("clicked", self.on_save_settings)
        self.settings_widget.pack_start(save_btn, False, False, 4)
        
        self.stack.add_named(self.settings_widget, "settings")
        
        # 9. Mac Island Dashboard Widget
        self.mac_island_widget = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=15)
        self.mac_island_widget.set_margin_top(15)
        self.mac_island_widget.set_margin_bottom(15)
        self.mac_island_widget.set_margin_start(20)
        self.mac_island_widget.set_margin_end(20)
        
        # 2. Main Content
        content_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=30)
        
        # --- LEFT: MEDIA ---
        mac_media_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=15)
        
        self.mac_cover_art = Gtk.DrawingArea()
        self.mac_cover_art.set_size_request(90, 90)
        self.mac_cover_art.set_valign(Gtk.Align.CENTER)
        self.mac_cover_art.connect("draw", self.on_draw_mac_cover)
        
        mac_media_info = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        mac_media_info.set_valign(Gtk.Align.CENTER)
        
        self.mac_title_l1 = Gtk.Label(label="No Media", xalign=0)
        self.mac_title_l1.set_name("TitleLabel")
        self.mac_title_l1.set_ellipsize(Pango.EllipsizeMode.END)
        self.mac_title_l1.set_max_width_chars(15)
        self.mac_title_l1.set_markup("<b>No Media</b>")
        
        self.mac_album_l1 = Gtk.Label(label="", xalign=0)
        self.mac_album_l1.set_name("MacAlbumLabel")
        self.mac_album_l1.set_ellipsize(Pango.EllipsizeMode.END)
        self.mac_album_l1.set_max_width_chars(15)
        
        self.mac_artist_l1 = Gtk.Label(label="", xalign=0)
        self.mac_artist_l1.set_name("MacArtistLabel")
        self.mac_artist_l1.set_ellipsize(Pango.EllipsizeMode.END)
        self.mac_artist_l1.set_max_width_chars(15)
        
        mac_media_controls = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=15)
        self.mac_btn_prev = Gtk.Button(label="⏮")
        self.mac_btn_play = Gtk.Button(label="⏸")
        self.mac_btn_next = Gtk.Button(label="⏭")
        for btn in [self.mac_btn_prev, self.mac_btn_play, self.mac_btn_next]:
            btn.set_name("MacNavButton")
            mac_media_controls.pack_start(btn, False, False, 0)
        
        mac_media_info.pack_start(self.mac_title_l1, False, False, 0)
        mac_media_info.pack_start(self.mac_album_l1, False, False, 0)
        mac_media_info.pack_start(self.mac_artist_l1, False, False, 0)
        mac_media_info.pack_start(mac_media_controls, False, False, 2)
        
        mac_media_box.pack_start(self.mac_cover_art, False, False, 0)
        mac_media_box.pack_start(mac_media_info, False, False, 0)
        
        # --- CENTER: CALENDAR ---
        mac_cal_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        mac_cal_box.set_valign(Gtk.Align.CENTER)
        
        mac_cal_top = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=15)
        
        self.mac_month_label = Gtk.Label(label="Aug", xalign=0)
        self.mac_month_label.set_name("MacMonthLabel")
        
        mac_cal_week = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        self.mac_cal_dates = []
        for i in range(7):
            vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            lbl_day = Gtk.Label()
            lbl_date = Gtk.Label()
            lbl_day.set_name("MacCalDay")
            lbl_date.set_name("MacCalDate")
            vbox.pack_start(lbl_day, False, False, 0)
            vbox.pack_start(lbl_date, False, False, 0)
            mac_cal_week.pack_start(vbox, False, False, 0)
            self.mac_cal_dates.append((lbl_day, lbl_date))
            
        mac_cal_top.pack_start(self.mac_month_label, False, False, 0)
        mac_cal_top.pack_start(mac_cal_week, False, False, 0)
        mac_cal_box.pack_start(mac_cal_top, False, False, 0)
        # --- RIGHT: AVATAR ---
        self.mac_avatar = Gtk.DrawingArea()
        self.mac_avatar.set_size_request(90, 90)
        self.mac_avatar.set_valign(Gtk.Align.CENTER)
        self.mac_avatar.connect("draw", self.on_draw_mac_avatar)
        
        # Pack Content
        content_box.pack_start(mac_media_box, False, False, 0)
        
        sep1 = Gtk.Separator(orientation=Gtk.Orientation.VERTICAL)
        sep1.set_name("MacSep")
        sep1.set_margin_start(10)
        sep1.set_margin_end(10)
        content_box.pack_start(sep1, False, False, 0)
        
        content_box.pack_start(mac_cal_box, True, True, 0)
        
        sep2 = Gtk.Separator(orientation=Gtk.Orientation.VERTICAL)
        sep2.set_name("MacSep")
        sep2.set_margin_start(10)
        sep2.set_margin_end(10)
        content_box.pack_start(sep2, False, False, 0)
        
        content_box.pack_end(self.mac_avatar, False, False, 0)
        
        # Add to Island
        self.mac_island_widget.pack_start(content_box, True, True, 0)
        
        self.mac_island_widget.show_all()
        self.stack.add_named(self.mac_island_widget, "mac_island")
        
        # Overlay input mask & css
        self.overlay.add_overlay(self.content_box)
        
        screen = Gdk.Screen.get_default()
        css = get_stylesheet() + "\nwindow { background: transparent; }\n"
        provider = Gtk.CssProvider()
        provider.load_from_data(css.encode())
        Gtk.StyleContext.add_provider_for_screen(screen, provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        
        # Monitors
        self.media_monitor = MediaMonitor(self.on_media, self.on_lyric, self.on_progress)
        self.media_monitor.start()
        self.btn_prev.connect("clicked", lambda w: self.media_monitor.prev_track())
        self.btn_play.connect("clicked", lambda w: self.media_monitor.toggle_play_pause())
        self.btn_next.connect("clicked", lambda w: self.media_monitor.next_track())
        self.sidebar_btn_prev.connect("clicked", lambda w: self.media_monitor.prev_track())
        self.sidebar_btn_play.connect("clicked", lambda w: self.media_monitor.toggle_play_pause())
        self.sidebar_btn_next.connect("clicked", lambda w: self.media_monitor.next_track())
        self.mac_btn_prev.connect("clicked", lambda w: self.media_monitor.prev_track())
        self.mac_btn_play.connect("clicked", lambda w: self.media_monitor.toggle_play_pause())
        self.mac_btn_next.connect("clicked", lambda w: self.media_monitor.next_track())

        self.notif_monitor = NotificationMonitor(self.on_notif)
        self.notif_monitor.start()
        
        self.key_monitor = KeyLockMonitor(self.on_keylock)
        self.key_monitor.start()
        
        self.battery_monitor = BatteryMonitor(self.on_battery_changed)
        self.battery_monitor.start()
        
        self.system_monitor = SystemMonitor(self.on_system_stats_update)
        self.system_monitor.start()
        
        self.weather_monitor = WeatherMonitor(self.on_weather_update)
        self.weather_monitor.start()
        
        self.anim_group = ParallelAnimationGroup()
        self.connect("destroy", self.on_destroy)

    def load_config(self):
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r") as f:
                    data = json.load(f)
                    self.app_config.update(data)
            except Exception as e:
                print("Error loading config:", e)

    def save_config(self):
        try:
            with open(self.config_path, "w") as f:
                json.dump(self.app_config, f, indent=4)
        except Exception as e:
            print("Error saving config:", e)

    def on_button_press(self, widget, event):
        if event.type == Gdk.EventType.BUTTON_PRESS:
            if event.button == 3:  # Right-click
                if self.current_state == "Settings":
                    self.change_state("Idle", "")
                else:
                    self.change_state("Settings", "")
                return True
        return False
        
    def on_theme_toggled(self, switch, state):
        self.app_config["theme"] = "Frosted Black" if state else "Clear Glass"
        self.save_config()
        self.drawing_area.queue_draw()
        
    def on_time_toggled(self, switch, state):
        self.app_config["time_format"] = "24h" if state else "12h"
        self.save_config()
        self.update_clock()
    
    def on_save_settings(self, btn):
        positions = ["top", "top-left", "top-right", "bottom", "bottom-left", "bottom-right", "left", "right"]
        idx = self.position_combo.get_active()
        if 0 <= idx < len(positions):
            self.app_config["position"] = positions[idx]
        self.save_config()
        self.apply_position()
        self.change_state("Idle", "")
        
    def _apply_anchors(self):
        if not (HAS_LAYER_SHELL and GtkLayerShell.is_supported()):
            return
            
        for edge in [GtkLayerShell.Edge.TOP, GtkLayerShell.Edge.BOTTOM, 
                     GtkLayerShell.Edge.LEFT, GtkLayerShell.Edge.RIGHT]:
            GtkLayerShell.set_anchor(self, edge, False)
            GtkLayerShell.set_margin(self, edge, 10)
            
        pos = self.app_config.get("position", "top")
        if "top" in pos:
            GtkLayerShell.set_anchor(self, GtkLayerShell.Edge.TOP, True)
        if "bottom" in pos:
            if HAS_LAYER_SHELL and GtkLayerShell.is_supported():
                GtkLayerShell.set_anchor(self, GtkLayerShell.Edge.BOTTOM, True)
        if "left" in pos:
            GtkLayerShell.set_anchor(self, GtkLayerShell.Edge.LEFT, True)
        if "right" in pos:
            GtkLayerShell.set_anchor(self, GtkLayerShell.Edge.RIGHT, True)

    def apply_position(self):
        self._apply_anchors()

        # Align content_box — always centered within the island window
        if hasattr(self, 'content_box'):
            self.content_box.set_halign(Gtk.Align.CENTER)
            self.content_box.set_margin_start(0)
            self.content_box.set_margin_end(0)
        
        if hasattr(self, 'drawing_area'):
            self.drawing_area.queue_draw()
    
    def update_radius(self, val):
        self.border_radius = val
        self.drawing_area.queue_draw()
        
    def on_destroy(self, widget):
        self.media_monitor.stop()
        self.notif_monitor.stop()
        self.key_monitor.stop()
        self.battery_monitor.stop()
        self.system_monitor.stop()
        self.weather_monitor.stop()
        Gtk.main_quit()
        
    def start_collapse_timer(self):
        if self.collapse_timer:
            GLib.source_remove(self.collapse_timer)
        self.collapse_timer = GLib.timeout_add(2000, self._do_collapse)
        
    def _do_collapse(self):
        self.collapse_timer = None
        if not self.is_hovered:
            self._do_idle_state()
        return False

    def on_hover_enter(self, widget, event):
        self.is_hovered = True
        if self.collapse_timer:
            GLib.source_remove(self.collapse_timer)
            self.collapse_timer = None
            
        if self.current_state == "CompactMedia" or (self.current_state == "Idle" and self.last_media_title):
            self.change_state("Media", f"{self.last_media_title} - {self.last_media_artist}")
        return False
        
    def on_hover_leave(self, widget, event):
        self.is_hovered = False
        if self.current_state not in ("Idle", "Settings"):
            self.start_collapse_timer()
        return False

    def hex_to_rgb(self, hex_color):
        hex_color = hex_color.lstrip('#')
        if len(hex_color) == 6:
            return tuple(int(hex_color[i:i+2], 16)/255.0 for i in (0, 2, 4))
        return (0, 0, 0)

    def on_draw(self, widget, cr):
        alloc = widget.get_allocation()
        cx = alloc.width / 2.0
        w = self.island_w
        h = self.island_h
        r = min(getattr(self, 'border_radius', min(w, h) / 2.0), w / 2.0, h / 2.0)
        
        x = cx - w / 2.0
        y = 0
        
        rect = cairo.RectangleInt(int(x), int(y), int(w), int(h))
        region = cairo.Region(rect)
        self.input_shape_combine_region(region)
        
        cr.arc(x + r, y + r, r, math.pi, 1.5 * math.pi)
        cr.arc(x + w - r, y + r, r, 1.5 * math.pi, 2 * math.pi)
        cr.arc(x + w - r, y + h - r, r, 0, 0.5 * math.pi)
        cr.arc(x + r, y + h - r, r, 0.5 * math.pi, math.pi)
        cr.close_path()
        cr.clip()
        
        # Base background for Idle mode (dark frosted glass feel)
        cr.set_source_rgba(0.0, 0.0, 0.0, 0.95)
        cr.paint()
        
        # Draw album cover background
        if getattr(self, 'bg_pixbuf', None) and getattr(self, 'bg_opacity', 0.0) > 0.01:
            cr.push_group()
            if getattr(self, 'old_bg_pixbuf', None) and getattr(self, 'art_alpha', 1.0) < 1.0:
                Gdk.cairo_set_source_pixbuf(cr, self.old_bg_pixbuf, x, y)
                cr.paint()
                Gdk.cairo_set_source_pixbuf(cr, self.bg_pixbuf, x, y)
                cr.paint_with_alpha(self.art_alpha)
            else:
                Gdk.cairo_set_source_pixbuf(cr, self.bg_pixbuf, x, y)
                cr.paint()
                self.old_bg_pixbuf = None
                
            # Darken the album cover to ensure text is readable
            cr.set_source_rgba(0, 0, 0, getattr(self, 'bg_darkness', 0.7))
            cr.paint()
            
            cr.pop_group_to_source()
            cr.paint_with_alpha(self.bg_opacity)
            
        # Subtle frosted glass border
        cr.set_source_rgba(1, 1, 1, 0.15)
        cr.set_line_width(1.5)
        cr.arc(x + r, y + r, r, math.pi, 1.5 * math.pi)
        cr.arc(x + w - r, y + r, r, 1.5 * math.pi, 2 * math.pi)
        cr.arc(x + w - r, y + h - r, r, 0, 0.5 * math.pi)
        cr.arc(x + r, y + h - r, r, 0.5 * math.pi, math.pi)
        cr.close_path()
        cr.stroke()
        
    def on_draw_cover(self, widget, cr):
        if not self.cover_pixbuf: return False
        w = widget.get_allocated_width()
        h = widget.get_allocated_height()
        radius = 12
        cr.arc(radius, radius, radius, math.pi, 1.5 * math.pi)
        cr.arc(w - radius, radius, radius, 1.5 * math.pi, 2 * math.pi)
        cr.arc(w - radius, h - radius, radius, 0, 0.5 * math.pi)
        cr.arc(radius, h - radius, radius, 0.5 * math.pi, math.pi)
        cr.close_path()
        cr.clip()
        
        if self.old_cover_pixbuf and getattr(self, 'art_alpha', 1.0) < 1.0:
            Gdk.cairo_set_source_pixbuf(cr, self.old_cover_pixbuf, 0, 0)
            cr.paint()
            Gdk.cairo_set_source_pixbuf(cr, self.cover_pixbuf, 0, 0)
            cr.paint_with_alpha(self.art_alpha)
        else:
            Gdk.cairo_set_source_pixbuf(cr, self.cover_pixbuf, 0, 0)
            cr.paint()
            self.old_cover_pixbuf = None
            
        return True
        
    def on_draw_sidebar_cover(self, widget, cr):
        """Cover art fills the full square; clips to rounded capsule, adds bottom gradient."""
        w = widget.get_allocated_width()
        h = widget.get_allocated_height()
        r = min(getattr(self, 'border_radius', 20.0), w / 2.0, h / 2.0)
        
        # Clip to rounded rect matching the capsule shape
        cr.arc(r, r, r, math.pi, 1.5 * math.pi)
        cr.arc(w - r, r, r, 1.5 * math.pi, 2 * math.pi)
        cr.arc(w - r, h - r, r, 0, 0.5 * math.pi)
        cr.arc(r, h - r, r, 0.5 * math.pi, math.pi)
        cr.close_path()
        cr.clip()
        
        if self.cover_pixbuf:
            scaled = self.cover_pixbuf.scale_simple(w, h, GdkPixbuf.InterpType.BILINEAR)
            if self.old_cover_pixbuf and getattr(self, 'art_alpha', 1.0) < 1.0:
                old_scaled = self.old_cover_pixbuf.scale_simple(w, h, GdkPixbuf.InterpType.BILINEAR)
                Gdk.cairo_set_source_pixbuf(cr, old_scaled, 0, 0)
                cr.paint()
                Gdk.cairo_set_source_pixbuf(cr, scaled, 0, 0)
                cr.paint_with_alpha(self.art_alpha)
            else:
                Gdk.cairo_set_source_pixbuf(cr, scaled, 0, 0)
                cr.paint()
        else:
            cr.set_source_rgba(0.12, 0.12, 0.18, 1.0)
            cr.paint()
            cr.set_source_rgba(1, 1, 1, 0.15)
            cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
            cr.set_font_size(48)
            note = "\u266b"
            ext = cr.text_extents(note)
            cr.move_to((w - ext.width) / 2, (h + ext.height) / 2)
            cr.show_text(note)
        
        # Bottom gradient overlay for text readability
        grad = cairo.LinearGradient(0, h * 0.42, 0, h)
        grad.add_color_stop_rgba(0, 0, 0, 0, 0)
        grad.add_color_stop_rgba(1, 0, 0, 0, 0.85)
        cr.set_source(grad)
        cr.paint()
        
        return True
    
    def on_draw_mac_avatar(self, widget, cr):
        w = widget.get_allocated_width()
        h = widget.get_allocated_height()
        r = min(w, h) / 2
        
        cr.arc(w/2, h/2, r, 0, 2*math.pi)
        cr.clip()
        
        if getattr(self, 'current_video_pixbuf', None):
            Gdk.cairo_set_source_pixbuf(cr, self.current_video_pixbuf, w/2 - self.current_video_pixbuf.get_width()/2, h/2 - self.current_video_pixbuf.get_height()/2)
            cr.paint()
            return True
            
        try:
            import getpass, os
            user = getpass.getuser()
            face_path = f"/var/lib/AccountsService/icons/{user}"
            if not os.path.exists(face_path):
                face_path = os.path.expanduser("~/.face")
            if os.path.exists(face_path):
                pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(face_path, int(r*2), int(r*2), True)
                Gdk.cairo_set_source_pixbuf(cr, pixbuf, w/2 - pixbuf.get_width()/2, h/2 - pixbuf.get_height()/2)
                cr.paint()
            else:
                cr.set_source_rgb(0.3, 0.3, 0.3)
                cr.paint()
        except:
            cr.set_source_rgb(0.3, 0.3, 0.3)
            cr.paint()
        
        return True

    def on_draw_mac_cover(self, widget, cr):
        if not getattr(self, 'cover_pixbuf', None): return False
        w = widget.get_allocated_width()
        h = widget.get_allocated_height()
        radius = 10.0
        
        cr.new_sub_path()
        cr.arc(w - radius, radius, radius, -math.pi/2, 0)
        cr.arc(w - radius, h - radius, radius, 0, math.pi/2)
        cr.arc(radius, h - radius, radius, math.pi/2, math.pi)
        cr.arc(radius, radius, radius, math.pi, 3*math.pi/2)
        cr.close_path()
        cr.clip()
        
        scaled = self.cover_pixbuf.scale_simple(w, h, GdkPixbuf.InterpType.BILINEAR)
        Gdk.cairo_set_source_pixbuf(cr, scaled, 0, 0)
        cr.paint()
        return True
        
    def on_draw_compact_cover(self, widget, cr):
        if not self.cover_pixbuf: return False
        w = widget.get_allocated_width()
        h = widget.get_allocated_height()
        radius = 6
        cr.arc(radius, radius, radius, math.pi, 1.5 * math.pi)
        cr.arc(w - radius, radius, radius, 1.5 * math.pi, 2 * math.pi)
        cr.arc(w - radius, h - radius, radius, 0, 0.5 * math.pi)
        cr.arc(radius, h - radius, radius, 0.5 * math.pi, math.pi)
        cr.close_path()
        cr.clip()
        
        cr.scale(w/110.0, h/110.0)
        Gdk.cairo_set_source_pixbuf(cr, self.cover_pixbuf, 0, 0)
        cr.paint()
        return True
        
    def on_draw_seekbar(self, widget, cr):
        w = widget.get_allocated_width()
        h = widget.get_allocated_height()
        cy = h / 2.0
        pad = 4
        
        progress_w = pad
        if self.current_length > 0:
            progress_w = pad + (w - 2*pad) * (self.visual_progress / self.current_length)
            
        cr.set_line_width(3)
        cr.set_line_cap(cairo.LINE_CAP_ROUND)
        cr.set_line_join(cairo.LINE_JOIN_ROUND)
        
        # Unplayed portion (straight line)
        cr.set_source_rgba(1, 1, 1, 0.2)
        cr.move_to(progress_w, cy)
        cr.line_to(w - pad, cy)
        cr.stroke()
        
        # Played portion (animated sine wave)
        if progress_w > pad:
            cr.set_source_rgba(1, 1, 1, 1.0)
            cr.move_to(pad, cy)
            
            amplitude = 3
            frequency = 0.2
            phase = getattr(self, 'wave_phase', 0.0)
            
            for x in range(pad, int(progress_w) + 1, 2):
                dampen = 1.0
                dist_to_handle = progress_w - x
                if dist_to_handle < 10:
                    dampen = dist_to_handle / 10.0
                    
                y = cy + math.sin((x - pad) * frequency - phase) * amplitude * dampen
                cr.line_to(x, y)
            cr.stroke()
            
            # Draw handle
            cr.arc(progress_w, cy, 4, 0, 2 * math.pi)
            cr.fill()
            
        return True

    def on_draw_battery(self, widget, cr):
        print("BATTERY ALLOC:", widget.get_allocated_width(), widget.get_allocated_height())
        w = widget.get_allocated_width()
        h = widget.get_allocated_height()
        
        status = getattr(self, 'battery_status', 'Unknown')
        percent = getattr(self, 'battery_percent', 0)
        time_str = getattr(self, 'battery_time', '')
        
        if status in ["Charging", "Full"]:
            color = (0.2, 0.8, 0.3)  # Green
        else:
            if percent <= 20:
                color = (1.0, 0.2, 0.2)  # Red for critical
            else:
                color = (1.0, 0.8, 0.1)  # Amber for discharging
            
        pct = max(5, min(100, percent)) / 100.0
        
        if self._is_sidebar():
            track_w = 6
            track_h = h - 50
            track_x = (w - track_w) / 2
            track_y = 20
            
            # Background
            cr.set_source_rgba(0.2, 0.2, 0.2, 1.0)
            cr.arc(track_x + track_w/2, track_y + track_w/2, track_w/2, math.pi, 2*math.pi)
            cr.arc(track_x + track_w/2, track_y + track_h - track_w/2, track_w/2, 0, math.pi)
            cr.fill()
            
            pill_w = 24
            pill_h = 46
            
            # Fill track vertically (bottom up)
            pill_center_y = track_y + track_h - (track_h * pct)
            pill_y = pill_center_y - pill_h / 2
            if pill_y < track_y: pill_y = track_y
            if pill_y + pill_h > track_y + track_h: pill_y = track_y + track_h - pill_h
            pill_x = (w - pill_w) / 2
            
            track_end_y = pill_y + pill_h + 8
            if track_end_y > track_y + track_h - track_w: track_end_y = track_y + track_h - track_w
            
            cr.set_source_rgb(*color)
            cr.arc(track_x + track_w/2, track_end_y + track_w/2, track_w/2, math.pi, 2*math.pi)
            cr.arc(track_x + track_w/2, track_y + track_h - track_w/2, track_w/2, 0, math.pi)
            cr.fill()
            
            # Glow vertically
            cr.save()
            cr.translate(pill_x + pill_w/2, pill_y + pill_h*0.75)
            cr.scale(1.0, 4.0)
            pat = cairo.RadialGradient(0, 10, 2, 0, -10, 20)
            pat.add_color_stop_rgba(0, color[0], color[1], color[2], 1.0)
            pat.add_color_stop_rgba(1, color[0], color[1], color[2], 0.0)
            cr.set_source(pat)
            cr.arc(0, -10, 20, 0, 2*math.pi)
            cr.fill()
            cr.restore()
            
            # Solid pill
            cr.set_source_rgb(*color)
            r = pill_w / 2
            cr.arc(pill_x + r, pill_y + r, r, math.pi, 2*math.pi)
            cr.arc(pill_x + r, pill_y + pill_h - r, r, 0, math.pi)
            cr.fill()
            
            # Lightning bolt inside pill
            if color == (1.0, 1.0, 1.0):
                cr.set_source_rgb(0, 0, 0)
            else:
                cr.set_source_rgb(1, 1, 1)
                
            bx = pill_x + 9
            by = pill_y + 12
            cr.move_to(bx + 4, by)
            cr.line_to(bx, by + 8)
            cr.line_to(bx + 3, by + 8)
            cr.line_to(bx + 1, by + 14)
            cr.line_to(bx + 7, by + 6)
            cr.line_to(bx + 3, by + 6)
            cr.line_to(bx + 4, by)
            cr.fill()
            
            # Draw percent text below the track
            cr.set_font_size(13)
            cr.select_font_face("Segoe UI", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
            text = f"{percent}"
            ext = cr.text_extents(text)
            cr.move_to((w - ext.width) / 2, track_y + track_h + 18)
            cr.show_text(text)
            
        else:
            track_w = w - 40
            track_h = 6
            track_x = 20
            track_y = (h - track_h) / 2
            
            # Draw track background
            cr.set_source_rgba(0.2, 0.2, 0.2, 1.0)
            cr.arc(track_x + track_h/2, track_y + track_h/2, track_h/2, math.pi/2, 3*math.pi/2)
            cr.arc(track_x + track_w - track_h/2, track_y + track_h/2, track_h/2, -math.pi/2, math.pi/2)
            cr.fill()
            
            pill_w = 46
            pill_h = 24
            
            pill_center_x = track_x + (track_w * pct)
            pill_x = pill_center_x - pill_w / 2
            if pill_x < track_x: pill_x = track_x
            if pill_x + pill_w > track_x + track_w: pill_x = track_x + track_w - pill_w
            pill_y = (h - pill_h) / 2
            
            # Draw filled track
            gap = 8
            track_end_x = pill_x - gap
            if track_end_x < track_x + track_h: track_end_x = track_x + track_h
            
            cr.set_source_rgb(*color)
            cr.arc(track_x + track_h/2, track_y + track_h/2, track_h/2, math.pi/2, 3*math.pi/2)
            cr.arc(track_end_x - track_h/2, track_y + track_h/2, track_h/2, -math.pi/2, math.pi/2)
            cr.fill()
            
            # Glow (Scaled Radial tail with intense right edge)
            cr.save()
            cr.translate(pill_x + pill_w/4, pill_y + pill_h/2)
            cr.scale(4.0, 1.0)
            pat = cairo.RadialGradient(10, 0, 2, -10, 0, 20)
            pat.add_color_stop_rgba(0, color[0], color[1], color[2], 1.0)
            pat.add_color_stop_rgba(1, color[0], color[1], color[2], 0.0)
            cr.set_source(pat)
            cr.arc(-10, 0, 20, 0, 2*math.pi)
            cr.fill()
            cr.restore()
            
            # Solid pill
            cr.set_source_rgb(*color)
            r = pill_h / 2
            cr.arc(pill_x + r, pill_y + r, r, math.pi/2, 3*math.pi/2)
            cr.arc(pill_x + pill_w - r, pill_y + r, r, -math.pi/2, math.pi/2)
            cr.fill()
            
            # Draw lightning bolt inside pill
            if color == (1.0, 1.0, 1.0):
                cr.set_source_rgb(0, 0, 0)
            else:
                cr.set_source_rgb(1, 1, 1)
                
            bx = pill_x + 6
            by = pill_y + 5
            
            cr.move_to(bx + 5, by)
            cr.line_to(bx + 1, by + 8)
            cr.line_to(bx + 4, by + 8)
            cr.line_to(bx + 2, by + 14)
            cr.line_to(bx + 8, by + 6)
            cr.line_to(bx + 4, by + 6)
            cr.line_to(bx + 5, by)
            cr.fill()
            
            # Draw percent text
            cr.set_font_size(13)
            cr.select_font_face("Segoe UI", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
            cr.move_to(bx + 12, pill_y + 16)
            cr.show_text(str(percent))

        return True

    def on_draw_compact_battery(self, widget, cr):
        w = widget.get_allocated_width()
        h = widget.get_allocated_height()
        
        status = getattr(self, 'battery_status', 'Unknown')
        percent = getattr(self, 'battery_percent', 0)
        
        if status in ["Charging", "Full"]:
            color = (0.2, 0.8, 0.3)  # Green
        else:
            if percent <= 20:
                color = (1.0, 0.2, 0.2)  # Red for critical
            else:
                color = (1.0, 0.8, 0.1)  # Amber for discharging
            
        pill_w = 46
        pill_h = 24
        pill_x = (w - pill_w) / 2
        pill_y = (h - pill_h) / 2
        
        # Solid pill
        cr.set_source_rgb(*color)
        r = pill_h / 2
        cr.arc(pill_x + r, pill_y + r, r, math.pi/2, 3*math.pi/2)
        cr.arc(pill_x + pill_w - r, pill_y + r, r, -math.pi/2, math.pi/2)
        cr.fill()
        
        if color == (1.0, 1.0, 1.0):
            cr.set_source_rgb(0, 0, 0)
        else:
            cr.set_source_rgb(1, 1, 1)
            
        bx = pill_x + 6
        by = pill_y + 5
        cr.move_to(bx + 5, by)
        cr.line_to(bx + 1, by + 8)
        cr.line_to(bx + 4, by + 8)
        cr.line_to(bx + 2, by + 14)
        cr.line_to(bx + 8, by + 6)
        cr.line_to(bx + 4, by + 6)
        cr.line_to(bx + 5, by)
        cr.fill()
        
        cr.set_font_size(13)
        cr.select_font_face("Segoe UI", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
        cr.move_to(bx + 12, pill_y + 16)
        cr.show_text(str(percent))
        
        return True

    def on_draw_sidebar_idle(self, widget, cr):
        """Vertical pill idle face for left/right sidebar positions."""
        import datetime
        now = datetime.datetime.now()
        fmt_24 = self.app_config.get("time_format", "24h") == "24h"
        
        alloc = widget.get_allocation()
        w, h = alloc.width, alloc.height
        # No background clear — the main on_draw capsule is drawn beneath us
        
        # ── Day name (e.g. "SUN") ──────────────────────────
        day_str  = now.strftime('%a').upper()
        date_str = now.strftime('%m/%d')
        hour_str = now.strftime('%H') if fmt_24 else now.strftime('%I').lstrip('0') or '12'
        min_str  = now.strftime('%M')
        ampm_str = '' if fmt_24 else now.strftime('%p').lower()
        
        cr.set_source_rgba(1, 1, 1, 0.45)
        cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
        cr.set_font_size(10)
        day_ext = cr.text_extents(day_str)
        cr.move_to((w - day_ext.width) / 2, 25)
        cr.show_text(day_str)
        
        # ── Date (e.g. "06/07") ──────────────────────────
        cr.set_source_rgba(1, 1, 1, 0.30)
        cr.set_font_size(9)
        date_ext = cr.text_extents(date_str)
        cr.move_to((w - date_ext.width) / 2, 38)
        cr.show_text(date_str)
        
        # ── Hour (large) ──────────────────────────────────
        cr.set_source_rgba(1, 1, 1, 1.0)
        cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
        cr.set_font_size(20)
        h_ext = cr.text_extents(hour_str)
        cr.move_to((w - h_ext.width) / 2, 85)
        cr.show_text(hour_str)
        
        # ── Minute (large) ───────────────────────────────
        cr.set_source_rgba(1, 1, 1, 0.80)
        m_ext = cr.text_extents(min_str)
        cr.move_to((w - m_ext.width) / 2, 120)
        cr.show_text(min_str)
        
        # ── AM/PM (if 12h) ───────────────────────────────
        if ampm_str:
            cr.set_source_rgba(1, 1, 1, 0.35)
            cr.set_font_size(9)
            ap_ext = cr.text_extents(ampm_str)
            cr.move_to((w - ap_ext.width) / 2, 145)
            cr.show_text(ampm_str)
        
        return True
    def update_w(self, val):
        self.island_w = val
        self.content_box.set_size_request(int(val) - int(getattr(self, 'current_margin_x', 30)), -1)
        self.drawing_area.set_size_request(int(val), int(self.island_h) + 4)
        self.drawing_area.queue_draw()
        
    def _is_sidebar(self):
        """True when position is left or right (pure sidebar, no top/bottom)."""
        return self.app_config.get("position", "top") in ("left", "right")

    def update_margin_x(self, val):
        self.current_margin_x = val
        self.content_box.set_size_request(int(self.island_w) - int(val), -1)
        
    def update_h(self, val):
        self.island_h = val
        self.drawing_area.set_size_request(int(self.island_w), int(val) + 4)
        self.drawing_area.queue_draw()

    def update_content_opacity(self, val):
        self.content_opacity = val
        self.content_box.set_opacity(val)
        
    def update_bg_darkness(self, val):
        self.bg_darkness = val
        self.drawing_area.queue_draw()
        
    def update_bg_opacity(self, val):
        self.bg_opacity = val
        self.drawing_area.queue_draw()
        
    def update_content_y(self, val):
        self.current_margin_top = val
        self.content_box.set_margin_top(int(val))

    def change_state(self, state, text=""):
        if self.current_state == state and self.status_label.get_text() == text:
            return
            
        self.current_state = state
        
        # Idle dimensions: vertical pill for sidebar, normal pill otherwise
        if state == "Idle":
            if self._is_sidebar():
                target_w, target_h = self.SIDEBAR_IDLE_W, self.SIDEBAR_IDLE_H
            else:
                target_w, target_h = self.IDLE_W, self.IDLE_H
        if state == "Media":
            if self._is_sidebar():
                target_w, target_h = self.SIDEBAR_MEDIA_W, self.SIDEBAR_MEDIA_H
            else:
                target_w, target_h = self.MEDIA_W, self.MEDIA_H
        elif state == "CompactMedia":
            target_w, target_h = self.COMPACT_W, self.COMPACT_H
        elif state == "SystemDetails":
            target_w, target_h = self.SYSTEM_W, self.SYSTEM_H
        elif state == "MacIsland":
            target_w = 860
            target_h = 124
            now = datetime.now()
            import datetime as dt
            self.mac_month_label.set_text(now.strftime('%b'))
            start_date = now - dt.timedelta(days=now.weekday()) # Monday
            
            accent = "#FFFFFF"
            try:
                import subprocess
                out = subprocess.check_output(["gsettings", "get", "org.gnome.desktop.background", "primary-color"]).decode().strip().strip("'")
                if out.startswith("#") and len(out) == 7:
                    r = int(out[1:3], 16)
                    g = int(out[3:5], 16)
                    b = int(out[5:7], 16)
                    luminance = 0.299 * r + 0.587 * g + 0.114 * b
                    if luminance >= 100:
                        accent = out
            except:
                pass
                
            if accent == "#FFFFFF":
                try:
                    import subprocess
                    out = subprocess.check_output(["kreadconfig5", "--group", "General", "--key", "AccentColor"], stderr=subprocess.STDOUT).decode().strip()
                    if out and "," in out:
                        r, g, b = map(int, out.split(","))
                        luminance = 0.299 * r + 0.587 * g + 0.114 * b
                        if luminance >= 100:
                            accent = f"#{r:02x}{g:02x}{b:02x}"
                except:
                    pass
                
            for i in range(7):
                d = start_date + dt.timedelta(days=i)
                lbl_day, lbl_date = self.mac_cal_dates[i]
                if d.date() == now.date():
                    lbl_day.set_markup(f"<span color='{accent}'>{d.strftime('%a').upper()[:3]}</span>")
                    lbl_date.set_markup(f"<span color='{accent}'>{d.strftime('%d')}</span>")
                else:
                    lbl_day.set_text(d.strftime('%a').upper()[:3])
                    lbl_date.set_text(d.strftime('%d'))
                    
            if getattr(self, 'video_cap', None) and not getattr(self, 'video_timer', None):
                self.video_timer = GLib.timeout_add(33, self._update_video_frame)
                
        elif state == "Calendar":
            target_w = self.CALENDAR_W
            req_h = self.calendar_widget.get_preferred_height()[1]
            target_h = req_h + 12
            self.update_recent_apps()
        elif state == "Battery":
            if self._is_sidebar():
                target_w, target_h = self.BATTERY_H, self.BATTERY_W
                self.battery_widget.set_size_request(self.BATTERY_H, self.BATTERY_W)
            else:
                target_w, target_h = self.BATTERY_W, self.BATTERY_H
                self.battery_widget.set_size_request(self.BATTERY_W - 20, self.BATTERY_H)
        elif state == "CompactBattery":
            target_w, target_h = self.COMPACT_W, self.COMPACT_H
        elif state == "Notify":
            target_w, target_h = self.NOTIFY_W, self.NOTIFY_H
        elif state == "Settings":
            target_w = self.SETTINGS_W
            target_h = 360
            self.border_radius = 14.0
            if HAS_LAYER_SHELL and GtkLayerShell.is_supported():
                GtkLayerShell.set_anchor(self, GtkLayerShell.Edge.BOTTOM, False)
            
        if state == "Calendar":
            if HAS_LAYER_SHELL and GtkLayerShell.is_supported():
                GtkLayerShell.set_anchor(self, GtkLayerShell.Edge.BOTTOM, True)
            
        self.anim_group.stop()
        
        def phase_2():
            self.status_label.set_text(text)
            
            self.status_label.set_text(text)
                
            if state == "Media":
                if self._is_sidebar():
                    self.stack.set_visible_child_name("sidebar_media")
                else:
                    self.stack.set_visible_child_name("media")
            elif state == "CompactMedia":
                self.stack.set_visible_child_name("compact")
            elif state == "SystemDetails":
                self.stack.set_visible_child_name("system")
            elif state == "Calendar":
                self.stack.set_visible_child_name("calendar")
            elif state == "Battery":
                self.stack.set_visible_child_name("battery")
            elif state == "CompactBattery":
                self.stack.set_visible_child_name("compact_battery")
            elif state == "Settings":
                self.stack.set_visible_child_name("settings")
            elif state == "MacIsland":
                self.stack.set_visible_child_name("mac_island")
            else:
                if self._is_sidebar():
                    self.stack.set_visible_child_name("sidebar_header")
                    if hasattr(self, 'sidebar_idle_widget'):
                        self.sidebar_idle_widget.queue_draw()
                else:
                    self.stack.set_visible_child_name("header")
                
            self.anim_group = ParallelAnimationGroup()
            self.anim_group.add_animation(Tween(self.island_w, target_w, 850, Easing.out_expo, self.update_w))
            self.anim_group.add_animation(Tween(self.island_h, target_h, 850, Easing.out_expo, self.update_h))
            self.anim_group.add_animation(Tween(0.0, 1.0, 850, Easing.in_out_sine, self.update_content_opacity))
            
            if state in ("SystemDetails", "CompactMedia", "Calendar"):
                target_radius = 16.0
            elif state == "Media":
                if self._is_sidebar():
                    target_radius = 20.0  # rounded rect for vertical card
                else:
                    target_radius = 24.0
            elif state == "Settings":
                target_radius = 14.0  # Sharp minimal radius for settings capsule
            elif state == "MacIsland":
                target_radius = 24.0
            elif state == "Idle" and self._is_sidebar():
                target_radius = self.SIDEBAR_IDLE_W / 2.0
            else:
                target_radius = target_h / 2.0
                
            self.anim_group.add_animation(Tween(getattr(self, 'border_radius', self.island_h / 2.0), target_radius, 850, Easing.out_expo, self.update_radius))
            
            target_darkness = 0.7 if state in ("Idle", "CompactMedia", "SystemDetails", "Calendar") else 0.5
            self.anim_group.add_animation(Tween(getattr(self, 'bg_darkness', 0.7), target_darkness, 850, Easing.out_expo, self.update_bg_darkness))
            
            target_bg_opacity = 0.0 if state in ("Idle", "SystemDetails", "Calendar", "Battery", "CompactBattery", "Settings", "MacIsland") else 1.0
            self.anim_group.add_animation(Tween(getattr(self, 'bg_opacity', 0.0), target_bg_opacity, 850, Easing.out_expo, self.update_bg_opacity))
            
            if state == "Media":
                if self._is_sidebar():
                    target_margin = 0  # sidebar_media_widget has its own margins
                else:
                    target_margin = 15  # Centered perfectly within 140px height
            elif state == "CompactMedia":
                target_margin = (target_h - 24) / 2 # Compact has 24px tall cover
            elif state == "SystemDetails":
                target_margin = 16
            elif state == "Calendar":
                target_margin = 6
            elif state in ("Battery", "CompactBattery"):
                target_margin = 0
            elif state == "Settings":
                target_margin = 0
            elif state == "MacIsland":
                target_margin = 0
            else:
                target_margin = (target_h - 20) / 2
                if target_margin < 0: target_margin = 6
                
            self.anim_group.add_animation(Tween(getattr(self, 'current_margin_top', target_margin - 5), target_margin, 850, Easing.out_expo, self.update_content_y))
            
            target_margin_x = 12 if state == "Calendar" else (0 if state in ("Settings", "Media", "Battery") and self._is_sidebar() else (0 if state in ("Settings", "MacIsland") else 30))
            self.anim_group.add_animation(Tween(getattr(self, 'current_margin_x', 30), target_margin_x, 850, Easing.out_expo, self.update_margin_x))
            
            self.anim_group.start()
            
            # Auto-collapse any mode to idle after 2s of no interaction
            if state not in ("Idle", "Settings"):
                self.start_collapse_timer()
            
        fade_out = Tween(self.content_opacity, 0.0, 150, Easing.in_out_sine, self.update_content_opacity, on_complete=phase_2)
        fade_out.start()
        
    def update_crossfade(self, stack, l1, l2, new_text):
        if stack.get_visible_child_name() == "1":
            if l1.get_text() == new_text: return
            l2.set_text(new_text)
            stack.set_visible_child_name("2")
        else:
            if l2.get_text() == new_text: return
            l1.set_text(new_text)
            stack.set_visible_child_name("1")
            
    def update_clock(self):
        import datetime
        now = datetime.datetime.now()
        fmt_24 = self.app_config.get("time_format", "24h") == "24h"
        if getattr(self, 'current_state', '') == "Idle":
            if self._is_sidebar():
                if hasattr(self, 'sidebar_idle_widget'):
                    self.sidebar_idle_widget.queue_draw()
            else:
                if fmt_24:
                    time_str = f"{now.strftime('%H:%M')}   {now.strftime('%a, %m/%d')}"
                else:
                    time_str = f"{now.strftime('%I:%M %p').lower()}   {now.strftime('%a, %m/%d')}"
                self.status_label.set_text(time_str)
        if getattr(self, 'current_state', '') == "Calendar":
            if hasattr(self, 'e_time'):
                self.e_time.set_text(f"Today, {now.strftime('%H:%M')}")
        return True
        
    def update_recent_apps(self):
        import json, subprocess
        try:
            output = subprocess.check_output(['hyprctl', 'clients', '-j']).decode()
            clients = json.loads(output)
            clients = [c for c in clients if c.get('mapped') and c.get('title')]
            clients.sort(key=lambda x: x.get('focusHistoryID', 999))
            
            # Clear existing children
            for child in self.recent_apps_box.get_children():
                self.recent_apps_box.remove(child)
                
            for c in clients[:3]:
                # Attempt to extract a clean name
                app_class = c.get('class', '')
                if app_class.startswith('brave'): app_name = 'Brave Browser'
                elif 'TDesktop' in app_class: app_name = 'Telegram'
                else: app_name = app_class.split('-')[0].capitalize() if app_class else 'App'
                
                # Combine app name with title (truncate if too long)
                title = c.get('title', '')
                display_str = f"{app_name}: {title}"
                
                lbl = Gtk.Label(label=display_str)
                lbl.set_name("EventTitle")
                lbl.set_halign(Gtk.Align.START)
                lbl.set_ellipsize(Pango.EllipsizeMode.END)
                lbl.set_max_width_chars(25) # Ensure it doesn't expand too much
                self.recent_apps_box.pack_start(lbl, False, False, 0)
                lbl.show()
                
            # If no apps found, show a fallback
            if not clients:
                lbl = Gtk.Label(label="No recent apps")
                lbl.set_name("EventTitle")
                lbl.set_halign(Gtk.Align.START)
                self.recent_apps_box.pack_start(lbl, False, False, 0)
                lbl.show()
                
        except Exception as e:
            print("Failed to fetch recent apps:", e)
        return False
        
    def _do_idle_state(self):
        import datetime
        now = datetime.datetime.now()
        time_str = f"{now.strftime('%I:%M %p').lower()} • {now.strftime('%a, %m/%d')}"
        self.change_state("Idle", time_str)
        self.idle_timer = None
        return False
        
    def on_media(self, state, title, artist, accent, art_url, album=""):
        self.last_media_title = title
        self.last_media_artist = artist
        
        accents = accent.split("|")
        self.target_accent = accents[0]
        self.target_light_accent = accents[1] if len(accents) > 1 else accents[0]
        
        if not hasattr(self, 'play_btn_provider'):
            self.play_btn_provider = Gtk.CssProvider()
            self.btn_play.get_style_context().add_provider(self.play_btn_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
            
        btn_css = f'''
        button#ControlBall {{
            background-color: rgba(255, 255, 255, 0.15);
            border: none;
        }}
        button#ControlBall label {{ color: #FFFFFF; font-weight: bold; }}
        button#ControlBall:hover {{ background-color: rgba(255, 255, 255, 0.3); }}
        button#ControlBall:hover label {{ color: #FFFFFF; }}
        '''
        self.play_btn_provider.load_from_data(btn_css.encode())
        
        if art_url and os.path.exists("/tmp/dynamic_island_cover.png"):
            try:
                new_pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale("/tmp/dynamic_island_cover.png", 110, 110, True)
                if self.cover_pixbuf:
                    self.old_cover_pixbuf = self.cover_pixbuf
                    self.art_alpha = 0.0
                self.cover_pixbuf = new_pixbuf
                self.cover_art.queue_draw()
                
                if os.path.exists("/tmp/dynamic_island_bg.png"):
                    new_bg = GdkPixbuf.Pixbuf.new_from_file_at_scale("/tmp/dynamic_island_bg.png", self.MEDIA_W, self.MEDIA_H, False)
                    if self.bg_pixbuf:
                        self.old_bg_pixbuf = self.bg_pixbuf
                    self.bg_pixbuf = new_bg
            except: pass
            
        self.update_crossfade(self.title_stack, self.title_l1, self.title_l2, title)
        self.update_crossfade(self.artist_stack, self.artist_l1, self.artist_l2, artist)
        self.compact_title.set_text(title)
        self.compact_artist.set_text(artist)
        self.compact_artist.set_visible(bool(artist))
        self.compact_cover.queue_draw()
        # Sync sidebar media widgets
        if hasattr(self, 'sidebar_title_label'):
            self.sidebar_title_label.set_text(title)
        if hasattr(self, 'sidebar_artist_label'):
            self.sidebar_artist_label.set_text(artist)
        if hasattr(self, 'sidebar_cover_art'):
            self.sidebar_cover_art.queue_draw()
        if hasattr(self, 'mac_title_l1'):
            import html
            self.mac_title_l1.set_markup(f"<b>{html.escape(title)}</b>" if title else "<b>Unknown</b>")
        if hasattr(self, 'mac_album_l1'):
            import html
            self.mac_album_l1.set_markup(f"<b>{html.escape(album)}</b>" if album else "")
        if hasattr(self, 'mac_artist_l1'):
            self.mac_artist_l1.set_text(artist)
        if hasattr(self, 'mac_cover_art'):
            self.mac_cover_art.queue_draw()
            
        if state == "Playing":
            self.btn_play.set_label("⏸")
            if hasattr(self, 'sidebar_btn_play'):
                self.sidebar_btn_play.set_label("⏸")
            if hasattr(self, 'mac_btn_play'):
                self.mac_btn_play.set_label("⏸")
            if hasattr(self, 'idle_timer') and self.idle_timer:
                GLib.source_remove(self.idle_timer)
                self.idle_timer = None
                
            if self.current_state != "CompactMedia" and self.current_state != "Media":
                self.change_state("Media", f"{title} - {artist}")
                self.start_collapse_timer()
            elif self.current_state == "CompactMedia" and self.last_media_title != title:
                self.change_state("Media", f"{title} - {artist}")
                self.start_collapse_timer()
            else:
                if self.current_state == "Media":
                    self.change_state("Media", f"{title} - {artist}")
                else:
                    self.change_state("CompactMedia", f"{title} - {artist}")
        else:
            self.btn_play.set_label("▶")
            if hasattr(self, 'sidebar_btn_play'):
                self.sidebar_btn_play.set_label("▶")
            if hasattr(self, 'mac_btn_play'):
                self.mac_btn_play.set_label("▶")
            if not hasattr(self, 'idle_timer') or not self.idle_timer:
                self.idle_timer = GLib.timeout_add(500, self._do_idle_state)
            
    def on_progress(self, position_us, length_us):
        self.current_progress = position_us
        self.current_length = length_us
        
        def format_time(us):
            if not us or us < 0: return "0:00"
            s = int(us / 1000000)
            m = int(s / 60)
            s = s % 60
            return f"{m}:{s:02d}"
            
        time_str = f"{format_time(position_us)} / {format_time(length_us)}"
        if self.media_time_label.get_text() != time_str:
            self.media_time_label.set_text(time_str)
        self.seekbar.queue_draw()
        if hasattr(self, 'sidebar_seekbar'):
            self.sidebar_seekbar.queue_draw()
            
    def on_lyric(self, lyric):
        pass # Handle lyrics later
            
    def on_notif(self, app, summary, body):
        self.change_state("Notify", f"{app}: {summary}")
        GLib.timeout_add(3000, lambda: self._do_collapse() or False)
        
    def on_keylock(self, key_name, state_bool):
        state_str = "ON" if state_bool else "OFF"
        self.change_state("Notify", f"{key_name} {state_str}")
        GLib.timeout_add(2000, lambda: self._do_collapse() or False)
        
    def on_battery_changed(self, status, percentage, time_str="", silent=False):
        self.battery_status = status
        self.battery_percent = percentage
        self.battery_time = time_str
        
        if getattr(self, 'current_state', '') in ("Battery", "CompactBattery"):
            self.battery_widget.queue_draw()
            self.compact_battery_widget.queue_draw()
            
        if not silent:
            self.change_state("Battery", "")
            if hasattr(self, 'battery_timer') and self.battery_timer:
                GLib.source_remove(self.battery_timer)
            self.battery_timer = GLib.timeout_add(3000, lambda: self._do_idle_state() or False)

    def on_mesh_tick(self):
        if getattr(self, 'current_state', '') == "Media":
            self.mesh_phase += 0.015
            if self.mesh_phase > math.pi * 100:
                self.mesh_phase = 0.0
                
            self.wave_phase += 0.15
            if self.wave_phase > math.pi * 100:
                self.wave_phase = 0.0
                
            def lerp_hex(c_hex, t_hex):
                if c_hex == t_hex: return c_hex
                cr, cg, cb = self.hex_to_rgb(c_hex)
                tr, tg, tb = self.hex_to_rgb(t_hex)
                nr = cr + (tr - cr) * 0.1
                ng = cg + (tg - cg) * 0.1
                nb = cb + (tb - cb) * 0.1
                return '#{:02x}{:02x}{:02x}'.format(int(nr*255), int(ng*255), int(nb*255))
                
            self.current_accent = lerp_hex(getattr(self, 'current_accent', '#000000'), getattr(self, 'target_accent', '#000000'))
            self.current_light_accent = lerp_hex(getattr(self, 'current_light_accent', '#000000'), getattr(self, 'target_light_accent', '#000000'))
            
            if getattr(self, 'art_alpha', 1.0) < 1.0:
                self.art_alpha = min(1.0, self.art_alpha + 0.05)
                self.cover_art.queue_draw()
                
            if getattr(self, 'visual_progress', 0) != getattr(self, 'current_progress', 0):
                diff = self.current_progress - self.visual_progress
                self.visual_progress += diff * 0.2
                if abs(self.current_progress - self.visual_progress) < 500000:
                    self.visual_progress = self.current_progress
                self.seekbar.queue_draw()
                
            self.drawing_area.queue_draw()
        return True
        
    def on_system_stats_update(self, stats):
        if getattr(self, 'current_state', '') == "SystemDetails":
            self.sys_labels["ram_used"].set_text(f"Used: {stats['ram_used']}")
            self.sys_labels["ram_free"].set_text(f"Free: {stats['ram_free']}")
            self.sys_labels["ram_total"].set_text(f"Total: {stats['ram_total']}")
            
            self.sys_labels["swap_used"].set_text(f"Used: {stats['swap_used']}")
            self.sys_labels["swap_free"].set_text(f"Free: {stats['swap_free']}")
            self.sys_labels["swap_total"].set_text(f"Total: {stats['swap_total']}")
            
            self.sys_labels["cpu_load"].set_text(f"Load: {stats['cpu_load']}")
            
    def on_seek_event(self, widget, event):
        if self.current_length > 0 and hasattr(self, 'media_monitor'):
            if event.type == Gdk.EventType.BUTTON_PRESS or (event.type == Gdk.EventType.MOTION_NOTIFY and event.get_state() & Gdk.ModifierType.BUTTON1_MASK):
                w = widget.get_allocated_width()
                target_progress = min(1.0, max(0.0, event.x / w))
                target_us = target_progress * self.current_length
                self.visual_progress = target_us
                self.current_progress = target_us
                self.media_monitor.seek(target_us)
                self.seekbar.queue_draw()
        return True
        
    def on_scroll(self, widget, event):
        # Scroll order (UP = previous, DOWN = next):
        if event.direction == Gdk.ScrollDirection.UP:
            if self.current_state == "Media":
                if not self._is_sidebar():
                    self.change_state("MacIsland", "")
                else:
                    self._do_idle_state()
            elif self.current_state == "MacIsland":
                self._do_idle_state()
            elif self.current_state == "SystemDetails":
                if getattr(self, 'last_media_title', None):
                    if hasattr(self, 'idle_timer') and self.idle_timer:
                        GLib.source_remove(self.idle_timer)
                        self.idle_timer = None
                    self.change_state("Media", f"{self.last_media_title} - {self.last_media_artist}")
                else:
                    if not self._is_sidebar():
                        self.change_state("MacIsland", "")
                    else:
                        self._do_idle_state()
            elif self.current_state == "Calendar":
                self.change_state("SystemDetails", "")
            elif self.current_state == "Battery":
                self.change_state("Calendar", "")
        elif event.direction == Gdk.ScrollDirection.DOWN:
            if self.current_state == "Idle":
                if not self._is_sidebar():
                    self.change_state("MacIsland", "")
                else:
                    if getattr(self, 'last_media_title', None):
                        if hasattr(self, 'idle_timer') and self.idle_timer:
                            GLib.source_remove(self.idle_timer)
                            self.idle_timer = None
                        self.change_state("Media", f"{self.last_media_title} - {self.last_media_artist}")
                    else:
                        self.change_state("SystemDetails", "")
            elif self.current_state == "MacIsland":
                if getattr(self, 'last_media_title', None):
                    if hasattr(self, 'idle_timer') and self.idle_timer:
                        GLib.source_remove(self.idle_timer)
                        self.idle_timer = None
                    self.change_state("Media", f"{self.last_media_title} - {self.last_media_artist}")
                else:
                    self.change_state("SystemDetails", "")
            elif self.current_state == "Media":
                self.change_state("SystemDetails", "")
            elif self.current_state == "SystemDetails":
                self.change_state("Calendar", "")
            elif self.current_state == "Calendar":
                self.change_state("Battery", "")
                self.battery_widget.queue_draw()
        return True
        
    def _update_video_frame(self):
        if self.current_state != "MacIsland":
            self.video_timer = None
            return False
            
        if self.video_cap:
            ret, frame = self.video_cap.read()
            if not ret:
                self.video_cap.set(1, 0) # rewind
                ret, frame = self.video_cap.read()
            
            if ret:
                import cv2
                frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                h, w, d = frame.shape
                target_w = self.mac_avatar.get_allocated_width() or 80
                target_h = self.mac_avatar.get_allocated_height() or 80
                
                scale = max(target_w/w, target_h/h)
                new_w, new_h = int(w * scale), int(h * scale)
                frame = cv2.resize(frame, (new_w, new_h))
                
                start_y = (new_h - target_h) // 2
                start_x = (new_w - target_w) // 2
                frame = frame[start_y:start_y+target_h, start_x:start_x+target_w]
                
                rowstride = target_w * 3
                self.current_video_pixbuf = GdkPixbuf.Pixbuf.new_from_data(
                    frame.tobytes(),
                    GdkPixbuf.Colorspace.RGB,
                    False,
                    8,
                    target_w,
                    target_h,
                    rowstride
                )
                self.mac_avatar.queue_draw()
        return True
        
    def on_weather_update(self, data):
        self.w_desc.set_text(data.get("desc", "Unknown"))
        self.w_temp.set_text(data.get("temp", "--°"))
        self.w_hl.set_text(f"L:{data.get('low', '--°')} H:{data.get('high', '--°')}")

if __name__ == "__main__":
    app = DynamicIsland()
    # Set correct initial state based on saved position
    if app._is_sidebar():
        app.island_w = app.SIDEBAR_IDLE_W
        app.island_h = app.SIDEBAR_IDLE_H
        app.border_radius = app.SIDEBAR_IDLE_W / 2.0
        app.drawing_area.set_size_request(app.SIDEBAR_IDLE_W, app.SIDEBAR_IDLE_H + 4)
        app.stack.set_visible_child_name("sidebar_header")
    else:
        app.stack.set_visible_child_name("header")
    app.show_all()
    Gtk.main()

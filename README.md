# Wayland Island

A sleek, fluid, and highly customizable Dynamic Island for Linux desktops (Wayland & X11), built from the ground up with Python, GTK3, and Cairo.

## ✨ Features

- **Built for Linux**: Runs natively on Wayland and X11 compositors via GTK3.
- **Fluid Animations**: Custom-built easing engine (using Expo/Cubic math) powers smooth, iPhone-like expansions and contractions between different UI states.
- **MacIsland Dashboard**: A stunning macOS-inspired expansive layout. Features a 7-day interactive calendar (that smartly pulls your desktop's wallpaper accent color!), full media controls, and a custom looping video avatar powered by OpenCV.
- **Dynamic Media Sync (MPRIS)**: Automatically detects playing music (Spotify, VLC, etc.). The island dynamically extracts the dominant accent color from the live album art to paint the UI, syncs the track progress bar, and natively streams live synchronized lyrics!
- **System Monitoring**: Real-time CPU, RAM, and Swap memory tracking displayed in a sleek, compact horizontal dashboard.
- **Weather & Time Integration**: Automatically updates location-based weather descriptions and live clock telemetry directly on the notch.
- **Advanced Graphics Processing**: Utilizes custom Cairo-drawn non-rectangular clipping paths and frosted-black backgrounds with alpha blending to simulate a premium hardware bezel.

## 📸 Overview

The island sits quietly at the top of your screen as a minimal, rounded capsule holding the clock and tiny indicators. When you play music, check system stats, or trigger the dashboard, it beautifully expands using hardware-accelerated GTK drawing algorithms. 

Every UI element is crafted to feel premium—from the 10px rounded album covers to the precisely clipped avatar circles and dynamically color-matched typography.

## 🚀 Installation & Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/rajsriv/wayland-Island.git
   cd wayland-Island
   ```

2. **Set up a Virtual Environment (Recommended):**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```

3. **Install Dependencies:**
   Make sure you have system packages for GTK3, Cairo, and Python-GObject (`python3-gi`, `gir1.2-gtk-3.0`, `libcairo2-dev`).
   Then, install the python packages:
   ```bash
   pip install dbus-next psutil requests Pillow opencv-python colorgram.py pycairo PyGObject
   ```

4. **Install to System (Autostart & App Launcher):**
   Run the installation script to dynamically generate your desktop shortcuts and configure autostart.
   ```bash
   chmod +x install.sh
   ./install.sh
   ```
   
   Once installed, the island will start automatically on boot. You can also run it immediately by finding **Wayland Island** in your app launcher!

## 🛠 Architecture

- `gtk_main.py`: The heart of the application. Manages the GTK Window, Cairo drawing loop, State Machine (Idle, MacIsland, Media, SystemDetails), and Animation Group tweening.
- `media_monitor.py`: A robust async DBUS monitor utilizing `dbus-next` to hook into `org.mpris.MediaPlayer2` to fetch metadata, album art, position, and lyrics.
- `system_monitor.py`: Threaded backend tracking `psutil` metrics for CPU and Memory without blocking the main GTK thread.
- `app_styles.py`: Centralized CSS architecture injected natively into the GTK `CssProvider` to enforce typography, margins, and the frosted-black aesthetic.

## 🤝 Contributing

Feel free to fork this project, submit pull requests, and contribute new "States" for the island to support!

## 📜 License

[MIT License](LICENSE)

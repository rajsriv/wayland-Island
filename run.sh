#!/bin/bash
# Wait for the Wayland/X11 compositor to be fully initialized on boot
sleep 3
cd "$(dirname "$0")"
source .venv/bin/activate
python gtk_main.py

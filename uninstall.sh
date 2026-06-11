#!/bin/bash

echo "🗑️  Uninstalling Wayland Island..."

# 1. Remove from App Launcher
if [ -f ~/.local/share/applications/wayland-island.desktop ]; then
    rm ~/.local/share/applications/wayland-island.desktop
    echo "✅ Removed from Application Launcher."
else
    echo "⚠️  App Launcher shortcut not found. Skipping..."
fi

# 2. Remove from Autostart
if [ -f ~/.config/autostart/wayland-island.desktop ]; then
    rm ~/.config/autostart/wayland-island.desktop
    echo "✅ Removed from Autostart."
else
    echo "⚠️  Autostart shortcut not found. Skipping..."
fi

echo "✨ Uninstall complete!"
echo "If you want to fully delete the app, you can now safely delete the wayland-Island folder."

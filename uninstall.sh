#!/bin/bash

echo "🗑️  Uninstalling Wayland Island..."

# Helper function for y/n prompts
ask_user() {
    while true; do
        read -p "$1 [y/N]: " yn
        case $yn in
            [Yy]* ) return 0;;
            [Nn]* | "" ) return 1;;
            * ) echo "Please answer yes or no (or hit enter for No).";;
        esac
    done
}

# 1. Remove from App Launcher
if [ -f ~/.local/share/applications/wayland-island.desktop ]; then
    if ask_user "📦 Remove shortcut from Application Launcher?"; then
        rm ~/.local/share/applications/wayland-island.desktop
        echo "✅ Removed from Application Launcher."
    else
        echo "⏭️  Skipping Application Launcher removal."
    fi
else
    echo "⚠️  App Launcher shortcut not found. Skipping..."
fi

# 2. Remove from Autostart
if [ -f ~/.config/autostart/wayland-island.desktop ]; then
    if ask_user "⚙️  Remove shortcut from Autostart menu?"; then
        rm ~/.config/autostart/wayland-island.desktop
        echo "✅ Removed from Autostart."
    else
        echo "⏭️  Skipping Autostart removal."
    fi
else
    echo "⚠️  Autostart shortcut not found. Skipping..."
fi

echo ""
echo "✨ Uninstall complete!"
echo "If you want to fully delete the app, you can now safely delete the wayland-Island folder."

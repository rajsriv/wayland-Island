#!/bin/bash

echo "🚀 Installing Wayland Island..."

# 1. Get the absolute path of the current directory
INSTALL_DIR=$(pwd)

# 2. Check if virtual environment exists
if [ ! -d "$INSTALL_DIR/.venv" ]; then
    echo "⚠️  No virtual environment found at $INSTALL_DIR/.venv"
    echo "Please create it and install dependencies first."
    exit 1
fi

# 3. Create the Desktop Entry
echo "📝 Creating Desktop Entry..."
cat << EOF > wayland-island.desktop
[Desktop Entry]
Name=Wayland Island
Comment=Dynamic Island for Linux
Exec=bash -c "cd '$INSTALL_DIR' && source .venv/bin/activate && python gtk_main.py"
Icon=utilities-system-monitor
Terminal=false
Type=Application
Categories=Utility;
X-GNOME-Autostart-enabled=true
EOF

# 4. "Install" it so it appears in the App Launcher
echo "📦 Installing to Application Launcher..."
mkdir -p ~/.local/share/applications
cp wayland-island.desktop ~/.local/share/applications/

# 5. "Install" it to run automatically on boot
echo "⚙️  Configuring autostart on boot..."
mkdir -p ~/.config/autostart
cp wayland-island.desktop ~/.config/autostart/

echo "✅ Wayland Island installed successfully!"
echo "It will now appear in your app launcher and start automatically when you log in."

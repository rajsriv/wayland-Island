#!/bin/bash

echo "🚀 Installing Wayland Island..."

INSTALL_DIR=$(pwd)

if [ ! -d "$INSTALL_DIR/.venv" ]; then
    echo "⚠️  No virtual environment found at $INSTALL_DIR/.venv"
    echo "Please create it and install dependencies first."
    exit 1
fi

echo "🔧 Creating launch wrapper script..."
cat << 'EOF' > run.sh
#!/bin/bash
cd "$(dirname "$0")"
source .venv/bin/activate
python gtk_main.py
EOF
chmod +x run.sh

echo "📝 Creating Desktop Entry..."
cat << EOF > wayland-island.desktop
[Desktop Entry]
Name=Wayland Island
Comment=Dynamic Island for Linux
Exec="$INSTALL_DIR/run.sh"
Icon=utilities-system-monitor
Terminal=false
Type=Application
Categories=Utility;
X-GNOME-Autostart-enabled=true
EOF

echo "📦 Installing to Application Launcher..."
mkdir -p ~/.local/share/applications
cp wayland-island.desktop ~/.local/share/applications/

echo "⚙️  Configuring autostart on boot..."
mkdir -p ~/.config/autostart
cp wayland-island.desktop ~/.config/autostart/

echo "✅ Wayland Island installed successfully!"
echo "It will now appear in your app launcher and start automatically when you log in."

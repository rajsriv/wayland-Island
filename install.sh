#!/bin/bash

echo "🚀 Installing Wayland Island..."

INSTALL_DIR=$(pwd)

# 2. Check if virtual environment exists
if [ ! -d "$INSTALL_DIR/.venv" ]; then
    echo "⚙️  No virtual environment found. Creating one now..."
    python3 -m venv .venv
    echo "📦 Installing requirements..."
    source .venv/bin/activate
    pip install -r requirements.txt
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

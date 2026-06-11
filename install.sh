#!/bin/bash

echo "🚀 Installing Wayland Island..."

INSTALL_DIR=$(pwd)

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

# 1. Check if virtual environment exists
if [ ! -d "$INSTALL_DIR/.venv" ]; then
    if ask_user "⚙️  No virtual environment found. Create one and install dependencies?"; then
        echo "⚙️  Creating virtual environment..."
        python3 -m venv --system-site-packages .venv
        echo "📦 Installing requirements..."
        source .venv/bin/activate
        pip install -r requirements.txt
    else
        echo "⏭️  Skipping virtual environment setup."
    fi
fi

# 2. Create wrapper script and desktop entry locally
if ask_user "🔧 Generate run.sh and desktop entry files in this directory?"; then
    echo "🔧 Creating launch wrapper script..."
    cat << 'EOF' > run.sh
#!/bin/bash
# Wait for the Wayland/X11 compositor to be fully initialized on boot
sleep 3
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
else
    echo "⏭️  Skipping script generation."
fi

# 3. Add to Application Launcher
if ask_user "📦 Install shortcut to Application Launcher so it appears in your system menu?"; then
    echo "📦 Installing to Application Launcher..."
    mkdir -p ~/.local/share/applications
    cp wayland-island.desktop ~/.local/share/applications/
else
    echo "⏭️  Skipping Application Launcher installation."
fi

# 4. Add to Autostart
if ask_user "⚙️  Configure autostart so it launches automatically on boot?"; then
    echo "⚙️  Configuring autostart on boot..."
    mkdir -p ~/.config/autostart
    cp wayland-island.desktop ~/.config/autostart/
else
    echo "⏭️  Skipping autostart configuration."
fi

echo ""
echo "✅ Setup complete!"

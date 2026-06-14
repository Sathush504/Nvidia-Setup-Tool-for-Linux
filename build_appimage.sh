#!/bin/bash
set -e

echo "=== Preparing AppDir ==="
APPDIR="nvidia-setup.AppDir"
rm -rf "$APPDIR"
mkdir -p "$APPDIR/usr/bin"

# Copy pyinstaller files
echo "Copying PyInstaller files..."
cp -r dist/nvidia-setup/* "$APPDIR/usr/bin/"

# Copy icon
echo "Setting up application icon..."
ICON_SRC="/home/rudy/.gemini/antigravity/brain/f5e2f88a-10bc-4dbb-8fda-1656afe967d0/nvidia_setup_icon_1781475497911.png"
if [ -f "$ICON_SRC" ]; then
    cp "$ICON_SRC" "$APPDIR/nvidia-setup.png"
else
    # Fallback to a blank touch if missing
    touch "$APPDIR/nvidia-setup.png"
fi

# Create desktop file
echo "Creating desktop entry..."
cat << 'EOF' > "$APPDIR/nvidia-setup.desktop"
[Desktop Entry]
Version=1.0
Type=Application
Name=NVIDIA GPU Setup Tool
Comment=Install NVIDIA drivers and CUDA toolkit
Exec=nvidia-setup
Icon=nvidia-setup
Terminal=false
Categories=System;Settings;HardwareSettings;
Keywords=NVIDIA;GPU;Driver;CUDA;Installation;
StartupNotify=true
EOF

# Create AppRun script
echo "Creating AppRun launcher..."
cat << 'EOF' > "$APPDIR/AppRun"
#!/bin/sh
SELF=$(readlink -f "$0")
HERE=$(dirname "$SELF")
exec "$HERE/usr/bin/nvidia-setup" "$@"
EOF
chmod +x "$APPDIR/AppRun"

# Download appimagetool
echo "=== Downloading appimagetool ==="
if [ ! -f "appimagetool-x86_64.AppImage" ]; then
    wget -q --show-progress -O appimagetool-x86_64.AppImage https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-x86_64.AppImage
    chmod +x appimagetool-x86_64.AppImage
fi

# Package AppImage
echo "=== Packaging AppImage ==="
export ARCH=x86_64
./appimagetool-x86_64.AppImage --appimage-extract-and-run "$APPDIR" nvidia-setup-x86_64.AppImage

# Clean up
echo "=== Cleaning up ==="
rm -rf "$APPDIR"
rm -f appimagetool-x86_64.AppImage

echo "=== AppImage build successful: nvidia-setup-x86_64.AppImage ==="

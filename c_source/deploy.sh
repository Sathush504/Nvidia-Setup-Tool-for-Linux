#!/bin/bash

# NVIDIA GPU Setup Tool - Deployment Script
# Creates a deployment package ready for distribution

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Configuration
PACKAGE_NAME="nvidia-setup-tool"
VERSION="1.0"
ARCH="x86_64"
DISTRO="ubuntu-debian"

# Create deployment directory
DEPLOY_DIR="${PACKAGE_NAME}-${VERSION}-${DISTRO}-${ARCH}"
PACKAGE_FILE="${PACKAGE_NAME}-${VERSION}-${DISTRO}-${ARCH}.tar.gz"

print_status "Creating deployment package: $PACKAGE_FILE"

# Clean previous builds
print_status "Cleaning previous builds..."
make clean 2>/dev/null || true
rm -rf "$DEPLOY_DIR" "$PACKAGE_FILE" 2>/dev/null || true

# Create deployment directory structure
print_status "Creating deployment directory structure..."
mkdir -p "$DEPLOY_DIR"

# Copy source files
print_status "Copying source files..."
cp nlinux.c "$DEPLOY_DIR/"
cp Makefile "$DEPLOY_DIR/"
cp install.sh "$DEPLOY_DIR/"
cp README.md "$DEPLOY_DIR/"
cp nvidia-setup-tool.desktop "$DEPLOY_DIR/"
cp .gitignore "$DEPLOY_DIR/"

# Build the application
print_status "Building application..."
make clean
make

# Copy built executable
cp nvidia-setup-tool "$DEPLOY_DIR/"

# Create installation script
print_status "Creating installation script..."
cat > "$DEPLOY_DIR/INSTALL" << 'EOF'
#!/bin/bash
# Quick installation script for NVIDIA GPU Setup Tool

echo "NVIDIA GPU Setup Tool - Quick Install"
echo "====================================="
echo ""

# Check if running as root
if [[ $EUID -eq 0 ]]; then
    echo "ERROR: This script should not be run as root (sudo)."
    echo "Please run it as a regular user. The script will request sudo when needed."
    exit 1
fi

# Make install script executable
chmod +x install.sh

# Run the installation
echo "Starting installation..."
./install.sh

echo ""
echo "Installation completed!"
echo "You can now run: nvidia-setup-tool"
EOF

chmod +x "$DEPLOY_DIR/INSTALL"

# Create uninstall script
print_status "Creating uninstall script..."
cat > "$DEPLOY_DIR/UNINSTALL" << 'EOF'
#!/bin/bash
# Uninstall script for NVIDIA GPU Setup Tool

echo "NVIDIA GPU Setup Tool - Uninstall"
echo "================================="
echo ""

# Remove system installation
if [[ -f "/usr/local/bin/nvidia-setup-tool" ]]; then
    echo "Removing system installation..."
    sudo rm -f /usr/local/bin/nvidia-setup-tool
fi

# Remove desktop entry
if [[ -f "$HOME/.local/share/applications/nvidia-setup-tool.desktop" ]]; then
    echo "Removing desktop entry..."
    rm -f "$HOME/.local/share/applications/nvidia-setup-tool.desktop"
fi

echo "Uninstallation completed!"
EOF

chmod +x "$DEPLOY_DIR/UNINSTALL"

# Create version info file
print_status "Creating version information..."
cat > "$DEPLOY_DIR/VERSION" << EOF
NVIDIA GPU Setup Tool
Version: $VERSION
Architecture: $ARCH
Distribution: $DISTRO
Build Date: $(date)
Build System: $(uname -s) $(uname -r)
Compiler: $(gcc --version | head -n1)
EOF

# Create package info
print_status "Creating package information..."
cat > "$DEPLOY_DIR/PACKAGE_INFO" << EOF
Package: $PACKAGE_NAME
Version: $VERSION
Architecture: $ARCH
Distribution: $DISTRO
Maintainer: NVIDIA GPU Setup Tool Team
Description: User-friendly GUI application for installing NVIDIA drivers and CUDA toolkit
Homepage: https://github.com/your-repo/nvidia-setup-tool
License: Open Source
Depends: build-essential, pkg-config, libgtk-3-dev, libglib2.0-dev
Recommends: sudo
Section: system
Priority: optional
EOF

# Create checksums
print_status "Creating checksums..."
cd "$DEPLOY_DIR"
find . -type f -exec md5sum {} \; > CHECKSUMS.md5
cd ..

# Create the tarball
print_status "Creating deployment package..."
tar -czf "$PACKAGE_FILE" "$DEPLOY_DIR"

# Calculate package size and checksum
PACKAGE_SIZE=$(du -h "$PACKAGE_FILE" | cut -f1)
PACKAGE_CHECKSUM=$(md5sum "$PACKAGE_FILE" | cut -d' ' -f1)

# Clean up deployment directory
rm -rf "$DEPLOY_DIR"

print_success "Deployment package created successfully!"
echo ""
echo "Package Details:"
echo "  File: $PACKAGE_FILE"
echo "  Size: $PACKAGE_SIZE"
echo "  MD5:  $PACKAGE_CHECKSUM"
echo ""
echo "Package Contents:"
echo "  - nlinux.c (source code)"
echo "  - Makefile (build system)"
echo "  - install.sh (installation script)"
echo "  - README.md (documentation)"
echo "  - nvidia-setup-tool (executable)"
echo "  - nvidia-setup-tool.desktop (desktop entry)"
echo "  - INSTALL (quick install script)"
echo "  - UNINSTALL (uninstall script)"
echo "  - VERSION (version information)"
echo "  - PACKAGE_INFO (package metadata)"
echo "  - CHECKSUMS.md5 (file checksums)"
echo ""
echo "To deploy:"
echo "  1. Extract: tar -xzf $PACKAGE_FILE"
echo "  2. Install: cd $DEPLOY_DIR && ./INSTALL"
echo ""
echo "To test locally:"
echo "  ./nvidia-setup-tool"

#!/bin/bash

# NVIDIA GPU Setup Tool - Installation Script
# This script automatically installs dependencies and builds the application

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
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

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to check if running as root
check_root() {
    if [[ $EUID -eq 0 ]]; then
        print_error "This script should not be run as root (sudo)."
        print_error "Please run it as a regular user. The script will request sudo when needed."
        exit 1
    fi
}

# Function to check system compatibility
check_system() {
    print_status "Checking system compatibility..."
    
    # Check if running on Linux
    if [[ "$OSTYPE" != "linux-gnu"* ]]; then
        print_error "This tool is designed for Linux systems only."
        exit 1
    fi
    
    # Check if running on Ubuntu/Debian
    if ! command_exists apt-get; then
        print_warning "This tool is optimized for Ubuntu/Debian systems."
        print_warning "Other distributions may require manual dependency installation."
    fi
    
    # Check architecture
    if [[ "$(uname -m)" != "x86_64" ]]; then
        print_warning "This tool is tested on x86_64 architecture."
        print_warning "Other architectures may work but are not guaranteed."
    fi
    
    print_success "System compatibility check passed"
}

# Function to install dependencies
install_dependencies() {
    print_status "Installing required dependencies..."
    
    if command_exists apt-get; then
        print_status "Updating package lists..."
        sudo apt-get update
        
        print_status "Installing build tools and GTK3 development libraries..."
        sudo apt-get install -y build-essential pkg-config libgtk-3-dev libglib2.0-dev
        
        print_success "Dependencies installed successfully"
    else
        print_warning "apt-get not found. Please install the following packages manually:"
        print_warning "- build-essential"
        print_warning "- pkg-config"
        print_warning "- libgtk-3-dev"
        print_warning "- libglib2.0-dev"
        print_warning "- libpthread-stubs0-dev"
        
        read -p "Press Enter after installing dependencies manually..."
    fi
}

# Function to check dependencies
check_dependencies() {
    print_status "Checking if all dependencies are installed..."
    
    local missing_deps=()
    
    # Check for required commands
    if ! command_exists gcc; then
        missing_deps+=("gcc")
    fi
    
    if ! command_exists pkg-config; then
        missing_deps+=("pkg-config")
    fi
    
    # Check for GTK3 libraries
    if ! pkg-config --exists gtk+-3.0 2>/dev/null; then
        missing_deps+=("libgtk-3-dev")
    fi
    
    if ! pkg-config --exists glib-2.0 2>/dev/null; then
        missing_deps+=("libglib2.0-dev")
    fi
    
    if [[ ${#missing_deps[@]} -gt 0 ]]; then
        print_error "Missing dependencies: ${missing_deps[*]}"
        print_status "Installing missing dependencies..."
        install_dependencies
    else
        print_success "All dependencies are installed"
    fi
}

# Function to build the application
build_application() {
    print_status "Building NVIDIA GPU Setup Tool..."
    
    if [[ -f "Makefile" ]]; then
        print_status "Using Makefile for build..."
        make clean 2>/dev/null || true
        make
    else
        print_status "Building manually..."
        gcc -Wall -Wextra -std=c99 -O2 -o nvidia-setup-tool nlinux.c \
            $(pkg-config --cflags --libs gtk+-3.0) -lpthread
    fi
    
    if [[ -f "nvidia-setup-tool" ]]; then
        chmod +x nvidia-setup-tool
        print_success "Application built successfully"
    else
        print_error "Build failed. Please check the error messages above."
        exit 1
    fi
}

# Function to install the application
install_application() {
    print_status "Installing NVIDIA GPU Setup Tool..."
    
    # Create desktop entry
    local desktop_dir="$HOME/.local/share/applications"
    local desktop_file="$desktop_dir/nvidia-setup-tool.desktop"
    
    mkdir -p "$desktop_dir"
    
    cat > "$desktop_file" << EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=NVIDIA GPU Setup Tool
Comment=Install NVIDIA drivers and CUDA toolkit
Exec=$(pwd)/nvidia-setup-tool
Icon=video-display
Terminal=false
Categories=System;Settings;HardwareSettings;
Keywords=NVIDIA;GPU;Driver;CUDA;Installation;
EOF
    
    chmod +x "$desktop_file"
    
    print_success "Application installed successfully"
    print_success "Desktop entry created at: $desktop_file"
}

# Function to show usage information
show_usage() {
    echo "NVIDIA GPU Setup Tool - Installation Script"
    echo "==========================================="
    echo ""
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  -h, --help     Show this help message"
    echo "  -d, --deps     Install dependencies only"
    echo "  -b, --build    Build application only"
    echo "  -i, --install  Install with desktop entry"
    echo "  -a, --all      Full installation (default)"
    echo ""
    echo "Examples:"
    echo "  $0              # Full installation"
    echo "  $0 --deps       # Install dependencies only"
    echo "  $0 --build      # Build application only"
    echo ""
}

# Main installation function
main_installation() {
    print_status "Starting NVIDIA GPU Setup Tool installation..."
    
    check_root
    check_system
    check_dependencies
    build_application
    install_application
    
    print_success "Installation completed successfully!"
    echo ""
    echo "You can now:"
    echo "1. Find 'NVIDIA GPU Setup Tool' in your applications menu"
    echo "2. Run it from terminal: ./nvidia-setup-tool"
    echo "3. Double-click the desktop icon to launch"
    echo ""
    echo "The application will help you install NVIDIA drivers and CUDA toolkit."
    echo "Make sure you have sudo access when running the tool."
}

# Parse command line arguments
case "${1:-}" in
    -h|--help)
        show_usage
        exit 0
        ;;
    -d|--deps)
        check_root
        check_system
        install_dependencies
        exit 0
        ;;
    -b|--build)
        check_dependencies
        build_application
        exit 0
        ;;
    -i|--install)
        if [[ ! -f "nvidia-setup-tool" ]]; then
            print_error "Application not built. Run with --build first."
            exit 1
        fi
        install_application
        exit 0
        ;;
    -a|--all|"")
        main_installation
        ;;
    *)
        print_error "Unknown option: $1"
        show_usage
        exit 1
        ;;
esac

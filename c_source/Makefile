# Makefile for NVIDIA GPU Setup Tool
# A user-friendly GUI application for installing NVIDIA drivers and CUDA toolkit

# Compiler and flags
CC = gcc
CFLAGS = -Wall -Wextra -std=c99 -O2
GTK_CFLAGS = $(shell pkg-config --cflags gtk+-3.0)
GTK_LIBS = $(shell pkg-config --libs gtk+-3.0)
LIBS = -lpthread

# Target executable
TARGET = nvidia-setup-tool

# Source files
SOURCES = nlinux.c

# Default target
all: $(TARGET)

# Compile the application
$(TARGET): $(SOURCES)
	@echo "Compiling NVIDIA GPU Setup Tool..."
	$(CC) $(CFLAGS) $(GTK_CFLAGS) -o $@ $^ $(GTK_LIBS) $(LIBS)
	@echo "Compilation completed successfully!"
	@echo "Run './$(TARGET)' to start the application"

# Install dependencies (Ubuntu/Debian)
install-deps:
	@echo "Installing required dependencies..."
	sudo apt-get update
	sudo apt-get install -y build-essential pkg-config libgtk-3-dev libglib2.0-dev
	@echo "Dependencies installed successfully!"

# Install the application system-wide
install: $(TARGET)
	@echo "Installing NVIDIA GPU Setup Tool..."
	sudo cp $(TARGET) /usr/local/bin/
	sudo chmod +x /usr/local/bin/$(TARGET)
	@echo "Application installed to /usr/local/bin/$(TARGET)"

# Create desktop entry
install-desktop: install
	@echo "Creating desktop entry..."
	@mkdir -p ~/.local/share/applications
	@echo "[Desktop Entry]" > ~/.local/share/applications/nvidia-setup-tool.desktop
	@echo "Version=1.0" >> ~/.local/share/applications/nvidia-setup-tool.desktop
	@echo "Type=Application" >> ~/.local/share/applications/nvidia-setup-tool.desktop
	@echo "Name=NVIDIA GPU Setup Tool" >> ~/.local/share/applications/nvidia-setup-tool.desktop
	@echo "Comment=Install NVIDIA drivers and CUDA toolkit" >> ~/.local/share/applications/nvidia-setup-tool.desktop
	@echo "Exec=/usr/local/bin/$(TARGET)" >> ~/.local/share/applications/nvidia-setup-tool.desktop
	@echo "Icon=video-display" >> ~/.local/share/applications/nvidia-setup-tool.desktop
	@echo "Terminal=false" >> ~/.local/share/applications/nvidia-setup-tool.desktop
	@echo "Categories=System;Settings;HardwareSettings;" >> ~/.local/share/applications/nvidia-setup-tool.desktop
	@echo "Keywords=NVIDIA;GPU;Driver;CUDA;Installation;" >> ~/.local/share/applications/nvidia-setup-tool.desktop
	@echo "Desktop entry created successfully!"
	@echo "You can now find the application in your applications menu"

# Uninstall the application
uninstall:
	@echo "Uninstalling NVIDIA GPU Setup Tool..."
	sudo rm -f /usr/local/bin/$(TARGET)
	rm -f ~/.local/share/applications/nvidia-setup-tool.desktop
	@echo "Application uninstalled successfully!"

# Clean build files
clean:
	@echo "Cleaning build files..."
	rm -f $(TARGET)
	@echo "Cleanup completed!"

# Check if dependencies are installed
check-deps:
	@echo "Checking dependencies..."
	@pkg-config --exists gtk+-3.0 && echo "✓ GTK3 development libraries found" || echo "✗ GTK3 development libraries missing"
	@echo "Run 'make install-deps' to install missing dependencies"

# Run the application
run: $(TARGET)
	@echo "Starting NVIDIA GPU Setup Tool..."
	./$(TARGET)

# Help target
help:
	@echo "NVIDIA GPU Setup Tool - Build System"
	@echo "===================================="
	@echo ""
	@echo "Available targets:"
	@echo "  all              - Build the application (default)"
	@echo "  install-deps     - Install required dependencies"
	@echo "  install          - Install the application system-wide"
	@echo "  install-desktop  - Install application and create desktop entry"
	@echo "  uninstall        - Remove the application"
	@echo "  clean            - Remove build files"
	@echo "  check-deps       - Check if dependencies are installed"
	@echo "  run              - Build and run the application"
	@echo "  help             - Show this help message"
	@echo ""
	@echo "Quick start:"
	@echo "  1. make install-deps    # Install dependencies"
	@echo "  2. make                 # Build the application"
	@echo "  3. make run             # Run the application"
	@echo "  4. make install-desktop # Install with desktop entry"

.PHONY: all install-deps install install-desktop uninstall clean check-deps run help

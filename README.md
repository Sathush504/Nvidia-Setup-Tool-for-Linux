# NVIDIA GPU Setup Tool

A user-friendly desktop application for Ubuntu/Debian Linux that automatically detects, installs, and configures NVIDIA GPU drivers and CUDA toolkit.

## Features

- **Automatic Detection**: Automatically detects NVIDIA GPUs in your system
- **Driver Installation**: Installs the latest proprietary NVIDIA drivers
- **CUDA Toolkit**: Optional installation of CUDA toolkit with environment setup
- **Modern GUI**: Beautiful GTK3-based interface with real-time progress tracking
- **Status Monitoring**: Real-time status updates and detailed logging
- **Progress Tracking**: Visual progress bar and console output
- **Error Handling**: Comprehensive error handling with user-friendly messages
- **Secure**: Proper sudo authentication and privilege management

## Screenshots

The application features a modern, dark-themed interface with:
- System status cards showing GPU, driver, and CUDA information
- Installation options with checkboxes
- Real-time progress bar and console output
- Professional styling with NVIDIA brand colors

## Requirements

- **Operating System**: Ubuntu 20.04+ or Debian 11+
- **Architecture**: x86_64 (64-bit)
- **Dependencies**: GTK3 development libraries, build tools
- **Privileges**: Sudo access for package installation

## Quick Installation

### 1. Install Dependencies

```bash
# Update package lists
sudo apt-get update

# Install required packages
sudo apt-get install -y build-essential pkg-config libgtk-3-dev libglib2.0-dev
```

### 2. Build and Install

```bash
# Clone or download the source code
# Navigate to the project directory
cd /path/to/nvidia-setup-tool

# Build the application
make

# Install system-wide with desktop entry
make install-desktop
```

### 3. Run the Application

The application will now appear in your applications menu as "NVIDIA GPU Setup Tool", or you can run it from terminal:

```bash
nvidia-setup-tool
```

## Manual Installation

If you prefer to build manually:

```bash
# Compile the application
gcc -Wall -Wextra -std=c99 -O2 -o nvidia-setup-tool nlinux.c \
    $(pkg-config --cflags --libs gtk+-3.0) -lpthread

# Make executable
chmod +x nvidia-setup-tool

# Run
./nvidia-setup-tool
```

## Usage

### 1. Launch the Application

Double-click the "NVIDIA GPU Setup Tool" icon from your applications menu, or run it from terminal.

### 2. System Detection

The application automatically detects your system components:
- **GPU Detection**: Uses `lspci` to find NVIDIA GPUs
- **Driver Status**: Checks if NVIDIA drivers are installed using `nvidia-smi`
- **CUDA Status**: Verifies CUDA installation with `nvcc --version`

### 3. Installation Options

Choose what to install:
- **NVIDIA Driver**: Latest proprietary driver (recommended)
- **CUDA Toolkit**: Complete CUDA development environment

### 4. Start Installation

Click "⚡︎ Start Installation" to begin. The application will:
- Request sudo password for authentication
- Update package repositories
- Install prerequisites
- Add NVIDIA repositories
- Install selected components
- Configure environment variables (if CUDA selected)

### 5. Post-Installation

After successful installation:
- **Reboot Required**: Restart your system for changes to take effect
- **Verification**: Use `nvidia-smi` and `nvcc --version` to verify installation
- **Environment**: CUDA paths are automatically added to your `.bashrc`

## What Gets Installed

### NVIDIA Driver
- Latest proprietary NVIDIA driver (currently driver-535)
- Graphics drivers PPA repository
- DKMS support for kernel modules

### CUDA Toolkit
- Complete CUDA development environment
- NVIDIA CUDA repository
- Environment variables setup:
  - `PATH=/usr/local/cuda/bin:$PATH`
  - `LD_LIBRARY_PATH=/usr/local/cuda/lib64:$LD_LIBRARY_PATH`

### Prerequisites
- `software-properties-common`
- `apt-transport-https`
- `ca-certificates`
- `curl`, `wget`, `gnupg`
- `build-essential`, `dkms`

## Troubleshooting

### Common Issues

**1. GTK3 Libraries Not Found**
```bash
sudo apt-get install libgtk-3-dev libglib2.0-dev
```

**2. Compilation Errors**
```bash
# Check dependencies
make check-deps

# Install missing dependencies
make install-deps
```

**3. Permission Denied**
- Ensure you have sudo access
- Check if the application is executable: `chmod +x nvidia-setup-tool`

**4. Installation Fails**
- Check internet connection
- Verify sudo password is correct
- Review console output for specific error messages
- Ensure system is up to date: `sudo apt-get update && sudo apt-get upgrade`

### Logs and Debugging

The application provides detailed logging in the console output. Common log messages:
- `INFO`: General information and progress updates
- `SUCCESS`: Successful operations
- `WARNING`: Non-critical issues
- `ERROR`: Failed operations

## Development

### Building from Source

```bash
# Clone repository
git clone <repository-url>
cd nvidia-setup-tool

# Install dependencies
make install-deps

# Build
make

# Run
make run
```

### Project Structure

```
nvidia-setup-tool/
├── nlinux.c          # Main application source code
├── Makefile          # Build system
├── README.md         # This file
└── .gitignore        # Git ignore rules
```

### Key Components

- **GTK3 GUI**: Modern desktop interface
- **Multi-threading**: Background installation and detection
- **System Integration**: Package management and system commands
- **Error Handling**: Comprehensive error reporting
- **Progress Tracking**: Real-time installation progress

## Contributing

Contributions are welcome! Please ensure:
- Code follows C99 standard
- GTK3 best practices are followed
- Error handling is comprehensive
- User experience remains simple and intuitive

## License

This project is open source. Please check the license file for details.

## Support

For issues and questions:
1. Check the troubleshooting section above
2. Review console output for error details
3. Ensure system meets requirements
4. Check if dependencies are properly installed

## Version History

- **v1.0**: Initial release with GPU detection, driver installation, and CUDA support

---

**Note**: This tool requires sudo privileges to install system packages. Always review what will be installed before proceeding. The tool is designed for Ubuntu/Debian systems and may require modifications for other distributions.

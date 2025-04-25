#!/usr/bin/env python3
"""
iPhone Photo Converter - Unified Setup Script
This script combines installation, launcher creation, and standalone executable building.
"""
import os
import sys
import platform
import subprocess
import shutil
import tempfile
import urllib.request
import time
import argparse
from pathlib import Path

# Constants
PYTHON_VERSION = "3.10.0"
WINDOWS_PYTHON_URL = f"https://www.python.org/ftp/python/{PYTHON_VERSION}/python-{PYTHON_VERSION}-amd64.exe"
APP_NAME = "iPhone Photo Converter"
APP_VERSION = "1.0.0"

def print_header(title):
    """Print a formatted header."""
    print("\n" + "=" * 60)
    print(f" {title} ".center(60, "="))
    print("=" * 60 + "\n")

def is_python_installed():
    """Check if Python is installed and accessible."""
    try:
        if platform.system() == "Windows":
            result = subprocess.run(["where", "python"], 
                                   stdout=subprocess.PIPE, 
                                   stderr=subprocess.PIPE)
            return result.returncode == 0
        else:
            result = subprocess.run(["which", "python3"], 
                                   stdout=subprocess.PIPE, 
                                   stderr=subprocess.PIPE)
            return result.returncode == 0
    except:
        return False

def install_dependencies():
    """Install required dependencies."""
    print("Installing dependencies...")
    
    # Core dependencies for all platforms
    core_dependencies = [
        'pillow',
        'pillow-heif',
        'piexif',
        'regex',
        'pyqt6',
    ]
    
    # Install core dependencies first
    try:
        print("Installing core dependencies...")
        if platform.system() == "Windows":
            subprocess.run([sys.executable, "-m", "pip", "install", *core_dependencies], check=True)
        else:
            subprocess.run([sys.executable, "-m", "pip", "install", *core_dependencies], check=True)
        print("Core dependencies installed successfully!")
    except subprocess.CalledProcessError as e:
        print(f"Error installing core dependencies: {e}")
        print("You may need to install these manually: " + ", ".join(core_dependencies))
        return False
    
    # Platform-specific dependencies
    try:
        print("Installing platform-specific dependencies...")
        if platform.system() == 'Darwin':  # macOS
            # Using pyusb instead of pyobjc-framework-libusb which may be unavailable
            macos_deps = ['pyusb']
            subprocess.run([sys.executable, "-m", "pip", "install", *macos_deps], check=True)
            print("Note: On macOS, you might need to install libusb with Homebrew:")
            print("brew install libusb")
        elif platform.system() == 'Windows':
            windows_deps = ['pyusb', 'libusb-package', 'wmi']
            subprocess.run([sys.executable, "-m", "pip", "install", *windows_deps], check=True)
        else:  # Linux
            linux_deps = ['pyusb']
            subprocess.run([sys.executable, "-m", "pip", "install", *linux_deps], check=True)
            print("Note: On Linux, you might need to install libusb development package:")
            print("Ubuntu/Debian: sudo apt-get install libusb-1.0-0-dev")
            print("Fedora: sudo dnf install libusb-devel")
        
        print("Platform-specific dependencies installed successfully!")
    except subprocess.CalledProcessError as e:
        print(f"Warning: Some platform-specific dependencies could not be installed: {e}")
        print("This might affect USB device detection, but the application should still work for basic functionality.")
    
    return True

def install_python_windows():
    """Download and install Python on Windows."""
    print("Python not found. Downloading and installing Python...")
    
    # Create a temporary directory and download the installer
    temp_dir = tempfile.mkdtemp()
    installer_path = os.path.join(temp_dir, "python_installer.exe")
    
    print(f"Downloading Python installer from {WINDOWS_PYTHON_URL}...")
    urllib.request.urlretrieve(WINDOWS_PYTHON_URL, installer_path)
    
    # Run the installer with required flags
    print("Running Python installer...")
    subprocess.run([installer_path, "/quiet", "InstallAllUsers=1", "PrependPath=1", "Include_test=0"])
    
    # Clean up
    shutil.rmtree(temp_dir)
    
    print("Python installed successfully!")
    print("Please restart this script to continue setup.")
    
    # Verify installation
    if is_python_installed():
        return True
    else:
        print("Failed to install Python. Please install it manually from https://www.python.org/downloads/")
        return False

def install_python_guide():
    """Display guide for installing Python on non-Windows systems."""
    system = platform.system()
    
    if system == "Darwin":  # macOS
        print("Python not found. Please install Python using one of these methods:")
        print("1. Download and install from https://www.python.org/downloads/")
        print("2. Install using Homebrew: brew install python")
        print("3. Install using MacPorts: port install python310")
    elif system == "Linux":
        print("Python 3 not found. Please install it using your distribution's package manager:")
        print("For Ubuntu/Debian: sudo apt-get update && sudo apt-get install python3 python3-pip")
        print("For Fedora: sudo dnf install python3 python3-pip")
        print("For Arch Linux: sudo pacman -S python python-pip")
    else:
        print(f"Unsupported operating system: {system}")
    
    print("\nAfter installing Python, run this script again.")
    return False

def create_windows_launcher():
    """Create a Windows .bat launcher."""
    launcher_path = "iPhone_Photo_Converter.bat"
    with open(launcher_path, "w") as f:
        f.write('@echo off\n')
        f.write('echo Starting iPhone Photo Converter...\n')
        f.write('python iphone_photo_converter.py\n')
        f.write('if errorlevel 1 (\n')
        f.write('    echo Error running application. Please make sure Python is installed.\n')
        f.write('    echo If Python is not installed, please run iphone_converter_setup.py first.\n')
        f.write('    pause\n')
        f.write(')\n')
    
    print(f"Created launcher: {launcher_path}")
    return launcher_path

def create_macos_launcher():
    """Create a macOS .command launcher."""
    launcher_path = "iPhone_Photo_Converter.command"
    with open(launcher_path, "w") as f:
        f.write('#!/bin/bash\n')
        f.write('cd "$(dirname "$0")"\n')
        f.write('echo "Starting iPhone Photo Converter..."\n')
        f.write('python3 iphone_photo_converter.py\n')
        f.write('if [ $? -ne 0 ]; then\n')
        f.write('    echo "Error running application. Please make sure Python is installed."\n')
        f.write('    echo "If Python is not installed, please run iphone_converter_setup.py first."\n')
        f.write('    read -p "Press Enter to continue..."\n')
        f.write('fi\n')
    
    # Make it executable
    os.chmod(launcher_path, 0o755)
    print(f"Created launcher: {launcher_path}")
    return launcher_path

def create_linux_launcher():
    """Create a Linux .sh launcher."""
    launcher_path = "iphone_photo_converter.sh"
    with open(launcher_path, "w") as f:
        f.write('#!/bin/bash\n')
        f.write('cd "$(dirname "$0")"\n')
        f.write('echo "Starting iPhone Photo Converter..."\n')
        f.write('python3 iphone_photo_converter.py\n')
        f.write('if [ $? -ne 0 ]; then\n')
        f.write('    echo "Error running application. Please make sure Python is installed."\n')
        f.write('    echo "If Python is not installed, please run iphone_converter_setup.py first."\n')
        f.write('    read -p "Press Enter to continue..."\n')
        f.write('fi\n')
    
    # Make it executable
    os.chmod(launcher_path, 0o755)
    print(f"Created launcher: {launcher_path}")
    return launcher_path

def check_pyinstaller():
    """Check if PyInstaller is installed."""
    try:
        subprocess.run([sys.executable, "-m", "PyInstaller", "--version"], 
                     stdout=subprocess.PIPE, 
                     stderr=subprocess.PIPE)
        return True
    except:
        return False

def install_pyinstaller():
    """Install PyInstaller."""
    print("Installing PyInstaller...")
    try:
        subprocess.run([sys.executable, "-m", "pip", "install", "pyinstaller"], check=True)
        
        # Verify installation
        if check_pyinstaller():
            print("PyInstaller installed successfully!")
            return True
        else:
            print("Failed to install PyInstaller. Please install it manually.")
            return False
    except subprocess.CalledProcessError as e:
        print(f"Error installing PyInstaller: {e}")
        print("Please try installing it manually: pip install pyinstaller")
        return False

def create_windows_exe():
    """Create standalone Windows executable."""
    print("Creating Windows executable...")
    
    # Run PyInstaller
    try:
        subprocess.run([
            sys.executable, "-m", "PyInstaller",
            "--name=iPhone_Photo_Converter",
            "--onefile",
            "--windowed",
            "--add-data=README.md;.",
            "iphone_photo_converter.py"
        ], check=True)
        
        # Copy the executable to the root directory
        exe_path = "iPhone_Photo_Converter.exe"
        dist_path = os.path.join("dist", exe_path)
        if os.path.exists(dist_path):
            shutil.copy(dist_path, exe_path)
            print(f"Executable created: {exe_path}")
            return exe_path
        else:
            print("Error: Executable not created.")
            return None
    except subprocess.CalledProcessError as e:
        print(f"Error creating Windows executable: {e}")
        return None

def create_macos_app():
    """Create standalone macOS application."""
    print("Creating macOS application...")
    
    # Run PyInstaller to create app bundle
    try:
        subprocess.run([
            sys.executable, "-m", "PyInstaller",
            "--name=iPhone Photo Converter",
            "--windowed",
            "--add-data=README.md:.",
            "iphone_photo_converter.py"
        ], check=True)
        
        app_path = os.path.join("dist", "iPhone Photo Converter.app")
        print(f"Application created: {app_path}")
        return app_path
    except subprocess.CalledProcessError as e:
        print(f"Error creating macOS application: {e}")
        return None

def create_linux_executable():
    """Create standalone Linux executable."""
    print("Creating Linux executable...")
    
    # Run PyInstaller
    try:
        subprocess.run([
            sys.executable, "-m", "PyInstaller",
            "--name=iphone-photo-converter",
            "--onefile",
            "--add-data=README.md:.",
            "iphone_photo_converter.py"
        ], check=True)
        
        # Copy the executable to the root directory
        exe_path = "iphone-photo-converter"
        dist_path = os.path.join("dist", exe_path)
        if os.path.exists(dist_path):
            shutil.copy(dist_path, exe_path)
            os.chmod(exe_path, 0o755)
            print(f"Executable created: {exe_path}")
            return exe_path
        else:
            print("Error: Executable not created.")
            return None
    except subprocess.CalledProcessError as e:
        print(f"Error creating Linux executable: {e}")
        return None

def get_user_choice(prompt, options):
    """Get user choice from a list of options."""
    while True:
        print(prompt)
        for i, option in enumerate(options, 1):
            print(f"{i}. {option}")
        
        try:
            choice = int(input("Enter your choice (number): "))
            if 1 <= choice <= len(options):
                return choice
            else:
                print("Invalid choice. Please try again.")
        except ValueError:
            print("Please enter a number.")

def basic_setup():
    """Perform basic setup: check Python, install dependencies, and create launcher."""
    print_header("Basic Setup")
    
    # Check if Python is installed
    if not is_python_installed():
        system = platform.system()
        if system == "Windows":
            if not install_python_windows():
                return False
        else:
            if not install_python_guide():
                return False
    
    # Install dependencies
    if not install_dependencies():
        print("Warning: Some dependencies could not be installed.")
        print("The application may still work with limited functionality.")
    
    # Make the main script executable
    system = platform.system()
    if system != "Windows":
        try:
            os.chmod("iphone_photo_converter.py", 0o755)
        except:
            print("Warning: Could not make script executable. You may need to run: chmod +x iphone_photo_converter.py")
    
    # Create platform-specific launcher
    if system == "Windows":
        launcher = create_windows_launcher()
    elif system == "Darwin":  # macOS
        launcher = create_macos_launcher()
    elif system == "Linux":
        launcher = create_linux_launcher()
    else:
        print(f"Unsupported operating system: {system}")
        return False
    
    print(f"\nBasic setup completed successfully!")
    print(f"You can now run the application using: {launcher}")
    return True

def advanced_setup():
    """Create standalone executable."""
    print_header("Create Standalone Application")
    
    # Check if PyInstaller is installed
    if not check_pyinstaller():
        if not install_pyinstaller():
            return False
    
    # Create platform-specific executable
    system = platform.system()
    if system == "Windows":
        executable = create_windows_exe()
    elif system == "Darwin":  # macOS
        executable = create_macos_app()
    elif system == "Linux":
        executable = create_linux_executable()
    else:
        print(f"Unsupported operating system: {system}")
        return False
    
    if executable:
        print(f"\nStandalone application created successfully!")
        print(f"You can now run the application using: {executable}")
        return True
    else:
        return False

def main():
    """Main function for the setup script."""
    parser = argparse.ArgumentParser(description=f"{APP_NAME} Setup")
    parser.add_argument('--basic', action='store_true', help='Perform basic setup only')
    parser.add_argument('--advanced', action='store_true', help='Create standalone executable only')
    parser.add_argument('--all', action='store_true', help='Perform both basic and advanced setup')
    args = parser.parse_args()

    print_header(f"Welcome to {APP_NAME} Setup")
    print(f"Version: {APP_VERSION}")
    print(f"Platform: {platform.system()} {platform.release()}")
    
    # Handle command-line arguments
    if args.basic:
        basic_setup()
    elif args.advanced:
        advanced_setup()
    elif args.all:
        basic_setup()
        advanced_setup()
    else:
        # Interactive mode
        options = ["Basic setup (Python, dependencies, and launcher)", 
                   "Create standalone executable (no Python required)", 
                   "Complete setup (both options above)", 
                   "Exit"]
        
        choice = get_user_choice("What would you like to do?", options)
        
        if choice == 1:
            basic_setup()
        elif choice == 2:
            advanced_setup()
        elif choice == 3:
            if basic_setup():
                advanced_setup()
        elif choice == 4:
            print("Exiting setup.")
            return

    print("\nSetup process completed!")

if __name__ == "__main__":
    main() 
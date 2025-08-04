#!/usr/bin/env python3
"""
iPhone Photo Converter - One-Click Launcher
Double-click this file to automatically set up and run the iPhone Photo Converter!

This script will:
1. Check if Python is properly installed
2. Install any missing dependencies
3. Launch the iPhone Photo Converter application

No technical knowledge required - just double-click and go!
"""

import os
import sys
import platform
import subprocess
import tkinter as tk
from tkinter import messagebox
import importlib.util


def show_message(title, message, error=False):
    """Show a message box to the user."""
    try:
        root = tk.Tk()
        root.withdraw()  # Hide the main window
        if error:
            messagebox.showerror(title, message)
        else:
            messagebox.showinfo(title, message)
        root.destroy()
    except:
        # Fallback to console output
        print(f"\n{title}: {message}")
        input("Press Enter to continue...")


def is_dependency_installed(package_name):
    """Check if a Python package is installed."""
    spec = importlib.util.find_spec(package_name)
    return spec is not None


def install_dependencies():
    """Install required dependencies."""
    print("Installing required dependencies...")
    
    # List of required packages
    required_packages = [
        'pillow',
        'pillow-heif', 
        'piexif',
        'PyQt6',
        'pyusb',
        'psutil'
    ]
    
    # Platform-specific packages
    if platform.system() == 'Windows':
        required_packages.extend(['wmi', 'libusb-package', 'pywin32'])
    
    missing_packages = []
    for package in required_packages:
        # Handle package name variations
        check_name = package
        if package == 'pillow-heif':
            check_name = 'pillow_heif'
        elif package == 'PyQt6':
            check_name = 'PyQt6'
        
        if not is_dependency_installed(check_name):
            missing_packages.append(package)
    
    if not missing_packages:
        print("All dependencies are already installed!")
        return True
    
    print(f"Installing missing packages: {', '.join(missing_packages)}")
    
    try:
        # Install missing packages
        cmd = [sys.executable, "-m", "pip", "install"] + missing_packages
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            print("Dependencies installed successfully!")
            return True
        else:
            print(f"Error installing dependencies: {result.stderr}")
            return False
            
    except Exception as e:
        print(f"Error installing dependencies: {e}")
        return False


def run_main_application():
    """Run the main iPhone Photo Converter application."""
    try:
        # Import and run the main application
        import iphone_photo_converter
        iphone_photo_converter.main()
    except ImportError as e:
        show_message(
            "Error", 
            f"Cannot import the main application: {e}\n\nMake sure 'iphone_photo_converter.py' is in the same folder as this launcher.",
            error=True
        )
        return False
    except Exception as e:
        show_message(
            "Error",
            f"Error running the application: {e}",
            error=True
        )
        return False
    
    return True


def check_python_version():
    """Check if Python version is compatible."""
    if sys.version_info < (3, 6):
        show_message(
            "Python Version Error",
            f"This application requires Python 3.6 or newer.\n"
            f"You have Python {sys.version_info.major}.{sys.version_info.minor}.\n\n"
            f"Please update Python and try again.",
            error=True
        )
        return False
    return True





def main():
    """Main launcher function."""
    print("=" * 60)
    print(" iPhone Photo Converter - One-Click Launcher ".center(60, "="))
    print("=" * 60)
    print()
    
    # Check Python version (we should already have Python if we're running this script)
    if not check_python_version():
        return
    
    print(f"Python {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro} detected")
    print(f"Platform: {platform.system()} {platform.release()}")
    print()
    
    # Check if main application file exists
    if not os.path.exists("iphone_photo_converter.py"):
        show_message(
            "File Missing",
            "The main application file 'iphone_photo_converter.py' was not found.\n\n"
            "Make sure this launcher is in the same folder as the iPhone Photo Converter files.",
            error=True
        )
        return
    
    # Install dependencies if needed
    print("Checking dependencies...")
    if not install_dependencies():
        show_message(
            "Setup Error",
            "Failed to install required dependencies.\n\n"
            "You may need to install them manually or run this as administrator.",
            error=True
        )
        return
    
    print("\nStarting iPhone Photo Converter...")
    print("-" * 40)
    
    # Run the main application
    if run_main_application():
        print("\nApplication closed successfully.")
    else:
        print("\nApplication encountered an error.")
        input("Press Enter to exit...")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nOperation cancelled by user.")
    except Exception as e:
        show_message(
            "Unexpected Error",
            f"An unexpected error occurred: {e}\n\n"
            f"Please check that all files are present and try running as administrator.",
            error=True
        ) 
#!/bin/bash
# iPhone Photo Converter - One-Click Launcher for Linux
# Double-click this file to run the application

# Change to the script's directory
cd "$(dirname "$0")"

echo "================================================================"
echo " iPhone Photo Converter - Starting Application..."
echo "================================================================"
echo

# Function to detect Linux distribution
detect_distro() {
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        DISTRO=$ID
        DISTRO_NAME=$PRETTY_NAME
    elif command -v lsb_release &> /dev/null; then
        DISTRO=$(lsb_release -si | tr '[:upper:]' '[:lower:]')
        DISTRO_NAME=$(lsb_release -sd)
    else
        DISTRO="unknown"
        DISTRO_NAME="Unknown Linux"
    fi
}

# Function to check if Python 3 is available
check_python() {
    # Try different Python commands
    for cmd in python3 python; do
        if command -v "$cmd" &> /dev/null; then
            # Check if it's Python 3.6+
            version_output=$($cmd --version 2>&1)
            if [[ $version_output =~ Python\ 3\.([0-9]+) ]]; then
                minor_version=${BASH_REMATCH[1]}
                if [ "$minor_version" -ge 6 ]; then
                    echo "Python found: $cmd ($version_output)"
                    PYTHON_CMD="$cmd"
                    return 0
                fi
            fi
        fi
    done
    return 1
}

# Function to install Python based on distribution
install_python() {
    echo "Attempting to install Python 3..."
    echo "Distribution: $DISTRO_NAME"
    echo
    
    case "$DISTRO" in
        ubuntu|debian)
            echo "Using apt package manager..."
            if sudo apt update && sudo apt install -y python3 python3-pip python3-tk; then
                return 0
            fi
            ;;
        fedora|rhel|centos)
            echo "Using dnf/yum package manager..."
            if command -v dnf &> /dev/null; then
                if sudo dnf install -y python3 python3-pip python3-tkinter; then
                    return 0
                fi
            elif command -v yum &> /dev/null; then
                if sudo yum install -y python3 python3-pip python3-tkinter; then
                    return 0
                fi
            fi
            ;;
        arch|manjaro)
            echo "Using pacman package manager..."
            if sudo pacman -S --noconfirm python python-pip tk; then
                return 0
            fi
            ;;
        opensuse*|sles)
            echo "Using zypper package manager..."
            if sudo zypper install -y python3 python3-pip python3-tk; then
                return 0
            fi
            ;;
        alpine)
            echo "Using apk package manager..."
            if sudo apk add python3 py3-pip py3-tkinter; then
                return 0
            fi
            ;;
        *)
            echo "Unknown distribution: $DISTRO"
            return 1
            ;;
    esac
    
    return 1
}

# Function to show manual installation instructions
manual_install() {
    echo
    echo "============================================================"
    echo " Python Installation Required"
    echo "============================================================"
    echo
    echo "Please install Python 3 using your distribution's package manager:"
    echo
    
    case "$DISTRO" in
        ubuntu|debian)
            echo "Ubuntu/Debian:"
            echo "  sudo apt update"
            echo "  sudo apt install python3 python3-pip python3-tk"
            ;;
        fedora|rhel|centos)
            echo "Fedora/RHEL/CentOS:"
            if command -v dnf &> /dev/null; then
                echo "  sudo dnf install python3 python3-pip python3-tkinter"
            else
                echo "  sudo yum install python3 python3-pip python3-tkinter"
            fi
            ;;
        arch|manjaro)
            echo "Arch Linux/Manjaro:"
            echo "  sudo pacman -S python python-pip tk"
            ;;
        opensuse*|sles)
            echo "openSUSE:"
            echo "  sudo zypper install python3 python3-pip python3-tk"
            ;;
        alpine)
            echo "Alpine Linux:"
            echo "  sudo apk add python3 py3-pip py3-tkinter"
            ;;
        *)
            echo "For your distribution ($DISTRO_NAME):"
            echo "Please consult your distribution's documentation for installing Python 3."
            echo
            echo "Generic instructions:"
            echo "1. Install Python 3.6 or newer"
            echo "2. Install pip (Python package manager)"
            echo "3. Install tkinter (for GUI support)"
            ;;
    esac
    
    echo
    echo "After installation, run this launcher again."
    echo
    read -p "Press Enter to exit..."
    exit 1
}

# Detect distribution
detect_distro

# Check if Python is available
if ! check_python; then
    echo "Python 3.6+ not found."
    echo
    
    # Ask user if they want to try automatic installation
    read -p "Would you like to try installing Python automatically? (y/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo
        if install_python; then
            echo
            echo "Python installation completed!"
            echo "Checking if Python is now available..."
            if check_python; then
                echo "Success! Python is now available."
            else
                echo "Python installation completed but Python is still not available."
                echo "You may need to restart your terminal or log out and log back in."
                read -p "Press Enter to exit..."
                exit 1
            fi
        else
            echo
            echo "Automatic installation failed."
            manual_install
        fi
    else
        manual_install
    fi
fi

echo
echo "Starting iPhone Photo Converter..."
echo

# Run the launcher
$PYTHON_CMD "RUN_iPhone_Photo_Converter.py"

# Keep terminal open if there was an error
if [ $? -ne 0 ]; then
    echo
    echo "The application encountered an error."
    read -p "Press Enter to exit..."
fi 
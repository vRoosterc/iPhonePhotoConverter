#!/bin/bash
# iPhone Photo Converter - One-Click Launcher for macOS
# Double-click this file to run the application

# Change to the script's directory
cd "$(dirname "$0")"

echo "================================================================"
echo " iPhone Photo Converter - Starting Application..."
echo "================================================================"
echo

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

# Function to install Python via Homebrew
install_python_homebrew() {
    echo "Checking if Homebrew is installed..."
    if command -v brew &> /dev/null; then
        echo "Homebrew found! Installing Python..."
        echo
        if brew install python; then
            echo
            echo "Python installed successfully via Homebrew!"
            # Refresh PATH
            export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
            return 0
        else
            echo "Failed to install Python via Homebrew."
            return 1
        fi
    else
        echo "Homebrew not found."
        return 1
    fi
}

# Function to guide manual installation
manual_install() {
    echo
    echo "============================================================"
    echo " Python Installation Required"
    echo "============================================================"
    echo
    echo "Choose an installation method:"
    echo
    echo "RECOMMENDED - Using Homebrew:"
    echo "1. Install Homebrew (if not already installed):"
    echo "   /bin/bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\""
    echo "2. Install Python:"
    echo "   brew install python"
    echo
    echo "ALTERNATIVE - Direct Download:"
    echo "1. Visit: https://www.python.org/downloads/"
    echo "2. Download and install Python 3.11+"
    echo
    echo "After installation, run this launcher again."
    echo
    
    # Ask user if they want to try automatic Homebrew installation
    read -p "Would you like to try installing Homebrew and Python automatically? (y/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo
        echo "Installing Homebrew..."
        if /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"; then
            # Add Homebrew to PATH for this session
            export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
            echo
            echo "Homebrew installed! Now installing Python..."
            if install_python_homebrew; then
                return 0
            fi
        else
            echo "Homebrew installation failed."
        fi
    fi
    
    # Open Python download page
    echo
    echo "Opening Python download page..."
    open "https://www.python.org/downloads/"
    echo
    read -p "Press Enter to exit..."
    exit 1
}

# Check if Python is available
if ! check_python; then
    echo "Python 3.6+ not found."
    echo
    
    # Try Homebrew installation first
    if ! install_python_homebrew; then
        # Fall back to manual installation guide
        manual_install
    else
        # Re-check Python after Homebrew installation
        if ! check_python; then
            echo "Python installation completed but Python is still not available."
            echo "Please restart Terminal and try again."
            read -p "Press Enter to exit..."
            exit 1
        fi
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
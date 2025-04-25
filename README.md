# iPhone Photo Converter

A cross-platform application for transferring photos/videos from an iPhone to your computer and converting HEIC files to JPEG format.

## Features

- Automatic iPhone detection when connected via USB
- Copy photos and videos from your iPhone to a local folder
- Convert HEIC images to JPEG format while preserving EXIF data
- Works on Windows, macOS, and Linux

## Quick Start

The easiest way to set up and use this application:

1. Download this repository
2. Run the unified setup script:
   - Windows: Double-click on `iphone_converter_setup.py` or run `python iphone_converter_setup.py` in Command Prompt
   - macOS: Run `python3 iphone_converter_setup.py` in Terminal
   - Linux: Run `python3 iphone_converter_setup.py` in Terminal

3. Choose from the setup options:
   - **Basic setup**: Installs dependencies and creates a launcher for your platform
   - **Create standalone executable**: Creates a standalone application that doesn't require Python
   - **Complete setup**: Performs both of the above

4. Follow the on-screen instructions

The setup script can also be run with command-line options:
```
python iphone_converter_setup.py --basic     # For basic setup only
python iphone_converter_setup.py --advanced  # To create standalone executable
python iphone_converter_setup.py --all       # For complete setup
```

## System Requirements

- Windows, macOS, or Linux operating system
- USB connection to your iPhone
- Python 3.6 or higher (if not using the standalone executable)
- The setup script will help you install Python if needed

## Manual Installation

If you prefer to install manually:

### Windows

1. Make sure you have Python installed. Download from [python.org](https://www.python.org/downloads/)
2. Download this repository
3. Open Command Prompt and navigate to the downloaded folder
4. Run the following command to install dependencies:
   ```
   pip install -r requirements.txt
   ```
5. Run the application:
   ```
   python iphone_photo_converter.py
   ```

### macOS

1. Make sure you have Python installed
2. Install libusb (recommended):
   ```
   brew install libusb
   ```
3. Download this repository
4. Open Terminal and navigate to the downloaded folder
5. Install Python dependencies:
   ```
   pip3 install -r requirements.txt
   ```
6. Make the script executable:
   ```
   chmod +x iphone_photo_converter.py
   ```
7. Run the application:
   ```
   ./iphone_photo_converter.py
   ```

### Linux

1. Install Python and required system dependencies:
   ```
   sudo apt-get update
   sudo apt-get install python3 python3-pip python3-pyqt6 libusb-1.0-0-dev
   ```
   (Command may vary depending on your Linux distribution)

2. Download this repository
3. Open Terminal and navigate to the downloaded folder
4. Install Python dependencies:
   ```
   pip3 install -r requirements.txt
   ```
5. Make the script executable:
   ```
   chmod +x iphone_photo_converter.py
   ```
6. Run the application:
   ```
   ./iphone_photo_converter.py
   ```

## How to Use

1. Connect your iPhone to your computer using a USB cable
2. Launch the application using one of these methods:
   - Run the launcher created by the setup script
   - Run the standalone executable if you created one
   - Run `python iphone_photo_converter.py` directly
3. Click "Detect iPhone" to locate your connected device
4. (Optional) Click "Select Output Folder" to choose where to save your photos/videos
5. Click "Transfer and Convert Photos" to begin the process
6. Wait for the process to complete. The application will automatically open the folder containing your transferred photos

## Troubleshooting

### iPhone Detection Issues

- Make sure your iPhone is connected and that you've trusted the computer on your iPhone
- On macOS, make sure libusb is installed: `brew install libusb`
- On Linux, install the libusb development package: `sudo apt-get install libusb-1.0-0-dev`
- Try using a different USB port or cable

### Dependency Issues

- If you encounter errors installing dependencies:
  - Try installing them manually: `pip install <package-name>`
  - Check the terminal output for specific error messages
  - Make sure you have the latest pip: `python -m pip install --upgrade pip`

### Permission Issues

- On macOS/Linux, you may need to run the application with administrator privileges
- Make sure the script is executable: `chmod +x iphone_photo_converter.py`

### Python Not Found

- Use the setup script (`iphone_converter_setup.py`) which will help you install Python
- Make sure Python is in your system PATH
- Try using the specific Python command for your system (`python3` on macOS/Linux)

## Building from Source

If you want to modify and build the application:

1. Make changes to `iphone_photo_converter.py`
2. Run the setup script with the advanced option to build a new standalone executable:
   ```
   python iphone_converter_setup.py --advanced
   ```

## License

This software is open source and available under the MIT License. 
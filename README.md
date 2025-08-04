# iPhone Photo Converter

A cross-platform application for transferring photos/videos from an iPhone to your computer and converting HEIC files to JPEG format.

## ✨ Features

- Automatic iPhone detection when connected via USB
- Copy photos and videos from your iPhone to a local folder
- Convert HEIC images to JPEG format while preserving EXIF data
- Works on Windows, macOS, and Linux
- **One-click setup and launch** - no technical knowledge required!

## 🚀 Quick Start (Recommended)

**The easiest way to use this application - just double-click and go!**

1. **Download this repository** to your computer
2. **Double-click the appropriate launcher for your system:**
   - **Windows**: Double-click `RUN_iPhone_Photo_Converter.bat`
   - **macOS**: Double-click `RUN_iPhone_Photo_Converter.command`
   - **Linux**: Double-click `RUN_iPhone_Photo_Converter.sh` (or run from terminal)

That's it! The launcher will:
- ✅ **Automatically install Python** if not found (Windows: fully automatic, macOS/Linux: guided)
- ✅ **Auto-install all required dependencies** (PyQt6, Pillow, etc.)
- ✅ **Launch the iPhone Photo Converter application**
- ✅ **Handle everything for you** - no technical knowledge required!

### 📋 System Requirements

- **Windows, macOS, or Linux** operating system
- **USB connection** to your iPhone
- **Internet connection** (for automatic Python and dependency installation)

**Note**: Python installation is handled automatically! If you don't have Python installed:
- **Windows**: Fully automatic download and installation
- **macOS**: Guided installation with Homebrew or manual download
- **Linux**: Automatic installation using your distribution's package manager

## 📱 How to Use

1. **Connect your iPhone** to your computer using a USB cable
2. **Launch the application** by double-clicking the launcher for your platform
3. Click **"Detect iPhone"** to locate your connected device
4. (Optional) Click **"Select Output Folder"** to choose where to save your photos/videos
5. Click **"Transfer and Convert Photos"** to begin the process
6. **Wait for completion** - the application will automatically open the folder containing your transferred photos

## 🔧 Advanced Setup Options

If you prefer more control over the installation process, you can still use the original setup script:

```bash
# Basic setup (installs dependencies and creates launchers)
python iphone_converter_setup.py --basic

# Create standalone executable (no Python required after creation)
python iphone_converter_setup.py --advanced

# Complete setup (both of the above)
python iphone_converter_setup.py --all
```

## 🛠️ Manual Installation

If you prefer to install manually or need more control:

### Windows

1. Install Python from [python.org](https://www.python.org/downloads/) (make sure to check "Add Python to PATH")
2. Download this repository
3. Open Command Prompt in the downloaded folder
4. Run: `pip install -r requirements.txt`
5. Run: `python iphone_photo_converter.py`

### macOS

1. Install Python 3 (built-in or from [python.org](https://www.python.org/downloads/))
2. (Recommended) Install libusb: `brew install libusb`
3. Download this repository
4. Open Terminal in the downloaded folder
5. Run: `pip3 install -r requirements.txt`
6. Run: `python3 iphone_photo_converter.py`

### Linux

1. Install Python 3: `sudo apt-get install python3 python3-pip libusb-1.0-0-dev` (Ubuntu/Debian)
2. Download this repository
3. Open Terminal in the downloaded folder
4. Run: `pip3 install -r requirements.txt`
5. Run: `python3 iphone_photo_converter.py`

## 🔍 Troubleshooting

### iPhone Detection Issues

**The app now uses 8 different detection methods for Windows, but if your iPhone still isn't recognized:**

**Quick Solutions:**
- Click **"🔍 Manually Select iPhone DCIM Folder"** to browse to your iPhone's photo folder
- Click **"🐛 Debug Detection"** to see exactly what the app is finding
- Use **"🧪 Test Connection"** for detailed diagnostics

**If automatic detection fails:**

**For Windows:**
- Make sure your iPhone is **unlocked** and you've tapped **"Trust This Computer"**
- Install **iTunes** or **Apple Mobile Device Support** if not already installed
- Try a **different USB port or cable** (USB 3.0 ports work best)
- **Restart both your iPhone and computer** if detection fails
- Check Windows Device Manager to see if iPhone appears under "Portable Devices"

**For macOS:**
- Make sure your iPhone is **unlocked** and you've tapped **"Trust This Computer"**
- **Close the Photos app** if it's open (it may have exclusive access)
- Install libusb with `brew install libusb` for better USB detection
- Try **disconnecting and reconnecting** your iPhone

**For Linux:**
- Make sure your iPhone is **unlocked** and you've tapped **"Trust This Computer"**
- Install required packages: `sudo apt-get install libimobiledevice-utils ifuse`
- You may need to run the app with `sudo` for the first connection
- Install libusb development package: `sudo apt-get install libusb-1.0-0-dev`

### Python Not Found

- **Use the one-click launchers** - they'll guide you to install Python
- Make sure Python is in your system PATH
- On Windows: Reinstall Python and check "Add Python to PATH"
- On macOS/Linux: Try using `python3` instead of `python`

### Permission Issues

- **Run as administrator** (Windows) or with `sudo` (macOS/Linux) if needed
- On macOS/Linux: The launchers should handle permissions automatically

### Dependency Installation Issues

- Make sure you have an **internet connection**
- Try running the launcher **as administrator**
- Check that pip is working: `python -m pip --version`
- Update pip: `python -m pip install --upgrade pip`

## 🏗️ Building from Source

To create your own standalone executable:

1. Make changes to `iphone_photo_converter.py`
2. Run: `python iphone_converter_setup.py --advanced`

## 📄 License

This software is open source and available under the MIT License. 
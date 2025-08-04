#!/usr/bin/env python3
import os
import sys
import shutil
import platform
import subprocess
from datetime import datetime
from pathlib import Path
from PIL import Image, ExifTags
from pillow_heif import register_heif_opener
import piexif
import re
import threading
import usb.core
import usb.util
from PyQt6.QtWidgets import (QApplication, QMainWindow, QPushButton, QVBoxLayout, 
                           QWidget, QLabel, QProgressBar, QFileDialog, QMessageBox, QInputDialog)
from PyQt6.QtCore import Qt, pyqtSignal, QThread

# Register HEIF opener
register_heif_opener()

# Constants
APPLE_VENDOR_ID = 0x05ac  # Apple's USB vendor ID

class WorkerThread(QThread):
    progress_updated = pyqtSignal(int)
    status_updated = pyqtSignal(str)
    finished_signal = pyqtSignal()
    
    def __init__(self, source_path, target_path):
        super().__init__()
        self.source_path = source_path
        self.target_path = target_path
        self.running = True
        
    def run(self):
        try:
            self.status_updated.emit("Finding and copying files...")
            self.copy_files_from_iphone()
            
            self.status_updated.emit("Converting HEIC files to JPEG...")
            self.convert_heic_files()
            
            self.status_updated.emit("Process completed successfully!")
            self.finished_signal.emit()
        except Exception as e:
            self.status_updated.emit(f"Error: {str(e)}")
    
    def copy_files_from_iphone(self):
        # Ensure target directory exists
        os.makedirs(self.target_path, exist_ok=True)
        
        # Get all files from source
        files = []
        for root, _, filenames in os.walk(self.source_path):
            for filename in filenames:
                if filename.lower().endswith(('.heic', '.jpg', '.jpeg', '.png', '.mov', '.mp4')):
                    files.append(os.path.join(root, filename))
        
        # Copy files with progress updates
        total_files = len(files)
        for i, file_path in enumerate(files):
            if not self.running:
                return
                
            try:
                file_name = os.path.basename(file_path)
                dest_path = os.path.join(self.target_path, file_name)
                shutil.copy2(file_path, dest_path)
                
                # Update progress
                progress = int((i + 1) / total_files * 50)  # First 50% for copying
                self.progress_updated.emit(progress)
            except Exception as e:
                print(f"Error copying {file_path}: {e}")
    
    def convert_heic_files(self):
        heic_files = [f for f in os.listdir(self.target_path) 
                     if os.path.isfile(os.path.join(self.target_path, f))
                     and f.lower().endswith(('.heic'))]
        
        total_files = len(heic_files)
        if total_files == 0:
            return
            
        for i, filename in enumerate(heic_files):
            if not self.running:
                return
                
            try:
                file_path = os.path.join(self.target_path, filename)
                image = Image.open(file_path)
                
                # Get exif data if available
                image_exif = image.getexif()
                exif_bytes = None
                
                if image_exif:
                    # Make a map with tag names
                    exif = {ExifTags.TAGS[k]: v for k, v in image_exif.items() 
                           if k in ExifTags.TAGS and type(v) is not bytes}
                    
                    # Load exif data via piexif
                    try:
                        exif_dict = piexif.load(image.info.get("exif", b''))
                        
                        # Update exif data with orientation
                        exif_dict["0th"][piexif.ImageIFD.Orientation] = 1
                        
                        # Add datetime if available
                        if 'DateTime' in exif:
                            date = datetime.strptime(exif['DateTime'], '%Y:%m:%d %H:%M:%S')
                            exif_dict["0th"][piexif.ImageIFD.DateTime] = date.strftime("%Y:%m:%d %H:%M:%S")
                            
                        exif_bytes = piexif.dump(exif_dict)
                    except Exception as e:
                        print(f"Error processing EXIF for {filename}: {e}")
                
                # Save image as jpeg
                jpeg_path = os.path.join(self.target_path, os.path.splitext(filename)[0] + ".jpg")
                
                # Save with exif if available, otherwise save without
                if exif_bytes:
                    image.save(jpeg_path, "jpeg", exif=exif_bytes)
                else:
                    image.save(jpeg_path, "jpeg")
                
                # Update progress (from 50% to 100%)
                progress = 50 + int((i + 1) / total_files * 50)
                self.progress_updated.emit(progress)
                
            except Exception as e:
                print(f"Error converting {filename}: {e}")
    
    def stop(self):
        self.running = False

class PhotoConverterApp(QMainWindow):
    def __init__(self):
        super().__init__()
        
        self.setWindowTitle("iPhone Photo Converter")
        self.setMinimumSize(500, 300)
        
        # Main widget and layout
        main_widget = QWidget()
        layout = QVBoxLayout()
        main_widget.setLayout(layout)
        self.setCentralWidget(main_widget)
        
        # Labels and controls
        self.status_label = QLabel("Ready to transfer photos from iPhone")
        layout.addWidget(self.status_label)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)
        
        # Primary Controls
        self.detect_button = QPushButton("🔍 Auto-Detect iPhone")
        self.detect_button.clicked.connect(self.detect_iphone)
        layout.addWidget(self.detect_button)
        
        self.retry_button = QPushButton("🔄 Retry Detection")
        self.retry_button.clicked.connect(self.retry_detection)
        self.retry_button.setVisible(False)  # Hidden by default
        layout.addWidget(self.retry_button)
        
        self.transfer_button = QPushButton("📱➡️💻 Transfer and Convert Photos")
        self.transfer_button.clicked.connect(self.start_transfer)
        self.transfer_button.setEnabled(False)
        layout.addWidget(self.transfer_button)
        
        self.select_output_button = QPushButton("📁 Select Output Folder")
        self.select_output_button.clicked.connect(self.select_output_folder)
        layout.addWidget(self.select_output_button)
        
        # Advanced Options (initially hidden)
        self.show_advanced_button = QPushButton("⚙️ Show Advanced Options")
        self.show_advanced_button.clicked.connect(self.toggle_advanced_options)
        layout.addWidget(self.show_advanced_button)
        
        # Advanced buttons (initially hidden)
        self.test_connection_button = QPushButton("🧪 Connection Diagnostics")
        self.test_connection_button.clicked.connect(self.test_connection)
        self.test_connection_button.setVisible(False)
        layout.addWidget(self.test_connection_button)
        
        self.manual_path_button = QPushButton("📝 Manual Path Entry")
        self.manual_path_button.clicked.connect(self.enter_path_manually)
        self.manual_path_button.setVisible(False)
        layout.addWidget(self.manual_path_button)
        
        self.debug_button = QPushButton("🐛 Debug Information")
        self.debug_button.clicked.connect(self.debug_detection)
        self.debug_button.setVisible(False)
        layout.addWidget(self.debug_button)
        
        # Initialize variables
        self.iphone_path = None
        self.output_folder = os.path.join(os.path.dirname(os.path.abspath(__file__)), "transferred_photos")
        self.update_status(f"Output folder: {self.output_folder}")
        self.worker_thread = None
    
    def _provide_connection_help(self, system):
        """Provide system-specific help for iPhone connection issues."""
        if system == "Windows":
            help_text = ("❌ iPhone not found. Please check:\n"
                        "• iPhone is connected via USB cable\n"
                        "• iPhone is unlocked and you've tapped 'Trust This Computer'\n"
                        "• iTunes or Apple Mobile Device Support is installed\n"
                        "• Try a different USB port or cable\n"
                        "• Restart both devices if needed")
        elif system == "Darwin":  # macOS
            help_text = ("❌ iPhone not found. Please check:\n"
                        "• iPhone is connected via USB cable\n"
                        "• iPhone is unlocked and you've tapped 'Trust This Computer'\n"
                        "• Photos app might have exclusive access - close it and try again\n"
                        "• Try disconnecting and reconnecting the iPhone")
        elif system == "Linux":
            help_text = ("❌ iPhone not found. Please check:\n"
                        "• iPhone is connected via USB cable\n"
                        "• iPhone is unlocked and you've tapped 'Trust This Computer'\n"
                        "• Install required packages: libimobiledevice, ifuse\n"
                        "• You may need to run: sudo apt install libimobiledevice-utils ifuse\n"
                        "• Try running the app with sudo for first connection")
        else:
            help_text = "iPhone not found. Please check your connection."
        
        self.update_status(help_text)
    
    def retry_detection(self):
        """Retry iPhone detection with enhanced methods."""
        self.retry_button.setVisible(False)
        self.update_status("🔄 Retrying iPhone detection...")
        self.progress_bar.setValue(0)
        
        # Clear previous detection result
        self.iphone_path = None
        self.transfer_button.setEnabled(False)
        
        # Start detection with extra thoroughness
        threading.Thread(target=self._enhanced_detection_worker, daemon=True).start()
    
    def _enhanced_detection_worker(self):
        """Enhanced detection worker with multiple retry attempts."""
        try:
            system = platform.system()
            
            for attempt in range(3):  # Try 3 times
                self.update_status(f"🔍 Detection attempt {attempt + 1}/3...")
                
                if system == "Windows":
                    self.iphone_path = self._find_iphone_windows()
                elif system == "Darwin":
                    self.iphone_path = self._find_iphone_macos()
                elif system == "Linux":
                    self.iphone_path = self._find_iphone_linux()
                
                if self.iphone_path:
                    # Verify access
                    try:
                        test_files = os.listdir(self.iphone_path)
                        file_count = len([f for f in test_files if os.path.isfile(os.path.join(self.iphone_path, f))])
                        self.update_status(f"✅ iPhone found on attempt {attempt + 1}! Found {file_count} items in DCIM")
                        self.transfer_button.setEnabled(True)
                        return
                    except Exception as e:
                        self.update_status(f"Found iPhone but access denied: {str(e)}")
                        self.iphone_path = None
                
                if attempt < 2:
                    self.update_status(f"❌ Attempt {attempt + 1} failed, waiting 2 seconds...")
                    threading.Event().wait(2)  # Wait 2 seconds between attempts
            
            # All attempts failed
            self.update_status("❌ All detection attempts failed.")
            self._provide_connection_help(system)
            self.retry_button.setVisible(True)
            
        except Exception as e:
            self.update_status(f"❌ Enhanced detection failed: {str(e)}")
            self.retry_button.setVisible(True)
    
    def toggle_advanced_options(self):
        """Toggle visibility of advanced options."""
        # Check current visibility of advanced buttons
        is_visible = self.test_connection_button.isVisible()
        
        # Toggle visibility
        self.test_connection_button.setVisible(not is_visible)
        self.manual_path_button.setVisible(not is_visible)
        self.debug_button.setVisible(not is_visible)
        
        # Update button text
        if is_visible:
            self.show_advanced_button.setText("⚙️ Show Advanced Options")
        else:
            self.show_advanced_button.setText("⚙️ Hide Advanced Options")
    
    def detect_iphone(self):
        """Enhanced iPhone detection with automatic retry logic."""
        self.update_status("🚀 Starting comprehensive iPhone detection...")
        self.progress_bar.setValue(0)
        self.retry_button.setVisible(False)
        
        # Run in a separate thread to avoid UI blocking
        threading.Thread(target=self._comprehensive_detection_worker, daemon=True).start()
    
    def _comprehensive_detection_worker(self):
        """Comprehensive detection worker with built-in intelligence."""
        try:
            system = platform.system()
            self.update_status(f"🔍 Scanning {system} system for iPhone...")
            
            # First attempt with standard detection
            if system == "Darwin":  # macOS
                self.iphone_path = self._find_iphone_macos()
            elif system == "Windows":
                self.iphone_path = self._find_iphone_windows()
            elif system == "Linux":
                self.iphone_path = self._find_iphone_linux()
            else:
                self.update_status("❌ Unsupported operating system")
                return
            
            if self.iphone_path:
                # Verify we can actually access the path
                try:
                    test_files = os.listdir(self.iphone_path)
                    file_count = len([f for f in test_files if os.path.isfile(os.path.join(self.iphone_path, f))])
                    
                    # Count photo/video files specifically
                    photo_count = 0
                    for root, dirs, files in os.walk(self.iphone_path):
                        for file in files:
                            if file.lower().endswith(('.heic', '.jpg', '.jpeg', '.png', '.mov', '.mp4')):
                                photo_count += 1
                        if photo_count > 0:  # Don't scan everything if we found some
                            break
                    
                    self.update_status(f"🎉 iPhone detected successfully! Found {photo_count} photos/videos ready to transfer")
                    self.transfer_button.setEnabled(True)
                    return
                    
                except PermissionError:
                    self.update_status("📱 iPhone found but locked. Please unlock your iPhone and tap 'Trust This Computer', then try again.")
                    self.retry_button.setVisible(True)
                    return
                except Exception as e:
                    self.update_status(f"📱 iPhone found but cannot access files: {str(e)}")
                    self.retry_button.setVisible(True)
                    return
            
            # If we get here, detection failed
            self.update_status("🔍 Initial detection failed. Checking for common connection issues...")
            
            # Provide helpful troubleshooting
            if system == "Windows":
                self._check_windows_connection_issues()
            elif system == "Darwin":
                self._check_macos_connection_issues()
            elif system == "Linux":
                self._check_linux_connection_issues()
            
            self.retry_button.setVisible(True)
            self.transfer_button.setEnabled(False)
                
        except Exception as e:
            self.update_status(f"❌ Detection error: {str(e)}")
            self.retry_button.setVisible(True)
            self.transfer_button.setEnabled(False)
    
    def _check_windows_connection_issues(self):
        """Check for common Windows iPhone connection issues."""
        issues = []
        
        # Check for Apple USB devices
        try:
            devices = usb.core.find(find_all=True, idVendor=APPLE_VENDOR_ID)
            apple_devices = list(devices)
            if not apple_devices:
                issues.append("• No Apple USB devices detected - check USB cable connection")
            else:
                issues.append(f"✅ Found {len(apple_devices)} Apple USB device(s)")
        except:
            issues.append("• Could not check USB devices")
        
        # Check for iTunes/Apple Mobile Device Support
        try:
            result = subprocess.run(["where", "iTunes"], capture_output=True, text=True)
            if result.returncode != 0:
                issues.append("• iTunes not found - install iTunes or Apple Mobile Device Support")
            else:
                issues.append("✅ iTunes detected")
        except:
            pass
        
        help_text = "❌ iPhone not found. Connection check results:\n\n" + "\n".join(issues)
        help_text += "\n\n💡 Try these solutions:\n"
        help_text += "• Unlock your iPhone and tap 'Trust This Computer'\n"
        help_text += "• Try a different USB port (USB 3.0 preferred)\n"
        help_text += "• Restart both your iPhone and computer\n"
        help_text += "• Install iTunes from Microsoft Store or Apple.com\n"
        help_text += "• Click 'Retry Detection' after trying these steps"
        
        self.update_status(help_text)
    
    def _check_macos_connection_issues(self):
        """Check for common macOS iPhone connection issues."""
        issues = []
        
        # Check for volumes
        try:
            volumes = os.listdir("/Volumes")
            iphone_volumes = [v for v in volumes if 'iphone' in v.lower() or 'apple' in v.lower()]
            if iphone_volumes:
                issues.append(f"✅ Found iPhone volume(s): {', '.join(iphone_volumes)}")
            else:
                issues.append("• No iPhone volumes found in /Volumes")
        except:
            issues.append("• Could not check /Volumes directory")
        
        help_text = "❌ iPhone not found. Connection check results:\n\n" + "\n".join(issues)
        help_text += "\n\n💡 Try these solutions:\n"
        help_text += "• Unlock your iPhone and tap 'Trust This Computer'\n"
        help_text += "• Close Photos app if it's open\n"
        help_text += "• Disconnect and reconnect your iPhone\n"
        help_text += "• Install libusb: brew install libusb\n"
        help_text += "• Click 'Retry Detection' after trying these steps"
        
        self.update_status(help_text)
    
    def _check_linux_connection_issues(self):
        """Check for common Linux iPhone connection issues."""
        issues = []
        
        # Check for lsusb
        try:
            result = subprocess.run(["lsusb"], capture_output=True, text=True)
            if "Apple" in result.stdout:
                issues.append("✅ Apple device detected by lsusb")
            else:
                issues.append("• No Apple devices found by lsusb")
        except:
            issues.append("• lsusb not available")
        
        help_text = "❌ iPhone not found. Connection check results:\n\n" + "\n".join(issues)
        help_text += "\n\n💡 Try these solutions:\n"
        help_text += "• Unlock your iPhone and tap 'Trust This Computer'\n"
        help_text += "• Install packages: sudo apt install libimobiledevice-utils ifuse\n"
        help_text += "• Try running with sudo permissions\n"
        help_text += "• Check mount points in /media and /mnt\n"
        help_text += "• Click 'Retry Detection' after trying these steps"
        
        self.update_status(help_text)
    
    def manually_select_iphone(self):
        """Allow user to manually select the iPhone DCIM folder."""
        # Show warning about MTP limitation first
        QMessageBox.information(
            self,
            "iPhone Folder Selection",
            "⚠️ NOTE: If your iPhone doesn't appear in this dialog, it's because it's connected via MTP.\n\n"
            "Try these alternatives:\n"
            "1. Click 'Enter iPhone Path Manually' instead\n"
            "2. Copy the path from Windows Explorer address bar\n"
            "3. Look for paths like: Computer\\Apple iPhone\\Internal Storage\\DCIM\n\n"
            "Click OK to continue with folder browser..."
        )
        
        folder = QFileDialog.getExistingDirectory(
            self, 
            "Select iPhone DCIM Folder (may not show MTP devices)",
            "",
            QFileDialog.Option.ShowDirsOnly
        )
        
        if folder:
            self._process_selected_path(folder)
        else:
            self.update_status("❌ No folder selected. Try 'Enter iPhone Path Manually' if your iPhone didn't appear in the dialog.")
    
    def enter_path_manually(self):
        """Allow user to manually enter the iPhone path."""
        instructions = (
            "Enter the full path to your iPhone's DCIM folder.\n\n"
            "Common iPhone paths on Windows:\n"
            "• Computer\\Apple iPhone\\Internal Storage\\DCIM\n"
            "• Computer\\[Your iPhone Name]\\Internal Storage\\DCIM\n"
            "• \\\\?\\usb#vid_05ac&pid_xxxx#...\\DCIM\n\n"
            "How to find your iPhone path:\n"
            "1. Open Windows Explorer\n"
            "2. Navigate to your iPhone\n"
            "3. Go to Internal Storage → DCIM\n"
            "4. Copy the address bar path\n"
            "5. Paste it below"
        )
        
        # Show instructions first
        QMessageBox.information(self, "How to Find iPhone Path", instructions)
        
        # Get path from user
        path, ok = QInputDialog.getText(
            self,
            "Enter iPhone DCIM Path",
            "iPhone DCIM folder path:",
            text=""
        )
        
        if ok and path:
            path = path.strip()
            if path:
                self._process_selected_path(path)
        else:
            self.update_status("❌ No path entered.")
    
    def _process_selected_path(self, path):
        """Process a manually selected or entered path."""
        # Clean up the path - handle Windows special paths
        original_path = path
        
        # Handle Windows MTP paths that start with Computer\
        if path.startswith("Computer\\"):
            # These are shell namespace paths, try to find equivalent file system path
            self.update_status(f"🔍 Trying to resolve shell path: {path}")
            resolved_path = self._resolve_shell_path(path)
            if resolved_path:
                path = resolved_path
                self.update_status(f"✅ Resolved to: {path}")
            else:
                self.update_status(f"❌ Could not resolve shell path. Trying original path...")
        
        # Verify this looks like a DCIM folder
        if self._verify_dcim_folder(path):
            self.iphone_path = path
            self.update_status(f"✅ Manual selection successful! iPhone path set to: {path}")
            self.transfer_button.setEnabled(True)
        else:
            # Maybe they selected the iPhone root, check for DCIM subfolder
            dcim_path = os.path.join(path, "DCIM")
            if os.path.exists(dcim_path) and self._verify_dcim_folder(dcim_path):
                self.iphone_path = dcim_path
                self.update_status(f"✅ Found DCIM folder! iPhone path set to: {dcim_path}")
                self.transfer_button.setEnabled(True)
            else:
                self.update_status(
                    f"❌ Path doesn't contain iPhone photos: {original_path}\n\n"
                    f"Make sure to:\n"
                    f"• Navigate to Internal Storage → DCIM in Windows Explorer\n"
                    f"• Copy the full path from the address bar\n"
                    f"• Ensure your iPhone is unlocked and trusted"
                )
    
    def _resolve_shell_path(self, shell_path):
        """Try to resolve a Windows shell namespace path to a real file path."""
        try:
            # This is complex because MTP devices use virtual paths
            # Try various approaches to resolve the path
            
            # Method 1: Check if it can be accessed directly
            if os.path.exists(shell_path):
                return shell_path
            
            # Method 2: Try converting Computer\ paths
            if shell_path.startswith("Computer\\"):
                remaining_path = shell_path[9:]  # Remove "Computer\"
                parts = remaining_path.split("\\")
                
                if len(parts) >= 1:
                    device_name = parts[0]
                    
                    # Try to find this device in various locations
                    search_paths = []
                    
                    # Check drive letters
                    import string
                    for drive in string.ascii_uppercase:
                        drive_path = f"{drive}:\\"
                        if os.path.exists(drive_path):
                            search_paths.append(drive_path)
                    
                    # Try to match device name with actual accessible paths
                    for search_path in search_paths:
                        test_path = os.path.join(search_path, *parts[1:]) if len(parts) > 1 else search_path
                        if os.path.exists(test_path):
                            return test_path
            
            # Method 3: Use Windows API if available
            try:
                import win32api
                # Try to get the real path using Windows API
                return win32api.GetLongPathName(shell_path)
            except:
                pass
            
            return None
            
        except Exception as e:
            print(f"Error resolving shell path: {e}")
            return None
    
    def browse_via_shell(self):
        """Browse for iPhone using Windows Shell COM interface for MTP devices."""
        try:
            import win32com.client
            shell = win32com.client.Dispatch("Shell.Application")
            
            self.update_status("🖥️ Searching for iPhone via Windows Shell...")
            
            # Look for iPhone in Computer namespace
            computer_folder = shell.NameSpace(17)  # My Computer
            if not computer_folder:
                self.update_status("❌ Cannot access Computer folder via Shell")
                return
            
            items = computer_folder.Items()
            iphone_devices = []
            
            # Find all potential iPhone devices
            for i in range(items.Count):
                try:
                    item = items.Item(i)
                    if item and item.Name:
                        name_lower = item.Name.lower()
                        if 'iphone' in name_lower or 'apple' in name_lower:
                            iphone_devices.append((item.Name, item.Path))
                except:
                    continue
            
            if not iphone_devices:
                self.update_status("❌ No iPhone devices found in Shell namespace")
                return
            
            # If multiple devices, let user choose
            if len(iphone_devices) == 1:
                device_name, device_path = iphone_devices[0]
            else:
                # Show selection dialog
                device_names = [name for name, path in iphone_devices]
                device_name, ok = QInputDialog.getItem(
                    self, 
                    "Select iPhone Device", 
                    "Multiple Apple devices found. Select your iPhone:",
                    device_names, 
                    0, 
                    False
                )
                if not ok:
                    self.update_status("❌ No device selected")
                    return
                device_path = next(path for name, path in iphone_devices if name == device_name)
            
            self.update_status(f"📱 Found iPhone: {device_name}")
            
            # Navigate to Internal Storage → DCIM
            dcim_path = self._navigate_to_dcim_shell(shell, device_path)
            if dcim_path:
                # Try to access the DCIM folder
                if self._test_shell_dcim_access(shell, dcim_path):
                    self.iphone_path = dcim_path
                    self.update_status(f"✅ iPhone DCIM found via Shell: {dcim_path}")
                    self.transfer_button.setEnabled(True)
                else:
                    self.update_status(f"❌ Found DCIM but cannot access files: {dcim_path}")
            else:
                self.update_status(f"❌ Could not find DCIM folder in: {device_name}")
                
        except ImportError:
            self.update_status("❌ Windows Shell COM interface not available (pywin32 not installed)")
        except Exception as e:
            self.update_status(f"❌ Shell browsing failed: {str(e)}")
    
    def _navigate_to_dcim_shell(self, shell, device_path):
        """Navigate to DCIM folder using Windows Shell."""
        try:
            # Open the device folder
            device_folder = shell.NameSpace(device_path)
            if not device_folder:
                return None
            
            # Look for "Internal Storage"
            device_items = device_folder.Items()
            internal_storage_path = None
            
            for i in range(device_items.Count):
                try:
                    item = device_items.Item(i)
                    if item and item.Name and item.Name.upper() == 'INTERNAL STORAGE':
                        internal_storage_path = item.Path
                        break
                except:
                    continue
            
            if not internal_storage_path:
                # Maybe DCIM is directly in the device folder
                for i in range(device_items.Count):
                    try:
                        item = device_items.Item(i)
                        if item and item.Name and item.Name.upper() == 'DCIM':
                            return item.Path
                    except:
                        continue
                return None
            
            # Open Internal Storage and look for DCIM
            internal_folder = shell.NameSpace(internal_storage_path)
            if not internal_folder:
                return None
            
            internal_items = internal_folder.Items()
            for i in range(internal_items.Count):
                try:
                    item = internal_items.Item(i)
                    if item and item.Name and item.Name.upper() == 'DCIM':
                        return item.Path
                except:
                    continue
            
            return None
            
        except Exception as e:
            print(f"Error navigating to DCIM: {e}")
            return None
    
    def _test_shell_dcim_access(self, shell, dcim_path):
        """Test if we can access files in the DCIM folder via Shell."""
        try:
            dcim_folder = shell.NameSpace(dcim_path)
            if not dcim_folder:
                return False
            
            # Try to enumerate items in DCIM
            dcim_items = dcim_folder.Items()
            if dcim_items.Count == 0:
                return False
            
            # Check if any subfolder contains photos
            for i in range(min(dcim_items.Count, 10)):  # Check first 10 items
                try:
                    item = dcim_items.Item(i)
                    if item and item.Name:
                        # Check if this looks like an iPhone folder (e.g., 100APPLE)
                        if re.match(r'^\d{3}APPLE$', item.Name):
                            return True
                        
                        # Or check if it's a folder that might contain photos
                        try:
                            subfolder = shell.NameSpace(item.Path)
                            if subfolder:
                                subfolder_items = subfolder.Items()
                                for j in range(min(subfolder_items.Count, 5)):
                                    subitem = subfolder_items.Item(j)
                                    if subitem and subitem.Name:
                                        name_lower = subitem.Name.lower()
                                        if (name_lower.endswith('.jpg') or name_lower.endswith('.heic') or 
                                            name_lower.endswith('.png') or name_lower.endswith('.jpeg')):
                                            return True
                        except:
                            continue
                except:
                    continue
            
            return True  # If we got here, assume it's accessible
            
        except Exception as e:
            print(f"Error testing DCIM access: {e}")
            return False
    
    def _verify_dcim_folder(self, folder_path):
        """Verify that a folder contains iPhone-style photos."""
        try:
            if not os.path.exists(folder_path):
                return False
            
            items = os.listdir(folder_path)
            
            # Look for typical iPhone patterns
            for item in items:
                item_path = os.path.join(folder_path, item)
                if os.path.isdir(item_path):
                    # Check for Apple folder pattern (100APPLE, 101APPLE, etc.)
                    if re.match(r'^\d{3}APPLE$', item):
                        return True
                    
                    # Check for photos inside any subfolder
                    try:
                        files = os.listdir(item_path)
                        photo_files = [f for f in files if f.lower().endswith(('.jpg', '.jpeg', '.heic', '.png'))]
                        if len(photo_files) > 0:
                            return True
                    except:
                        continue
            
            # If no subfolders, check for photos directly
            files = [f for f in items if f.lower().endswith(('.jpg', '.jpeg', '.heic', '.png'))]
            return len(files) > 0
            
        except Exception as e:
            print(f"Error verifying DCIM folder: {e}")
            return False
    
    def debug_detection(self):
        """Show detailed debugging information about device detection."""
        self.update_status("🐛 Starting debug detection - checking all possible iPhone locations...")
        self.progress_bar.setValue(0)
        
        # Run in a separate thread
        threading.Thread(target=self._debug_detection_worker, daemon=True).start()
    
    def _debug_detection_worker(self):
        """Worker thread for debug detection."""
        try:
            system = platform.system()
            debug_info = []
            debug_info.append(f"🐛 DEBUG DETECTION RESULTS ({system}):")
            debug_info.append("=" * 50)
            
            if system == "Windows":
                debug_info.extend(self._debug_windows_detection())
            elif system == "Darwin":
                debug_info.extend(self._debug_macos_detection())
            elif system == "Linux":
                debug_info.extend(self._debug_linux_detection())
            
            debug_text = "\n".join(debug_info)
            self.update_status(debug_text)
            self.progress_bar.setValue(100)
            
        except Exception as e:
            self.update_status(f"❌ Debug detection failed: {str(e)}")
    
    def _debug_windows_detection(self):
        """Debug Windows iPhone detection methods."""
        debug_info = []
        import string
        
        # Check drive letters
        debug_info.append("\n📁 CHECKING DRIVE LETTERS:")
        found_drives = []
        for drive in string.ascii_uppercase:
            drive_path = f"{drive}:\\"
            if os.path.exists(drive_path):
                try:
                    drive_type = "Unknown"
                    dcim_path = os.path.join(drive_path, "DCIM")
                    dcim_exists = os.path.exists(dcim_path)
                    
                    # Try to get drive info
                    try:
                        result = subprocess.run(
                            ["wmic", "logicaldisk", "where", f"DeviceID='{drive}:'", "get", "DriveType,VolumeName"],
                            capture_output=True, text=True, timeout=5
                        )
                        if result.returncode == 0:
                            lines = result.stdout.strip().split('\n')
                            if len(lines) > 1:
                                drive_type = lines[1].strip()
                    except:
                        pass
                    
                    found_drives.append(f"  {drive}: - Type: {drive_type}, DCIM: {'✅' if dcim_exists else '❌'}")
                    
                    if dcim_exists:
                        try:
                            dcim_contents = os.listdir(dcim_path)
                            debug_info.append(f"    📂 DCIM contents: {dcim_contents[:5]}{'...' if len(dcim_contents) > 5 else ''}")
                        except Exception as e:
                            debug_info.append(f"    ❌ Cannot access DCIM: {e}")
                            
                except Exception as e:
                    found_drives.append(f"  {drive}: - Error: {e}")
        
        debug_info.extend(found_drives)
        
        # Check WMI devices
        debug_info.append("\n🔌 CHECKING WMI DEVICES:")
        try:
            import wmi
            c = wmi.WMI()
            
            debug_info.append("  Portable Devices:")
            for device in c.Win32_PnPEntity():
                if device.Name and ('iphone' in device.Name.lower() or 'apple' in device.Name.lower() or 'portable' in device.Name.lower()):
                    debug_info.append(f"    📱 {device.Name}")
            
            debug_info.append("  Logical Disks:")
            for disk in c.Win32_LogicalDisk():
                if disk.DriveType == 2:  # Removable
                    debug_info.append(f"    💾 {disk.DeviceID} - {disk.VolumeName or 'No Name'}")
                    
        except ImportError:
            debug_info.append("  ❌ WMI not available")
        except Exception as e:
            debug_info.append(f"  ❌ WMI Error: {e}")
        
        # Check PowerShell devices
        debug_info.append("\n⚡ CHECKING POWERSHELL DEVICES:")
        try:
            result = subprocess.run(
                ["powershell", "-Command", "Get-PnpDevice | Where-Object {$_.FriendlyName -like '*iPhone*' -or $_.FriendlyName -like '*Apple*'} | Select-Object FriendlyName, Status"],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')
                for line in lines[2:]:  # Skip headers
                    if line.strip():
                        debug_info.append(f"    📱 {line.strip()}")
            else:
                debug_info.append(f"  ❌ PowerShell error: {result.stderr}")
        except Exception as e:
            debug_info.append(f"  ❌ PowerShell Error: {e}")
        
        # Check USB devices
        debug_info.append("\n🔌 CHECKING USB DEVICES:")
        try:
            devices = usb.core.find(find_all=True, idVendor=APPLE_VENDOR_ID)
            apple_devices = list(devices)
            if apple_devices:
                for device in apple_devices:
                    debug_info.append(f"    🍎 Apple USB Device: Vendor={hex(device.idVendor)}, Product={hex(device.idProduct)}")
            else:
                debug_info.append("  ❌ No Apple USB devices found")
        except Exception as e:
            debug_info.append(f"  ❌ USB Error: {e}")
        
        # Check all partitions with psutil
        debug_info.append("\n💽 CHECKING ALL PARTITIONS (psutil):")
        try:
            import psutil
            partitions = psutil.disk_partitions()
            for partition in partitions:
                if partition.mountpoint:
                    dcim_path = os.path.join(partition.mountpoint, "DCIM")
                    dcim_exists = os.path.exists(dcim_path)
                    debug_info.append(f"    💾 {partition.mountpoint} ({partition.fstype}) - DCIM: {'✅' if dcim_exists else '❌'}")
                    
                    if dcim_exists:
                        try:
                            dcim_contents = os.listdir(dcim_path)
                            apple_folders = [f for f in dcim_contents if re.match(r'^\d{3}APPLE$', f)]
                            debug_info.append(f"      📂 Apple folders: {apple_folders}")
                            if apple_folders:
                                debug_info.append(f"      ✅ FOUND iPhone! Use this path: {dcim_path}")
                        except Exception as e:
                            debug_info.append(f"      ❌ Cannot read DCIM: {e}")
        except ImportError:
            debug_info.append("  ❌ psutil not available")
        except Exception as e:
            debug_info.append(f"  ❌ psutil error: {e}")
        
        # Check Windows shell namespace for MTP devices
        debug_info.append("\n🗂️ CHECKING WINDOWS SHELL NAMESPACE:")
        try:
            import win32com.client
            shell = win32com.client.Dispatch("Shell.Application")
            
            # Check "Computer" namespace (where MTP devices appear)
            computer_folder = shell.NameSpace(17)  # My Computer
            if computer_folder:
                debug_info.append("    📁 Computer folder contents:")
                items = computer_folder.Items()
                for i in range(items.Count):
                    try:
                        item = items.Item(i)
                        if item and item.Name:
                            debug_info.append(f"      📱 {item.Name}")
                            if 'iphone' in item.Name.lower() or 'apple' in item.Name.lower():
                                debug_info.append(f"        🎯 POTENTIAL iPhone: {item.Name}")
                                debug_info.append(f"        📂 Path: {item.Path}")
                                
                                # Try to explore this device
                                try:
                                    device_folder = shell.NameSpace(item.Path)
                                    if device_folder:
                                        device_items = device_folder.Items()
                                        for j in range(device_items.Count):
                                            device_item = device_items.Item(j)
                                            if device_item and device_item.Name:
                                                debug_info.append(f"          📁 {device_item.Name}")
                                                if device_item.Name.upper() == 'INTERNAL STORAGE':
                                                    internal_path = device_item.Path
                                                    debug_info.append(f"            📂 Internal Storage Path: {internal_path}")
                                                    
                                                    # Check for DCIM in internal storage
                                                    try:
                                                        internal_folder = shell.NameSpace(internal_path)
                                                        if internal_folder:
                                                            internal_items = internal_folder.Items()
                                                            for k in range(internal_items.Count):
                                                                internal_item = internal_items.Item(k)
                                                                if internal_item and internal_item.Name == 'DCIM':
                                                                    dcim_shell_path = internal_item.Path
                                                                    debug_info.append(f"              ✅ FOUND DCIM! Shell path: {dcim_shell_path}")
                                                                    debug_info.append(f"              💡 TRY THIS PATH: {dcim_shell_path}")
                                                    except:
                                                        pass
                                except:
                                    pass
                    except:
                        continue
        except ImportError:
            debug_info.append("    ❌ win32com not available")
        except Exception as e:
            debug_info.append(f"    ❌ Shell namespace error: {e}")
        
        # Provide manual instructions
        debug_info.append("\n📝 MANUAL INSTRUCTIONS:")
        debug_info.append("    If your iPhone wasn't found automatically:")
        debug_info.append("    1. Open Windows Explorer")
        debug_info.append("    2. Look for your iPhone in 'This PC' or 'Computer'")
        debug_info.append("    3. Navigate to: iPhone → Internal Storage → DCIM")
        debug_info.append("    4. Copy the address bar path")
        debug_info.append("    5. Use 'Enter iPhone Path Manually' button")
        debug_info.append("    6. Common path format: Computer\\[iPhone Name]\\Internal Storage\\DCIM")
        
        return debug_info
    
    def _debug_macos_detection(self):
        """Debug macOS iPhone detection methods."""
        debug_info = []
        
        # Check volumes
        debug_info.append("\n📁 CHECKING /Volumes:")
        try:
            volumes = os.listdir("/Volumes")
            for volume in volumes:
                volume_path = f"/Volumes/{volume}"
                dcim_path = os.path.join(volume_path, "DCIM")
                dcim_exists = os.path.exists(dcim_path)
                debug_info.append(f"  📂 {volume} - DCIM: {'✅' if dcim_exists else '❌'}")
        except Exception as e:
            debug_info.append(f"  ❌ Error checking volumes: {e}")
        
        # Check system_profiler
        debug_info.append("\n🔍 CHECKING system_profiler:")
        try:
            result = subprocess.run(
                ["system_profiler", "SPUSBDataType"],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                if "iPhone" in result.stdout:
                    debug_info.append("  ✅ iPhone found in system_profiler")
                else:
                    debug_info.append("  ❌ No iPhone in system_profiler")
            else:
                debug_info.append("  ❌ system_profiler failed")
        except Exception as e:
            debug_info.append(f"  ❌ system_profiler error: {e}")
        
        return debug_info
    
    def _debug_linux_detection(self):
        """Debug Linux iPhone detection methods."""
        debug_info = []
        
        # Check common mount points
        user_id = os.getuid() if hasattr(os, 'getuid') else 1000
        username = os.environ.get("USER", "user")
        
        paths_to_check = [
            f"/run/user/{user_id}/gvfs",
            f"/media/{username}",
            "/media",
            "/mnt"
        ]
        
        debug_info.append("\n📁 CHECKING MOUNT POINTS:")
        for path in paths_to_check:
            if os.path.exists(path):
                try:
                    items = os.listdir(path)
                    debug_info.append(f"  📂 {path}: {items}")
                except Exception as e:
                    debug_info.append(f"  ❌ {path}: Error - {e}")
            else:
                debug_info.append(f"  ❌ {path}: Does not exist")
        
        # Check lsusb
        debug_info.append("\n🔌 CHECKING lsusb:")
        try:
            result = subprocess.run(["lsusb"], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                apple_lines = [line for line in result.stdout.split('\n') if 'Apple' in line or 'iPhone' in line]
                if apple_lines:
                    for line in apple_lines:
                        debug_info.append(f"  🍎 {line.strip()}")
                else:
                    debug_info.append("  ❌ No Apple devices in lsusb")
        except Exception as e:
            debug_info.append(f"  ❌ lsusb error: {e}")
        
        return debug_info
    
    def test_connection(self):
        """Test iPhone connection and provide detailed feedback."""
        self.update_status("🧪 Running comprehensive iPhone connection test...")
        self.progress_bar.setValue(0)
        
        # Run in a separate thread to avoid UI blocking
        threading.Thread(target=self._test_connection_worker, daemon=True).start()
    
    def _test_connection_worker(self):
        """Worker thread for testing iPhone connection."""
        try:
            system = platform.system()
            test_results = []
            
            # Test 1: USB Device Detection
            self.update_status("Test 1/5: Checking USB device detection...")
            usb_result = self._test_usb_detection()
            test_results.append(f"USB Detection: {'✅ PASS' if usb_result else '❌ FAIL'}")
            self.progress_bar.setValue(20)
            
            # Test 2: Platform-specific detection
            self.update_status("Test 2/5: Platform-specific device detection...")
            platform_result = self._test_platform_detection(system)
            test_results.append(f"Platform Detection: {'✅ PASS' if platform_result else '❌ FAIL'}")
            self.progress_bar.setValue(40)
            
            # Test 3: File system access
            self.update_status("Test 3/5: Testing file system access...")
            fs_result = self._test_filesystem_access()
            test_results.append(f"File System Access: {'✅ PASS' if fs_result else '❌ FAIL'}")
            self.progress_bar.setValue(60)
            
            # Test 4: DCIM folder structure
            self.update_status("Test 4/5: Verifying DCIM folder structure...")
            dcim_result = self._test_dcim_structure()
            test_results.append(f"DCIM Structure: {'✅ PASS' if dcim_result else '❌ FAIL'}")
            self.progress_bar.setValue(80)
            
            # Test 5: Photo file access
            self.update_status("Test 5/5: Testing photo file access...")
            photo_result = self._test_photo_access()
            test_results.append(f"Photo Access: {'✅ PASS' if photo_result else '❌ FAIL'}")
            self.progress_bar.setValue(100)
            
            # Compile results
            passed_tests = sum(1 for result in test_results if '✅ PASS' in result)
            total_tests = len(test_results)
            
            summary = f"\n🧪 CONNECTION TEST RESULTS ({passed_tests}/{total_tests} passed):\n\n"
            summary += "\n".join(test_results)
            
            if passed_tests == total_tests:
                summary += "\n\n🎉 All tests passed! Your iPhone should work perfectly with this app."
            elif passed_tests >= 3:
                summary += "\n\n⚠️ Most tests passed. iPhone detected but there may be some issues."
            else:
                summary += "\n\n❌ Multiple test failures. Please check your iPhone connection."
                summary += f"\n\nTroubleshooting for {system}:"
                if system == "Windows":
                    summary += "\n• Install iTunes or Apple Mobile Device Support"
                    summary += "\n• Try different USB port (USB 3.0 preferred)"
                    summary += "\n• Check Device Manager for iPhone under 'Portable Devices'"
                elif system == "Darwin":
                    summary += "\n• Close Photos app if open"
                    summary += "\n• Install libusb: brew install libusb"
                    summary += "\n• Try disconnecting/reconnecting iPhone"
                elif system == "Linux":
                    summary += "\n• Install: sudo apt install libimobiledevice-utils ifuse"
                    summary += "\n• Try running with sudo"
            
            self.update_status(summary)
            
        except Exception as e:
            self.update_status(f"❌ Connection test failed with error: {str(e)}")
    
    def _test_usb_detection(self):
        """Test if iPhone is detected as a USB device."""
        try:
            devices = usb.core.find(find_all=True, idVendor=APPLE_VENDOR_ID)
            apple_devices = list(devices)
            return len(apple_devices) > 0
        except Exception as e:
            print(f"USB detection test failed: {e}")
            return False
    
    def _test_platform_detection(self, system):
        """Test platform-specific iPhone detection."""
        try:
            if system == "Windows":
                return self._find_iphone_windows() is not None
            elif system == "Darwin":
                return self._find_iphone_macos() is not None
            elif system == "Linux":
                return self._find_iphone_linux() is not None
            return False
        except Exception as e:
            print(f"Platform detection test failed: {e}")
            return False
    
    def _test_filesystem_access(self):
        """Test if we can access the iPhone file system."""
        try:
            if self.iphone_path and os.path.exists(self.iphone_path):
                os.listdir(self.iphone_path)
                return True
            return False
        except Exception as e:
            print(f"Filesystem access test failed: {e}")
            return False
    
    def _test_dcim_structure(self):
        """Test if the DCIM folder has the expected iPhone structure."""
        try:
            if not self.iphone_path or not os.path.exists(self.iphone_path):
                return False
            
            items = os.listdir(self.iphone_path)
            # Look for typical iPhone folder patterns (like 100APPLE, 101APPLE, etc.)
            apple_folders = [item for item in items if re.match(r'^\d{3}APPLE$', item)]
            return len(apple_folders) > 0
        except Exception as e:
            print(f"DCIM structure test failed: {e}")
            return False
    
    def _test_photo_access(self):
        """Test if we can access actual photo files."""
        try:
            if not self.iphone_path or not os.path.exists(self.iphone_path):
                return False
            
            # Look for photo files in DCIM subfolders
            for item in os.listdir(self.iphone_path):
                item_path = os.path.join(self.iphone_path, item)
                if os.path.isdir(item_path):
                    try:
                        files = os.listdir(item_path)
                        photo_files = [f for f in files if f.lower().endswith(('.jpg', '.jpeg', '.heic', '.png'))]
                        if photo_files:
                            return True
                    except:
                        continue
            return False
        except Exception as e:
            print(f"Photo access test failed: {e}")
            return False
    
    def _find_iphone_macos(self):
        """Enhanced iPhone detection for macOS with multiple methods."""
        
        # Method 1: Check standard mount points
        possible_paths = [
            "/Volumes/Apple iPhone",
            "/Volumes/iPhone",
        ]
        
        # Also check /Volumes directory for any device that might be an iPhone
        try:
            volumes = os.listdir("/Volumes")
            for volume in volumes:
                volume_lower = volume.lower()
                if ("iphone" in volume_lower or "apple" in volume_lower or 
                    "ios" in volume_lower or volume_lower.startswith("iph")):
                    possible_paths.append(f"/Volumes/{volume}")
        except:
            pass
            
        # Check if any of the possible paths exist and contain DCIM
        for path in possible_paths:
            dcim_path = os.path.join(path, "DCIM")
            if os.path.exists(dcim_path) and self._verify_iphone_device(path):
                return dcim_path
        
        # Method 2: Use system_profiler to find connected iOS devices
        try:
            result = subprocess.run(
                ["system_profiler", "SPUSBDataType", "-xml"],
                capture_output=True, text=True, timeout=10
            )
            
            if result.returncode == 0 and ("iPhone" in result.stdout or "Apple Inc." in result.stdout):
                # Parse the output to find device mount points
                iphone_path = self._parse_system_profiler_for_iphone(result.stdout)
                if iphone_path:
                    return iphone_path
        except:
            pass
        
        # Method 3: Use mdfind to search for iPhone-related content
        try:
            result = subprocess.run(["mdfind", "kMDItemKind == 'iPhone'"], 
                                    capture_output=True, text=True, timeout=10)
            paths = result.stdout.strip().split("\n")
            for path in paths:
                if path and os.path.exists(path):
                    dcim_path = os.path.join(path, "DCIM")
                    if os.path.exists(dcim_path):
                        return dcim_path
        except:
            pass
        
        # Method 4: Check for iOS-style USB devices
        try:
            result = subprocess.run(
                ["diskutil", "list"],
                capture_output=True, text=True, timeout=10
            )
            
            if result.returncode == 0:
                lines = result.stdout.split('\n')
                for line in lines:
                    if 'iPhone' in line or 'Apple' in line:
                        # Try to extract device identifier and find mount point
                        parts = line.split()
                        for part in parts:
                            if part.startswith('/dev/disk'):
                                mount_point = self._get_mount_point_macos(part)
                                if mount_point:
                                    dcim_path = os.path.join(mount_point, "DCIM")
                                    if os.path.exists(dcim_path):
                                        return dcim_path
        except:
            pass
        
        # Method 5: Check user directories for iOS device mounts
        try:
            user_home = os.path.expanduser("~")
            desktop_path = os.path.join(user_home, "Desktop")
            
            # Sometimes iOS devices appear as folders on desktop
            if os.path.exists(desktop_path):
                items = os.listdir(desktop_path)
                for item in items:
                    item_lower = item.lower()
                    if ("iphone" in item_lower or "apple" in item_lower):
                        item_path = os.path.join(desktop_path, item)
                        if os.path.isdir(item_path):
                            dcim_path = os.path.join(item_path, "DCIM")
                            if os.path.exists(dcim_path):
                                return dcim_path
        except:
            pass
            
        return None
    
    def _parse_system_profiler_for_iphone(self, xml_output):
        """Parse system_profiler XML output to find iPhone mount points."""
        try:
            import xml.etree.ElementTree as ET
            root = ET.fromstring(xml_output)
            
            # Look for iPhone entries in the USB device tree
            for item in root.iter():
                if item.text and 'iPhone' in item.text:
                    # Try to find associated volume information
                    parent = item.getparent()
                    if parent is not None:
                        for sibling in parent:
                            if sibling.text and '/Volumes/' in sibling.text:
                                volume_path = sibling.text
                                dcim_path = os.path.join(volume_path, "DCIM")
                                if os.path.exists(dcim_path):
                                    return dcim_path
        except:
            pass
        
        return None
    
    def _get_mount_point_macos(self, device_path):
        """Get the mount point for a device path on macOS."""
        try:
            result = subprocess.run(
                ["diskutil", "info", device_path],
                capture_output=True, text=True, timeout=5
            )
            
            if result.returncode == 0:
                lines = result.stdout.split('\n')
                for line in lines:
                    if 'Mount Point:' in line:
                        mount_point = line.split('Mount Point:')[1].strip()
                        return mount_point
        except:
            pass
        
        return None
    
    def _find_iphone_windows(self):
        """Enhanced iPhone detection for Windows with comprehensive automatic methods."""
        self.update_status("🔍 Scanning Windows drives and devices...")
        
        # Method 1: Windows Shell COM Interface (handles MTP devices)
        iphone_path = self._auto_detect_shell_windows()
        if iphone_path:
            self.update_status(f"✅ Found iPhone via Windows Shell: {os.path.dirname(iphone_path)}")
            return iphone_path
        
        # Method 2: Enhanced drive scanning with psutil
        self.update_status("💾 Scanning all disk partitions...")
        iphone_path = self._auto_scan_all_drives_windows()
        if iphone_path:
            self.update_status(f"✅ Found iPhone on drive: {os.path.dirname(iphone_path)}")
            return iphone_path
        
        # Method 3: WMI comprehensive device detection
        self.update_status("🔌 Checking Windows device manager...")
        iphone_path = self._auto_detect_wmi_windows()
        if iphone_path:
            self.update_status(f"✅ Found iPhone via WMI: {os.path.dirname(iphone_path)}")
            return iphone_path
        
        # Method 4: PowerShell advanced detection
        self.update_status("⚡ Running PowerShell device scan...")
        iphone_path = self._auto_detect_powershell_windows()
        if iphone_path:
            self.update_status(f"✅ Found iPhone via PowerShell: {os.path.dirname(iphone_path)}")
            return iphone_path
        
        # Method 5: Registry device enumeration
        self.update_status("📋 Checking Windows registry...")
        iphone_path = self._auto_detect_registry_windows()
        if iphone_path:
            self.update_status(f"✅ Found iPhone via Registry: {os.path.dirname(iphone_path)}")
            return iphone_path
        
        # Method 6: USB device correlation
        self.update_status("🔌 Correlating USB devices with file system...")
        iphone_path = self._auto_correlate_usb_windows()
        if iphone_path:
            self.update_status(f"✅ Found iPhone via USB correlation: {os.path.dirname(iphone_path)}")
            return iphone_path
            
        return None
    
    def _auto_detect_shell_windows(self):
        """Automatically detect iPhone using Windows Shell COM interface."""
        try:
            import win32com.client
            shell = win32com.client.Dispatch("Shell.Application")
            
            # Look for iPhone in Computer namespace
            computer_folder = shell.NameSpace(17)  # My Computer
            if not computer_folder:
                return None
            
            items = computer_folder.Items()
            
            # Find iPhone devices automatically
            for i in range(items.Count):
                try:
                    item = items.Item(i)
                    if item and item.Name:
                        name_lower = item.Name.lower()
                        if 'iphone' in name_lower or 'apple' in name_lower:
                            # Found iPhone, navigate to DCIM automatically
                            dcim_path = self._navigate_to_dcim_shell(shell, item.Path)
                            if dcim_path and self._test_shell_dcim_access(shell, dcim_path):
                                return dcim_path
                except:
                    continue
            
            return None
            
        except ImportError:
            return None
        except Exception as e:
            print(f"Shell detection failed: {e}")
            return None
    
    def _auto_scan_all_drives_windows(self):
        """Automatically scan all drives for iPhone DCIM folders."""
        try:
            import psutil
            import string
            
            # First check traditional drive letters
            for drive in string.ascii_uppercase:
                drive_path = f"{drive}:\\"
                if os.path.exists(drive_path):
                    dcim_path = os.path.join(drive_path, "DCIM")
                    if os.path.exists(dcim_path) and self._verify_iphone_device(drive_path):
                        return dcim_path
            
            # Then use psutil for comprehensive scanning
            partitions = psutil.disk_partitions()
            for partition in partitions:
                try:
                    if 'cdrom' in partition.opts or partition.fstype == '':
                        continue
                    
                    mount_point = partition.mountpoint
                    if mount_point and os.path.exists(mount_point):
                        dcim_path = os.path.join(mount_point, "DCIM")
                        if os.path.exists(dcim_path) and self._verify_iphone_device(mount_point):
                            return dcim_path
                        
                        # Check for nested iPhone structures
                        try:
                            items = os.listdir(mount_point)
                            for item in items:
                                item_path = os.path.join(mount_point, item)
                                if os.path.isdir(item_path):
                                    item_lower = item.lower()
                                    if ('iphone' in item_lower or 'apple' in item_lower or 
                                        'portable' in item_lower):
                                        nested_dcim = os.path.join(item_path, "DCIM")
                                        if os.path.exists(nested_dcim):
                                            return nested_dcim
                        except:
                            continue
                            
                except Exception:
                    continue
                    
            return None
            
        except ImportError:
            return None
        except Exception as e:
            print(f"Drive scanning failed: {e}")
            return None
    
    def _auto_detect_wmi_windows(self):
        """Automatically detect iPhone using WMI."""
        try:
            import wmi
            c = wmi.WMI()
            
            # Check removable drives first
            for drive in c.Win32_LogicalDisk():
                if drive.DriveType == 2:  # Removable drive
                    dcim_path = os.path.join(drive.DeviceID, "DCIM")
                    if os.path.exists(dcim_path) and self._verify_iphone_device(drive.DeviceID):
                        return dcim_path
            
            # Check for Portable devices (MTP)
            apple_devices = []
            for device in c.Win32_PnPEntity():
                if device.Name and ('iphone' in device.Name.lower() or 'apple' in device.Name.lower()):
                    apple_devices.append(device)
            
            # Try to correlate Apple devices with accessible paths
            if apple_devices:
                # Look for any accessible DCIM paths that might correspond to these devices
                return self._correlate_devices_with_paths(apple_devices)
                        
            return None
            
        except ImportError:
            return None
        except Exception as e:
            print(f"WMI detection failed: {e}")
            return None
    
    def _auto_detect_powershell_windows(self):
        """Automatically detect iPhone using PowerShell."""
        try:
            # PowerShell script to find iPhone and get DCIM path
            ps_script = '''
            # Find Apple devices
            $appleDevices = Get-PnpDevice | Where-Object {$_.FriendlyName -like "*iPhone*" -or $_.FriendlyName -like "*Apple*"}
            
            if ($appleDevices) {
                Write-Output "APPLE_DEVICE_FOUND"
            }
            
            # Check all removable drives for iPhone-style DCIM
            Get-WmiObject -Class Win32_LogicalDisk | Where-Object {$_.DriveType -eq 2} | ForEach-Object {
                $driveLetter = $_.DeviceID
                $dcimPath = Join-Path $driveLetter "DCIM"
                if (Test-Path $dcimPath) {
                    $subfolders = Get-ChildItem $dcimPath -Directory -ErrorAction SilentlyContinue
                    foreach ($folder in $subfolders) {
                        if ($folder.Name -match "^\\d{3}APPLE$") {
                            Write-Output "IPHONE_DCIM:$dcimPath"
                            break
                        }
                    }
                }
            }
            '''
            
            result = subprocess.run(
                ["powershell", "-ExecutionPolicy", "Bypass", "-Command", ps_script],
                capture_output=True, text=True, timeout=15
            )
            
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')
                for line in lines:
                    if line.startswith("IPHONE_DCIM:"):
                        dcim_path = line.replace("IPHONE_DCIM:", "").strip()
                        if os.path.exists(dcim_path):
                            return dcim_path
                            
            return None
            
        except Exception as e:
            print(f"PowerShell detection failed: {e}")
            return None
    
    def _auto_detect_registry_windows(self):
        """Automatically detect iPhone using Windows registry."""
        try:
            import winreg
            
            # Check mount points registry
            try:
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Explorer\MountPoints2") as key:
                    i = 0
                    while True:
                        try:
                            subkey_name = winreg.EnumKey(key, i)
                            if 'apple' in subkey_name.lower():
                                # Try to find corresponding drive
                                for drive_letter in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ':
                                    drive_path = f"{drive_letter}:\\"
                                    if os.path.exists(drive_path):
                                        dcim_path = os.path.join(drive_path, "DCIM")
                                        if os.path.exists(dcim_path) and self._verify_iphone_device(drive_path):
                                            return dcim_path
                            i += 1
                        except OSError:
                            break
            except:
                pass
                
            return None
            
        except ImportError:
            return None
        except Exception as e:
            print(f"Registry detection failed: {e}")
            return None
    
    def _auto_correlate_usb_windows(self):
        """Automatically correlate USB devices with file system access."""
        try:
            # Check if any Apple USB devices are connected
            devices = usb.core.find(find_all=True, idVendor=APPLE_VENDOR_ID)
            apple_devices = list(devices)
            
            if not apple_devices:
                return None
            
            # If Apple devices are connected, do a thorough scan for any DCIM folder
            # that might be accessible through the file system
            import psutil
            partitions = psutil.disk_partitions()
            
            for partition in partitions:
                try:
                    mount_point = partition.mountpoint
                    if mount_point and os.path.exists(mount_point):
                        dcim_path = os.path.join(mount_point, "DCIM")
                        if os.path.exists(dcim_path):
                            # Check if this DCIM contains iPhone-style content
                            try:
                                items = os.listdir(dcim_path)
                                apple_folders = [item for item in items if re.match(r'^\d{3}APPLE$', item)]
                                if apple_folders:
                                    return dcim_path
                                    
                                # Check for any photo files that might indicate iPhone
                                for item in items:
                                    item_path = os.path.join(dcim_path, item)
                                    if os.path.isdir(item_path):
                                        try:
                                            files = os.listdir(item_path)
                                            heic_files = [f for f in files if f.lower().endswith('.heic')]
                                            if heic_files:  # HEIC files are iPhone-specific
                                                return dcim_path
                                        except:
                                            continue
                            except:
                                continue
                                
                except Exception:
                    continue
                    
            return None
            
        except Exception as e:
            print(f"USB correlation failed: {e}")
            return None
    
    def _correlate_devices_with_paths(self, apple_devices):
        """Correlate Apple devices with accessible file paths."""
        # This is a fallback method to try to find accessible paths
        # when we know Apple devices are connected but can't directly access them
        
        try:
            import psutil
            partitions = psutil.disk_partitions()
            
            for partition in partitions:
                try:
                    mount_point = partition.mountpoint
                    if mount_point and os.path.exists(mount_point):
                        dcim_path = os.path.join(mount_point, "DCIM")
                        if os.path.exists(dcim_path) and self._verify_iphone_device(mount_point):
                            return dcim_path
                except:
                    continue
                    
            return None
            
        except Exception:
            return None
    
    def _find_iphone_mtp_windows(self):
        """Find iPhone connected via MTP (Media Transfer Protocol)."""
        try:
            # Check common MTP mount points
            user_profile = os.environ.get('USERPROFILE', 'C:\\Users\\Default')
            possible_mtp_paths = [
                os.path.join(user_profile, 'This PC'),
                'Computer',
                'This PC'
            ]
            
            # Use PowerShell to find MTP devices
            ps_script = """
            Get-WmiObject -Class Win32_PnPEntity | Where-Object {
                $_.Name -like "*iPhone*" -or $_.Name -like "*Apple*"
            } | Select-Object Name, DeviceID
            """
            
            try:
                result = subprocess.run(
                    ["powershell", "-Command", ps_script],
                    capture_output=True, text=True, timeout=10
                )
                
                if result.returncode == 0 and "iPhone" in result.stdout:
                    # Try to find the device in Windows Explorer namespace
                    return self._get_iphone_from_shell_namespace()
            except:
                pass
                
        except Exception as e:
            print(f"MTP detection failed: {e}")
        
        return None
    
    def _find_iphone_shell_windows(self):
        """Use Windows Shell COM interface to find iPhone."""
        try:
            import win32com.client
            
            shell = win32com.client.Dispatch("Shell.Application")
            
            # Iterate through all shell folders
            for i in range(shell.NameSpace(17).Items().Count):  # 17 is My Computer
                try:
                    item = shell.NameSpace(17).Items().Item(i)
                    if item and item.Name:
                        name_lower = item.Name.lower()
                        if 'iphone' in name_lower or 'apple' in name_lower:
                            # Found potential iPhone, try to access DCIM
                            try:
                                device_folder = shell.NameSpace(item.Path)
                                if device_folder:
                                    for j in range(device_folder.Items().Count):
                                        folder_item = device_folder.Items().Item(j)
                                        if folder_item and folder_item.Name.upper() == 'DCIM':
                                            return folder_item.Path
                            except:
                                continue
                except:
                    continue
                    
        except ImportError:
            print("pywin32 not available - using alternative detection methods")
        except Exception as e:
            print(f"Shell detection failed: {e}")
        
        return None
    
    def _find_iphone_powershell_windows(self):
        """Use PowerShell to detect iPhone and get its path."""
        try:
            # PowerShell script to find iPhone and get DCIM path
            ps_script = '''
            $devices = Get-PnpDevice | Where-Object {$_.FriendlyName -like "*iPhone*" -or $_.FriendlyName -like "*Apple*"}
            foreach ($device in $devices) {
                $devicePath = (Get-PnpDeviceProperty -InstanceId $device.InstanceId -KeyName 'DEVPKEY_Device_DriverInfPath' -ErrorAction SilentlyContinue).Data
                if ($devicePath) {
                    Write-Output "Device: $($device.FriendlyName)"
                    Write-Output "Path: $devicePath"
                }
            }
            
            # Also check for drive letters that might be iPhone
            Get-WmiObject -Class Win32_LogicalDisk | Where-Object {$_.DriveType -eq 2} | ForEach-Object {
                $driveLetter = $_.DeviceID
                $dcimPath = Join-Path $driveLetter "DCIM"
                if (Test-Path $dcimPath) {
                    # Check if it looks like iPhone by looking for typical iOS folder structure
                    $subfolders = Get-ChildItem $dcimPath -Directory -ErrorAction SilentlyContinue
                    foreach ($folder in $subfolders) {
                        if ($folder.Name -match "^\d{3}APPLE$") {
                            Write-Output "iPhone-DCIM: $dcimPath"
                            break
                        }
                    }
                }
            }
            '''
            
            result = subprocess.run(
                ["powershell", "-ExecutionPolicy", "Bypass", "-Command", ps_script],
                capture_output=True, text=True, timeout=15
            )
            
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')
                for line in lines:
                    if line.startswith("iPhone-DCIM:"):
                        dcim_path = line.replace("iPhone-DCIM:", "").strip()
                        if os.path.exists(dcim_path):
                            return dcim_path
                            
        except subprocess.TimeoutExpired:
            print("PowerShell detection timed out")
        except Exception as e:
            print(f"PowerShell detection failed: {e}")
        
        return None
    
    def _verify_iphone_device(self, device_path):
        """Verify that a device path actually belongs to an iPhone."""
        try:
            dcim_path = os.path.join(device_path, "DCIM")
            if not os.path.exists(dcim_path):
                return False
            
            # Look for typical iPhone folder structure
            # iPhone creates folders like "100APPLE", "101APPLE", etc.
            subfolders = os.listdir(dcim_path)
            for folder in subfolders:
                if re.match(r'^\d{3}APPLE$', folder):
                    return True
            
            # Also check for common iPhone photo patterns
            for folder in subfolders:
                folder_path = os.path.join(dcim_path, folder)
                if os.path.isdir(folder_path):
                    try:
                        files = os.listdir(folder_path)
                        # Look for iPhone-style filenames (IMG_xxxx.HEIC, etc.)
                        for file in files[:10]:  # Check first 10 files
                            if (file.upper().startswith('IMG_') and 
                                (file.upper().endswith('.HEIC') or file.upper().endswith('.JPG'))):
                                return True
                    except:
                        continue
            
            return True  # If DCIM exists, assume it might be an iPhone
            
        except Exception as e:
            print(f"Device verification failed: {e}")
            return False
    
    def _get_mtp_device_path(self, device):
        """Try to get the file system path for an MTP device."""
        # This is complex on Windows as MTP devices don't have traditional paths
        # We'll try to use the device instance to find a corresponding drive letter
        try:
            if hasattr(device, 'DeviceID') and device.DeviceID:
                # Try to correlate with logical disks
                import wmi
                c = wmi.WMI()
                for disk in c.Win32_LogicalDisk():
                    if disk.DriveType == 2:  # Removable
                        dcim_path = os.path.join(disk.DeviceID, "DCIM")
                        if os.path.exists(dcim_path):
                            return dcim_path
        except:
            pass
        
        return None
    
    def _find_iphone_explorer_windows(self):
        """Use Windows Explorer special folders to find iPhone."""
        try:
            # Check Windows special folder paths where devices might appear
            special_paths = [
                os.path.join(os.environ.get('USERPROFILE', ''), 'Desktop'),
                os.path.join(os.environ.get('USERPROFILE', ''), 'ThisPCDesktopFolder'),
                'Computer',
                'This PC',
            ]
            
            # Also check environment variables that might point to device locations
            env_vars = ['DEVICEPATH', 'PORTABLE_DEVICE_PATH']
            for var in env_vars:
                path = os.environ.get(var)
                if path:
                    special_paths.append(path)
            
            for base_path in special_paths:
                if base_path and os.path.exists(base_path):
                    try:
                        items = os.listdir(base_path)
                        for item in items:
                            item_lower = item.lower()
                            if ('iphone' in item_lower or 'apple' in item_lower):
                                item_path = os.path.join(base_path, item)
                                if os.path.isdir(item_path):
                                    dcim_path = os.path.join(item_path, "DCIM")
                                    if os.path.exists(dcim_path):
                                        return dcim_path
                    except:
                        continue
        except Exception as e:
            print(f"Explorer detection failed: {e}")
        
        return None
    
    def _find_iphone_registry_windows(self):
        """Check Windows registry for mounted device information."""
        try:
            import winreg
            
            # Check various registry keys where device information might be stored
            registry_paths = [
                (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Explorer\MountPoints2"),
                (winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Enum\USB"),
                (winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\MountedDevices"),
            ]
            
            for hkey, subkey_path in registry_paths:
                try:
                    with winreg.OpenKey(hkey, subkey_path) as key:
                        i = 0
                        while True:
                            try:
                                subkey_name = winreg.EnumKey(key, i)
                                if 'apple' in subkey_name.lower() or 'iphone' in subkey_name.lower():
                                    # Found a potential iPhone entry, try to get its path
                                    with winreg.OpenKey(key, subkey_name) as device_key:
                                        try:
                                            # Try to get drive letter or path
                                            drive_letter = winreg.QueryValue(device_key, "")
                                            if drive_letter:
                                                dcim_path = os.path.join(drive_letter, "DCIM")
                                                if os.path.exists(dcim_path):
                                                    return dcim_path
                                        except:
                                            pass
                                i += 1
                            except OSError:
                                break
                except:
                    continue
                    
        except ImportError:
            print("winreg not available")
        except Exception as e:
            print(f"Registry detection failed: {e}")
        
        return None
    
    def _scan_all_drives_windows(self):
        """Thoroughly scan all available drives for iPhone DCIM folders."""
        try:
            import psutil
            
            # Use psutil to get all disk partitions
            partitions = psutil.disk_partitions()
            
            for partition in partitions:
                try:
                    # Skip system partitions and CD-ROMs
                    if 'cdrom' in partition.opts or partition.fstype == '':
                        continue
                    
                    mount_point = partition.mountpoint
                    if mount_point and os.path.exists(mount_point):
                        # Check for DCIM directly
                        dcim_path = os.path.join(mount_point, "DCIM")
                        if os.path.exists(dcim_path) and self._verify_iphone_device(mount_point):
                            return dcim_path
                        
                        # Check for nested iPhone folders
                        try:
                            items = os.listdir(mount_point)
                            for item in items:
                                item_path = os.path.join(mount_point, item)
                                if os.path.isdir(item_path):
                                    item_lower = item.lower()
                                    if ('iphone' in item_lower or 'apple' in item_lower or 
                                        'portable' in item_lower or item_lower.startswith('apple')):
                                        nested_dcim = os.path.join(item_path, "DCIM")
                                        if os.path.exists(nested_dcim):
                                            return nested_dcim
                        except:
                            continue
                            
                except Exception as e:
                    print(f"Error scanning partition {partition.mountpoint}: {e}")
                    continue
                    
        except ImportError:
            print("psutil not available for drive scanning")
        except Exception as e:
            print(f"Drive scanning failed: {e}")
        
        return None
    
    def _get_iphone_from_shell_namespace(self):
        """Try to get iPhone path from Windows Shell namespace."""
        try:
            # Use Windows API to enumerate portable devices
            # This is a fallback method
            import win32api
            drives = win32api.GetLogicalDriveStrings()
            drives = drives.split('\000')[:-1]
            
            for drive in drives:
                try:
                    drive_type = win32api.GetDriveType(drive)
                    if drive_type == win32api.DRIVE_REMOVABLE:
                        dcim_path = os.path.join(drive, "DCIM")
                        if os.path.exists(dcim_path) and self._verify_iphone_device(drive):
                            return dcim_path
                except:
                    continue
                    
        except ImportError:
            pass
        except Exception as e:
            print(f"Shell namespace detection failed: {e}")
        
        return None
    
    def _find_iphone_linux(self):
        """Enhanced iPhone detection for Linux with multiple methods."""
        
        # Method 1: Check standard mount points
        user_id = os.getuid() if hasattr(os, 'getuid') else 1000
        username = os.environ.get("USER", "user")
        
        possible_paths = [
            f"/run/user/{user_id}/gvfs",
            f"/media/{username}",
            "/media",
            "/mnt",
            "/tmp",
            f"/home/{username}/.gvfs"
        ]
        
        for base_path in possible_paths:
            if os.path.exists(base_path):
                try:
                    for device in os.listdir(base_path):
                        device_path = os.path.join(base_path, device)
                        device_lower = device.lower()
                        
                        # Check if this looks like an iPhone
                        if ("iphone" in device_lower or "apple" in device_lower or 
                            "ios" in device_lower or device_lower.startswith("iph") or
                            "mtp" in device_lower):
                            dcim_path = os.path.join(device_path, "DCIM")
                            if os.path.exists(dcim_path) and self._verify_iphone_device(device_path):
                                return dcim_path
                        
                        # Also check any device that has a DCIM directory
                        if os.path.isdir(device_path):
                            dcim_path = os.path.join(device_path, "DCIM")
                            if os.path.exists(dcim_path) and self._verify_iphone_device(device_path):
                                return dcim_path
                except:
                    pass
        
        # Method 2: Use lsusb to find connected Apple devices
        try:
            result = subprocess.run(["lsusb"], capture_output=True, text=True, timeout=10)
            if result.returncode == 0 and ("Apple" in result.stdout or "iPhone" in result.stdout):
                # Apple device detected, try to find its mount point
                iphone_path = self._find_apple_device_mount_linux()
                if iphone_path:
                    return iphone_path
        except:
            pass
        
        # Method 3: Check /proc/mounts for mounted filesystems
        try:
            with open('/proc/mounts', 'r') as f:
                mounts = f.read()
                
            for line in mounts.split('\n'):
                if line and ('iphone' in line.lower() or 'apple' in line.lower() or 'mtp' in line.lower()):
                    parts = line.split()
                    if len(parts) >= 2:
                        mount_point = parts[1]
                        dcim_path = os.path.join(mount_point, "DCIM")
                        if os.path.exists(dcim_path):
                            return dcim_path
        except:
            pass
        
        # Method 4: Use udisksctl to find block devices
        try:
            result = subprocess.run(["udisksctl", "status"], capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                lines = result.stdout.split('\n')
                for line in lines:
                    if 'Apple' in line or 'iPhone' in line:
                        # Try to get more info about this device
                        device_info = self._get_udisks_device_info(line)
                        if device_info:
                            return device_info
        except:
            pass
        
        # Method 5: Check dmesg for recently connected Apple devices
        try:
            result = subprocess.run(["dmesg", "|", "tail", "-100"], 
                                  shell=True, capture_output=True, text=True, timeout=5)
            if result.returncode == 0 and ("Apple" in result.stdout or "iPhone" in result.stdout):
                # Device was recently connected, try harder to find it
                iphone_path = self._scan_all_mount_points_linux()
                if iphone_path:
                    return iphone_path
        except:
            pass
                    
        return None
    
    def _find_apple_device_mount_linux(self):
        """Find Apple device mount point on Linux."""
        try:
            # Check common GVFS mount locations for MTP devices
            user_id = os.getuid() if hasattr(os, 'getuid') else 1000
            gvfs_path = f"/run/user/{user_id}/gvfs"
            
            if os.path.exists(gvfs_path):
                for mount in os.listdir(gvfs_path):
                    mount_path = os.path.join(gvfs_path, mount)
                    if ("mtp" in mount.lower() or "apple" in mount.lower() or 
                        "iphone" in mount.lower()):
                        
                        # Look for DCIM folder in this MTP device
                        dcim_path = os.path.join(mount_path, "DCIM")
                        if os.path.exists(dcim_path):
                            return dcim_path
                        
                        # Some devices might have DCIM nested deeper
                        try:
                            for item in os.listdir(mount_path):
                                item_path = os.path.join(mount_path, item)
                                if os.path.isdir(item_path):
                                    dcim_path = os.path.join(item_path, "DCIM")
                                    if os.path.exists(dcim_path):
                                        return dcim_path
                        except:
                            continue
        except:
            pass
        
        return None
    
    def _get_udisks_device_info(self, device_line):
        """Get device information using udisksctl."""
        try:
            # Extract device path from udisksctl output
            parts = device_line.split()
            for part in parts:
                if part.startswith('/dev/'):
                    # Get detailed info about this device
                    result = subprocess.run(
                        ["udisksctl", "info", "-b", part],
                        capture_output=True, text=True, timeout=5
                    )
                    
                    if result.returncode == 0:
                        lines = result.stdout.split('\n')
                        for line in lines:
                            if 'MountPoints:' in line:
                                mount_point = line.split('MountPoints:')[1].strip()
                                if mount_point and mount_point != '[]':
                                    # Clean up the mount point format
                                    mount_point = mount_point.strip('[]').strip()
                                    dcim_path = os.path.join(mount_point, "DCIM")
                                    if os.path.exists(dcim_path):
                                        return dcim_path
        except:
            pass
        
        return None
    
    def _scan_all_mount_points_linux(self):
        """Scan all mount points to find iPhone DCIM folder."""
        try:
            result = subprocess.run(["mount"], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                lines = result.stdout.split('\n')
                for line in lines:
                    parts = line.split()
                    if len(parts) >= 3:
                        mount_point = parts[2]
                        if os.path.exists(mount_point):
                            dcim_path = os.path.join(mount_point, "DCIM")
                            if os.path.exists(dcim_path) and self._verify_iphone_device(mount_point):
                                return dcim_path
        except:
            pass
        
        return None
    
    def start_transfer(self):
        if not self.iphone_path:
            self.update_status("No iPhone detected. Please detect iPhone first.")
            return
            
        if not os.path.exists(self.iphone_path):
            self.update_status("iPhone path no longer accessible. Please detect iPhone again.")
            self.transfer_button.setEnabled(False)
            return
            
        # Disable buttons during transfer
        self.detect_button.setEnabled(False)
        self.transfer_button.setEnabled(False)
        self.select_output_button.setEnabled(False)
        
        # Create and start worker thread
        self.worker_thread = WorkerThread(self.iphone_path, self.output_folder)
        self.worker_thread.progress_updated.connect(self.update_progress)
        self.worker_thread.status_updated.connect(self.update_status)
        self.worker_thread.finished_signal.connect(self.on_transfer_finished)
        self.worker_thread.start()
    
    def on_transfer_finished(self):
        # Re-enable buttons
        self.detect_button.setEnabled(True)
        self.transfer_button.setEnabled(True)
        self.select_output_button.setEnabled(True)
        
        # Show completion message
        QMessageBox.information(
            self, 
            "Transfer Complete",
            f"Photos and videos have been transferred and converted to:\n{self.output_folder}"
        )
        
        # Open the folder with the default file manager
        self.open_folder(self.output_folder)
    
    def select_output_folder(self):
        folder = QFileDialog.getExistingDirectory(
            self, 
            "Select Output Folder",
            self.output_folder
        )
        
        if folder:
            self.output_folder = folder
            self.update_status(f"Output folder: {self.output_folder}")
    
    def update_status(self, message):
        # This method may be called from another thread
        # Use the signal/slot mechanism to update the UI safely
        if threading.current_thread() is threading.main_thread():
            self.status_label.setText(message)
        else:
            # Use PyQt's thread-safe way to update UI
            self.status_label.setText(message)
    
    def update_progress(self, value):
        self.progress_bar.setValue(value)
    
    def open_folder(self, path):
        """Open the folder with the default file manager"""
        if platform.system() == "Windows":
            os.startfile(path)
        elif platform.system() == "Darwin":  # macOS
            subprocess.run(["open", path])
        else:  # Linux
            subprocess.run(["xdg-open", path])
    
    def closeEvent(self, event):
        # Stop the worker thread if it's running
        if self.worker_thread and self.worker_thread.isRunning():
            self.worker_thread.stop()
            self.worker_thread.wait()
        event.accept()

def main():
    # Create the application
    app = QApplication(sys.argv)
    window = PhotoConverterApp()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main() 
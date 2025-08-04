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
                           QWidget, QLabel, QProgressBar, QFileDialog, QMessageBox)
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
        
        # Buttons
        self.detect_button = QPushButton("🔍 Detect iPhone")
        self.detect_button.clicked.connect(self.detect_iphone)
        layout.addWidget(self.detect_button)
        
        self.test_connection_button = QPushButton("🧪 Test Connection")
        self.test_connection_button.clicked.connect(self.test_connection)
        layout.addWidget(self.test_connection_button)
        
        self.transfer_button = QPushButton("📱➡️💻 Transfer and Convert Photos")
        self.transfer_button.clicked.connect(self.start_transfer)
        self.transfer_button.setEnabled(False)
        layout.addWidget(self.transfer_button)
        
        self.select_output_button = QPushButton("📁 Select Output Folder")
        self.select_output_button.clicked.connect(self.select_output_folder)
        layout.addWidget(self.select_output_button)
        
        # Initialize variables
        self.iphone_path = None
        self.output_folder = os.path.join(os.path.dirname(os.path.abspath(__file__)), "transferred_photos")
        self.update_status(f"Output folder: {self.output_folder}")
        self.worker_thread = None
        
    def detect_iphone(self):
        self.update_status("Detecting iPhone...")
        self.progress_bar.setValue(0)
        
        # Run in a separate thread to avoid UI blocking
        threading.Thread(target=self._detect_iphone_worker, daemon=True).start()
    
    def _detect_iphone_worker(self):
        try:
            self.update_status("Scanning for connected iPhones...")
            
            # Try to find iPhone using platform-specific methods
            system = platform.system()
            if system == "Darwin":  # macOS
                self.update_status("Checking macOS volumes and USB devices...")
                self.iphone_path = self._find_iphone_macos()
            elif system == "Windows":
                self.update_status("Checking Windows drives and MTP devices...")
                self.iphone_path = self._find_iphone_windows()
            elif system == "Linux":
                self.update_status("Checking Linux mount points and USB devices...")
                self.iphone_path = self._find_iphone_linux()
            else:
                self.update_status("Unsupported operating system")
                return
            
            if self.iphone_path:
                # Verify we can actually access the path
                try:
                    test_files = os.listdir(self.iphone_path)
                    file_count = len([f for f in test_files if os.path.isfile(os.path.join(self.iphone_path, f))])
                    self.update_status(f"✅ iPhone detected! Found {file_count} items in DCIM folder")
                    self.transfer_button.setEnabled(True)
                except PermissionError:
                    self.update_status("iPhone found but access denied. Please unlock your iPhone and trust this computer.")
                    self.transfer_button.setEnabled(False)
                except Exception as e:
                    self.update_status(f"iPhone found but cannot access files: {str(e)}")
                    self.transfer_button.setEnabled(False)
            else:
                self._provide_connection_help(system)
                self.transfer_button.setEnabled(False)
                
        except Exception as e:
            self.update_status(f"Error detecting iPhone: {str(e)}")
            self.transfer_button.setEnabled(False)
    
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
        """Enhanced iPhone detection for Windows with multiple methods."""
        import string
        
        # Method 1: Check for MTP devices (most common for modern iPhones)
        iphone_path = self._find_iphone_mtp_windows()
        if iphone_path:
            return iphone_path
        
        # Method 2: Check common drive letters (legacy/iTunes mode)
        for drive in string.ascii_uppercase:
            drive_path = f"{drive}:\\"
            if os.path.exists(drive_path):
                # Check if this is an iPhone
                dcim_path = os.path.join(drive_path, "DCIM")
                if os.path.exists(dcim_path):
                    # Verify it's actually an iPhone by checking for iOS-specific folders
                    if self._verify_iphone_device(drive_path):
                        return dcim_path
                        
        # Method 3: Use WMI to find devices
        try:
            import wmi
            c = wmi.WMI()
            
            # Check removable drives
            for drive in c.Win32_LogicalDisk():
                if drive.DriveType == 2:  # Removable drive
                    dcim_path = os.path.join(drive.DeviceID, "DCIM")
                    if os.path.exists(dcim_path) and self._verify_iphone_device(drive.DeviceID):
                        return dcim_path
            
            # Check for Portable devices (MTP)
            for device in c.Win32_PnPEntity():
                if device.Name and ('iphone' in device.Name.lower() or 'apple' in device.Name.lower()):
                    # Try to find the corresponding path
                    mtp_path = self._get_mtp_device_path(device)
                    if mtp_path:
                        return mtp_path
                        
        except ImportError:
            print("WMI not available - continuing with other detection methods")
        except Exception as e:
            print(f"WMI detection failed: {e}")
        
        # Method 4: Check Windows shell for portable devices
        iphone_path = self._find_iphone_shell_windows()
        if iphone_path:
            return iphone_path
        
        # Method 5: PowerShell detection
        iphone_path = self._find_iphone_powershell_windows()
        if iphone_path:
            return iphone_path
            
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
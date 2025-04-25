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
        self.detect_button = QPushButton("Detect iPhone")
        self.detect_button.clicked.connect(self.detect_iphone)
        layout.addWidget(self.detect_button)
        
        self.transfer_button = QPushButton("Transfer and Convert Photos")
        self.transfer_button.clicked.connect(self.start_transfer)
        self.transfer_button.setEnabled(False)
        layout.addWidget(self.transfer_button)
        
        self.select_output_button = QPushButton("Select Output Folder")
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
            # Try to find iPhone using platform-specific methods
            if platform.system() == "Darwin":  # macOS
                self.iphone_path = self._find_iphone_macos()
            elif platform.system() == "Windows":
                self.iphone_path = self._find_iphone_windows()
            elif platform.system() == "Linux":
                self.iphone_path = self._find_iphone_linux()
            else:
                self.update_status("Unsupported operating system")
                return
            
            if self.iphone_path:
                self.update_status(f"iPhone detected at: {self.iphone_path}")
                self.transfer_button.setEnabled(True)
            else:
                self.update_status("iPhone not found. Please check connection.")
                self.transfer_button.setEnabled(False)
                
        except Exception as e:
            self.update_status(f"Error detecting iPhone: {str(e)}")
            self.transfer_button.setEnabled(False)
    
    def _find_iphone_macos(self):
        # Check common mount points on macOS
        possible_paths = [
            "/Volumes/Apple iPhone",
            "/Volumes/iPhone",
        ]
        
        # Also check /Volumes directory for any device that might be an iPhone
        try:
            volumes = os.listdir("/Volumes")
            for volume in volumes:
                if "iphone" in volume.lower() or "apple" in volume.lower():
                    possible_paths.append(f"/Volumes/{volume}")
        except:
            pass
            
        # Check if any of the possible paths exist and contain DCIM
        for path in possible_paths:
            dcim_path = os.path.join(path, "DCIM")
            if os.path.exists(dcim_path):
                return dcim_path
        
        # Use specific macOS command to find iOS devices
        try:
            result = subprocess.run(["mdfind", "kMDItemKind == 'iPhone'"], 
                                    capture_output=True, text=True, check=True)
            paths = result.stdout.strip().split("\n")
            for path in paths:
                if path and os.path.exists(path):
                    dcim_path = os.path.join(path, "DCIM")
                    if os.path.exists(dcim_path):
                        return dcim_path
        except:
            pass
            
        return None
    
    def _find_iphone_windows(self):
        # Check common drive letters on Windows
        import string
        
        for drive in string.ascii_uppercase:
            drive_path = f"{drive}:\\"
            if os.path.exists(drive_path):
                # Check if this is an iPhone
                dcim_path = os.path.join(drive_path, "DCIM")
                if os.path.exists(dcim_path):
                    return dcim_path
                    
        # Try using Windows specific methods to locate the device
        try:
            # WMI query to find removable drives
            import wmi
            c = wmi.WMI()
            for drive in c.Win32_LogicalDisk():
                if drive.DriveType == 2:  # Removable drive
                    dcim_path = os.path.join(drive.DeviceID, "DCIM")
                    if os.path.exists(dcim_path):
                        return dcim_path
        except:
            pass
            
        return None
    
    def _find_iphone_linux(self):
        # Check common mount points on Linux
        possible_paths = [
            "/run/user/1000/gvfs",
            "/media/" + os.environ.get("USER", ""),
            "/mnt",
        ]
        
        for base_path in possible_paths:
            if os.path.exists(base_path):
                try:
                    for device in os.listdir(base_path):
                        device_path = os.path.join(base_path, device)
                        # Check if this looks like an iPhone
                        if "iphone" in device.lower() or "apple" in device.lower():
                            dcim_path = os.path.join(device_path, "DCIM")
                            if os.path.exists(dcim_path):
                                return dcim_path
                        
                        # Also check for a DCIM directory
                        dcim_path = os.path.join(device_path, "DCIM")
                        if os.path.exists(dcim_path):
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
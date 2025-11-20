# Rescue Console Application

**eMMC Image Flasher for JetHub Rescue Systems**

Complete rescue system with two interfaces:
- **Console Application** - Full-featured terminal interface with interactive menus
- **OLED Grid Application** - Compact 128x64 OLED interface with hardware buttons

---

## 📋 Table of Contents

- [Overview](#overview)
- [Console Application](#console-application)
- [OLED Grid Application](#oled-grid-application)
- [Installation](#installation)
- [Configuration](#configuration)
- [Hardware Requirements](#hardware-requirements)
- [Usage Examples](#usage-examples)
- [Troubleshooting](#troubleshooting)

---

## 🎯 Overview

This is a professional rescue system application for **JetHub (j200)** devices that allows you to:

- 🌐 **Configure WiFi/Ethernet** - Connect to networks using wpa_supplicant (busybox-compatible)
- 📥 **Download firmware** - Fetch latest images from JetHome API or custom HTTP servers
- 💾 **Flash eMMC** - Write compressed `.img.xz` images directly to eMMC
- 🔌 **USB support** - Load images from USB drives
- ⚡ **Progress tracking** - Real-time progress with speed and ETA
- 🔒 **Safety features** - Multiple confirmations before destructive operations

### Key Features

- **Dual Interface**: Terminal and OLED display support
- **JetHome API Integration**: Automatic firmware discovery
- **Smart Decompression**: Stream `.xz` files directly to eMMC (no extra space needed)
- **Resume Support**: Continue interrupted downloads
- **Network Management**: Uses wpa_supplicant (busybox/minimal system compatible)
- **Zero Dependencies**: Only Python standard library (+ Pillow for OLED)

---

## 💻 Console Application

**Location**: `/root/rescue-consoleview/console-application/`

Full-featured terminal interface with arrow key navigation and color output.

### Interface Preview

```
╔═══════════════════════════════════════════════════════════════════════╗
║                                                                       ║
║                    RESCUE CONSOLE APPLICATION                         ║
║                           Version 1.3.0                               ║
║                                                                       ║
║              eMMC Image Flasher for Rescue Systems                    ║
║                     Device: JetHub                                 ║
║                                                                       ║
╚═══════════════════════════════════════════════════════════════════════╝

╔════════════════════ MAIN MENU ════════════════════╗
║                                                    ║
║  ❯ Network Setup (WiFi/Ethernet)                  ║
║    Flash Image to eMMC                            ║
║    System Information                             ║
║                                                    ║
║  Use ↑↓ arrows to navigate, Enter to select      ║
╚════════════════════════════════════════════════════╝
```

### Network Setup Menu

```
╔══════════════════ NETWORK SETUP ══════════════════╗
║                                                    ║
║  Status: Connected (wlan0)                        ║
║  IP Address: 192.168.1.100                        ║
║  WiFi Network: MyHomeNetwork                      ║
║                                                    ║
║  ❯ ← Back to Main Menu                            ║
║    Connect to WiFi                                ║
║    Test Internet Connection                       ║
║                                                    ║
╚════════════════════════════════════════════════════╝
```

### WiFi Network Selection

```
╔════════════ Select WiFi Network ══════════════════╗
║                                                    ║
║  ← Back / Cancel                                  ║
║  ❯ MyHomeNetwork         🔒 [████] 100%            ║
║    OfficeWiFi            🔒 [███ ] 75%             ║
║    GuestNetwork          🔓 [██  ] 50%             ║
║    CoffeeShop            🔓 [█   ] 25%             ║
║                                                    ║
║  Use ↑↓ arrows to navigate, Enter to select      ║
╚════════════════════════════════════════════════════╝
```

### Flash Image Menu

```
╔══════════════ FLASH IMAGE TO eMMC ════════════════╗
║                                                    ║
║  Select image source:                             ║
║                                                    ║
║  ❯ ← Back to Main Menu                            ║
║    Download from HTTP/JetHome API                 ║
║    Load from USB drive                            ║
║                                                    ║
╚════════════════════════════════════════════════════╝
```

### Firmware Selection (JetHome API)

```
╔════════════ Select Image to Download ════════════════════════╗
║                                                                ║
║  Found 5 firmware image(s)                                    ║
║                                                                ║
║  ← Back / Cancel                                              ║
║  ❯ armbian.nightly.trixie.edge v25.11.0 | 536 MB             ║
║    armbian.nightly.jammy.edge v25.11.0  | 512 MB             ║
║    armbian.nightly.noble.edge v25.11.0  | 548 MB             ║
║    armbian.nightly.bookworm.edge v25.11.0 | 524 MB           ║
║    jhaos.release v2.0.1 | 450 MB                             ║
║                                                                ║
╚════════════════════════════════════════════════════════════════╝
```

### Download Progress

```
📥 Downloading: armbian-trixie-edge-jethub.img.xz
📍 URL: https://fw.jethome.com/media/firmwares/...
📦 Total size: 536 MB

Downloaded: 245 MB (45%) | ETA: 00:03:42 | Speed: 2.3 MB/s

[████████████████████░░░░░░░░░░░░░░░░░░░░░░] 45%
```

### Flash Progress

```
⚠️  WARNING: This will ERASE ALL DATA on /dev/mmcblk1!

Target device: /dev/mmcblk1 (14.6 GB eMMC)
Image: armbian-trixie-edge-jethub.img.xz (536 MB compressed)

Type 'yes' to continue: yes

🔄 Unmounting partitions...
✓ All partitions unmounted

🔥 Flashing image to eMMC...
[████████████████████████░░░░░░░░░░░░░░░░] 65%
Written: 3.2 GB / 4.8 GB | Speed: 42 MB/s | ETA: 00:00:38
```

### Features

- ✅ **Arrow Key Navigation** - Intuitive menu navigation with ↑↓ keys
- ✅ **Color Output** - Visual highlighting for selected items
- ✅ **Progress Bars** - Real-time progress with percentage and ETA
- ✅ **Network Testing** - Built-in connectivity check to JetHome API
- ✅ **Device Auto-Detection** - Finds all mmcblk devices automatically
- ✅ **Smart Filtering** - Only shows flashable `sdcard` images
- ✅ **Resume Downloads** - Continue interrupted HTTP downloads
- ✅ **Safety Checks** - Multiple confirmations before flashing

### Running Console Application

```bash
cd /root/rescue-consoleview/console-application
sudo ./main.py
```

**Requirements:**
- Python 3.6+
- Root privileges
- Terminal with UTF-8 support
- wpa_cli for WiFi (wpa_supplicant)

---

## 📺 OLED Grid Application

**Location**: `/root/rescue-consoleview/oled-grid-application/`

Compact interface designed for 128x64 OLED displays with hardware button navigation.

### Hardware Configuration

- **Display**: 128x64 OLED (SH1106 or SSD1306)
- **Connection**: I2C (framebuffer `/dev/fb1`)
- **Buttons**: 5 GPIO buttons (UP, DOWN, LEFT, RIGHT, ENTER)
- **Font Size**: 12px (optimized for readability)

### OLED Display Examples

#### Main Menu (2x2 Grid)

```
┌─────────────────────────────────┐
│  JetHub Rescue      [EN] 🔋  │ ← Header
├────────────────┬────────────────┤
│                │                │
│     Network    │    Flash to    │
│                │      disk      │ ← Selected (thick border)
├────────────────┼────────────────┤
│                │                │
│      Info      │     Reboot     │
│                │                │
└────────────────┴────────────────┘
        128 x 64 pixels
```

Visual selection with thick border around active cell.

#### Network Menu

```
┌─────────────────────────────────┐
│ Network                    [EN] │ ← Title
├─────────────────────────────────┤
│                                 │
│ ❯ WiFi Setup                    │ ← Selected
│   Test Connection               │
│   Back                          │
│                                 │
└─────────────────────────────────┘
```

#### WiFi Networks List

```
┌─────────────────────────────────┐
│ Select WiFi            [Scroll] │
├─────────────────────────────────┤
│                                 │
│ ❯ MyHomeNet 🔒 ████ 95%         │ ← Selected
│   OfficeWiFi 🔒 ███  75%        │
│   GuestNet   🔓 ██   50%        │
│                                 │
└─────────────────────────────────┘
```

#### Grid Keyboard for Password Input

```
┌─────────────────────────────────┐
│ Pass: MyP****          [HIDDEN] │ ← Shows typed password
├─────────────────────────────────┤
│ Q W E R T Y U I O P             │
│ A S D F G H J K L               │ ← Selected: 'D'
│ Z X C V B N M ⌫                 │
│ AB 12 ab _ @ . ✓                │
└─────────────────────────────────┘
   ↑  ↑  ↑        ↑
   │  │  │        └─ Submit
   │  │  └─ Lowercase mode
   │  └─ Numbers/symbols mode
   └─ Uppercase mode
```

Navigation with UP/DOWN/LEFT/RIGHT buttons, ENTER to select character.

#### Connecting Animation

```
┌─────────────────────────────────┐
│ Connecting...                   │
├─────────────────────────────────┤
│                                 │
│         🔄                      │
│                                 │
│      MyHomeNetwork              │
│                                 │
└─────────────────────────────────┘
```

#### Success Message

```
┌─────────────────────────────────┐
│ Connected                       │
├─────────────────────────────────┤
│                                 │
│            ✓                    │
│                                 │
│      MyHomeNetwork              │
│      192.168.1.100              │
│                                 │
└─────────────────────────────────┘
```

#### Firmware Selection (Scrollable)

```
┌─────────────────────────────────┐
│ Select Image            [3 / 5] │ ← Scroll indicator
├─────────────────────────────────┤
│                                 │
│ ❯ armbian.trixie                │ ← Selected
│   v25.11.0 536MB                │
│   armbian.jammy                 │
│                                 │
└─────────────────────────────────┘
```

Scrolling with UP/DOWN through available firmware images.

#### Download Progress

```
┌─────────────────────────────────┐
│ Downloading...          [  45%] │
├─────────────────────────────────┤
│                                 │
│ armbian-trixie-edge             │
│                                 │
│ [████████░░░░░░░░░░]            │
│ 245 / 536 MB                    │
│ 2.3 MB/s  ⏱ 03:42               │
│                                 │
└─────────────────────────────────┘
```

#### Flash Progress

```
┌─────────────────────────────────┐
│ Flashing eMMC...        [  65%] │
├─────────────────────────────────┤
│                                 │
│ /dev/mmcblk1                    │
│                                 │
│ [█████████████░░░░░░░]          │
│ 3.2 / 4.8 GB                    │
│ 42 MB/s  ⏱ 00:38                │
│                                 │
└─────────────────────────────────┘
```

#### Confirmation Dialog

```
┌─────────────────────────────────┐
│ Enter WiFi Password?            │
├─────────────────────────────────┤
│                                 │
│        MyHomeNetwork            │
│                                 │
│        ┌────┐   ┌────┐          │
│        │ OK │   │ NO │          │ ← Selected: OK
│        └────┘   └────┘          │
│                                 │
└─────────────────────────────────┘
```

Navigate with LEFT/RIGHT buttons, ENTER to select.

#### System Information

```
┌─────────────────────────────────┐
│ System Info                     │
├─────────────────────────────────┤
│                                 │
│ Device: JetHub               │
│ Platform: j200                  │
│ Network: Connected              │
│ IP: 192.168.1.100               │
│                                 │
│ Press any key...                │
└─────────────────────────────────┘
```

### Features

- ✅ **Grid Navigation** - 2x2 grid menu with directional buttons
- ✅ **On-Screen Keyboard** - Full QWERTY layout for text input
- ✅ **Visual Feedback** - Thick borders for selection highlighting
- ✅ **Word Wrapping** - Automatic text wrapping for Russian/English
- ✅ **Progress Animations** - Spinner and progress bars
- ✅ **Error Handling** - Wrong password retry with clear messages
- ✅ **Multi-Language** - English and Russian support
- ✅ **Auto-Return** - Returns to menu after 2 seconds on success

### Running OLED Application

```bash
cd /root/rescue-consoleview/oled-grid-application
sudo ./main.py
```

**Requirements:**
- Python 3.6+
- Pillow (PIL) for image rendering
- `/dev/fb1` framebuffer device
- `/dev/input/event0` for GPIO buttons
- Root privileges

---

## 📦 Installation

### Console Application

```bash
# No additional dependencies needed (uses Python standard library)
cd /root/rescue-consoleview/console-application
sudo ./main.py
```

### OLED Grid Application

```bash
# Install required packages
apt-get update
apt-get install -y python3-pil fonts-dejavu-core

# OR install via pip
pip3 install Pillow

# Run application
cd /root/rescue-consoleview/oled-grid-application
sudo ./main.py
```

**Dependencies** (`oled-grid-application/requirements.txt`):
```
Pillow>=10.0.0
python-evdev>=1.6.0
```

### Kernel Configuration for OLED

For OLED display support, ensure your kernel has:

```bash
# Device Tree: SH1106 OLED support
&i2c1 {
    status = "okay";

    oled: oled@3c {
        compatible = "sinowealth,sh1106";
        reg = <0x3c>;
        solomon,height = <64>;
        solomon,width = <128>;
        solomon,page-offset = <0>;
    };
};

# Kernel Config
CONFIG_FB=y
CONFIG_FB_SH1106=y
CONFIG_INPUT_GPIO_KEYS=y
```

---

## ⚙️ Configuration

### Console Application Config

**File**: `console-application/config.py`

```python
# ==================== NETWORK SETTINGS ====================

# JetHome API settings (for automatic firmware discovery)
JETHOME_API_ENABLED = True
JETHOME_API_BASE = "https://fw.jethome.com"

# JetHome device configuration
JETHOME_DEVICE_NAME = "JetHub"
JETHOME_DEVICE = "d2"        # Device identifier for API
JETHOME_PLATFORM = "j200"    # Platform identifier

# Network interfaces
WIFI_INTERFACE = "wlan0"
ETHERNET_INTERFACE = "eth0"
NETWORK_TIMEOUT = 10

# ==================== STORAGE SETTINGS ====================

# eMMC device path (check with: lsblk)
EMMC_DEVICE = "/dev/mmcblk1"

# Temporary directory for downloads (uses RAM)
TEMP_DIR = "/tmp/rescue"

# USB mount point
USB_MOUNT_POINT = "/mnt/usb"

# Minimum free space required in RAM (600MB for compressed images)
MIN_FREE_SPACE = 600 * 1024 * 1024

# ==================== IMAGE SETTINGS ====================

# JetHome firmware types to show (filter by these keys)
JETHOME_FIRMWARE_FILTER = [
    "armbian.nightly.trixie.edge",
    "armbian.nightly.jammy.edge",
    "armbian.nightly.noble.edge",
    "armbian.nightly.bookworm.edge",
    "jhaos.release"
]

# ==================== ADVANCED SETTINGS ====================

# Block size for dd command (in MB)
DD_BLOCK_SIZE = 4  # 4MB blocks

# Chunk size for downloads (bytes)
DOWNLOAD_CHUNK_SIZE = 1024 * 1024  # 1MB

# Number of retries for network operations
NETWORK_RETRY_COUNT = 3
RETRY_DELAY = 5

# ==================== SAFETY SETTINGS ====================

# Skip mount check (DANGEROUS! Only for testing)
SKIP_MOUNT_CHECK = True  # Set to False for production!
```

### OLED Grid Application Config

**File**: `oled-grid-application/config.py`

```python
# ==================== OLED DISPLAY SETTINGS ====================

# Framebuffer Settings
FRAMEBUFFER_DEVICE = '/dev/fb1'  # Linux framebuffer for OLED
OLED_WIDTH = 128
OLED_HEIGHT = 64

# ==================== DISPLAY SETTINGS ====================

# Font Settings
FONT_SMALL = 12   # For menu items
FONT_NORMAL = 14  # For titles
FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"

# Text Settings
MAX_LINE_LENGTH = 15  # Characters per line at font size 12
TEXT_TRUNCATE = "..."

# ==================== DEVICE SETTINGS ====================

# Device configuration
JETHOME_DEVICE_NAME = "JetHub"
DEVICE = "j200"
DEVICE_ID = "d2"
PLATFORM = "j200"

# Hardware devices
EMMC_DEVICE = "/dev/mmcblk1"
WIFI_INTERFACE = "wlan0"
ETHERNET_INTERFACE = "eth0"
USB_MOUNT_POINT = "/mnt/usb"

# Storage paths
TEMP_DIR = "/var/rescue"

# JetHome API
JETHOME_API_ENABLED = True
JETHOME_API_BASE = "https://fw.jethome.com"

# ==================== INPUT SETTINGS ====================

# GPIO Input Device
INPUT_DEVICE_PATH = "/dev/input/event0"

# Button key codes (from evdev)
KEY_UP = 103      # KEY_UP
KEY_DOWN = 108    # KEY_DOWN
KEY_LEFT = 105    # KEY_LEFT
KEY_RIGHT = 106   # KEY_RIGHT
KEY_ENTER = 28    # KEY_ENTER

# Button debounce delay (seconds)
BUTTON_DEBOUNCE = 0.15

# ==================== LANGUAGE SETTINGS ====================

# Default language ('ENG' or 'RUS')
DEFAULT_LANGUAGE = 'ENG'
```

---

## 🔧 Hardware Requirements

### For Console Application

- **Platform**: JetHub (j200) or any ARM/x86_64 Linux system
- **Python**: 3.6+
- **RAM**: 1GB+ (for image downloads)
- **Storage**: Enough space in `/tmp` for compressed images (~600MB)
- **Network**: WiFi adapter or Ethernet
- **Privileges**: Root access required

### For OLED Grid Application

**Required Hardware:**

- **OLED Display**: 128x64 pixels (SH1106 or SSD1306 controller)
- **Connection**: I2C bus (typically I2C1)
- **Framebuffer**: `/dev/fb1` (managed by kernel driver)
- **Buttons**: 5x GPIO buttons connected to `/dev/input/event0`
  - UP (GPIO key code 103)
  - DOWN (GPIO key code 108)
  - LEFT (GPIO key code 105)
  - RIGHT (GPIO key code 106)
  - ENTER (GPIO key code 28)

**Connection Example:**

```
JetHub          OLED Display (SH1106)
---------          ---------------------
I2C1_SDA  ------>  SDA (Pin 3)
I2C1_SCL  ------>  SCL (Pin 5)
3.3V      ------>  VCC
GND       ------>  GND

GPIO Buttons:
- UP:    GPIO 506 → Event Code 103
- DOWN:  GPIO 426 → Event Code 108
- LEFT:  GPIO 429 → Event Code 105
- RIGHT: GPIO 412 → Event Code 106
- ENTER: GPIO 495 → Event Code 28
```

---

## 📖 Usage Examples

### Console Application Examples

#### Example 1: Flash Latest Armbian from JetHome API

```bash
$ sudo ./console-application/main.py

# 1. Main Menu → "Network Setup (WiFi/Ethernet)"
# 2. Network Menu → "Connect to WiFi"
# 3. Select your WiFi network
# 4. Enter password
# 5. Back to Main Menu → "Flash Image to eMMC"
# 6. Select "Download from HTTP/JetHome API"
# 7. Choose firmware (e.g., "armbian.nightly.trixie.edge v25.11.0")
# 8. Confirm download
# 9. Select target device (/dev/mmcblk1)
# 10. Type 'yes' to confirm flashing
# 11. Wait for completion
# 12. Reboot
```

#### Example 2: Flash from USB Drive

```bash
$ sudo ./console-application/main.py

# 1. Insert USB drive with .img.xz file
# 2. Main Menu → "Flash Image to eMMC"
# 3. Select "Load from USB drive"
# 4. Select USB device from list
# 5. Choose image file
# 6. Select target device (/dev/mmcblk1)
# 7. Type 'yes' to confirm
# 8. Wait for completion (do NOT remove USB!)
# 9. Reboot after success
```

#### Example 3: Check System Information

```bash
$ sudo ./console-application/main.py

# Main Menu → "System Information"

# Output:
#   Hostname:      jethubj200
#   Kernel:        6.1.0-meson64
#   Architecture:  aarch64
#   Memory:        2.0 GB
#   Free Space:    800 MB
#
#   Device:        JetHub
#   Platform:      j200
#
#   eMMC Device:   /dev/mmcblk1
#   Network:       Connected (wlan0)
#   IP Address:    192.168.1.100
```

### OLED Grid Application Examples

#### Example 1: Connect to WiFi via OLED

```
Hardware Buttons Navigation:

1. Power on → Main menu appears
2. UP/DOWN/LEFT/RIGHT → Navigate to "Network" cell
3. ENTER → Open Network menu
4. DOWN → Select "WiFi Setup"
5. ENTER → Scan for networks
6. UP/DOWN → Select your network
7. ENTER → Confirm
8. ENTER → Confirm password input (OK)
9. Use grid keyboard:
   - UP/DOWN/LEFT/RIGHT to navigate characters
   - ENTER to type character
   - Navigate to 'ab'/'AB'/'12' to switch modes
   - Navigate to '✓' when done
   - ENTER to submit
10. Wait for connection (2 seconds auto-return)
11. Back in Network menu
```

#### Example 2: Flash Firmware via OLED

```
1. Main menu → Navigate to "Flash to disk"
2. ENTER → Open Flash menu
3. DOWN → Select "Download & Flash"
4. ENTER → Fetch firmware list from JetHome API
5. UP/DOWN → Scroll through available images
6. ENTER → Select image
7. ENTER → Confirm download
8. Wait for download (progress bar shown)
9. ENTER → Confirm flash operation (type 'yes' via keyboard)
10. Wait for flashing (progress bar shown)
11. ENTER → Reboot now or return to menu
```

#### Example 3: View System Info

```
1. Main menu → Navigate to "Info" cell
2. ENTER → Display system information
   - Shows device name, platform, network status, IP
3. Press any button → Return to main menu
```

---

## 🐛 Troubleshooting

### Console Application Issues

#### Issue: "No network manager available"
**Solution:**
```bash
# Check if wpa_cli is available
which wpa_cli

# If not, install wpa_supplicant
apt-get install wpa_supplicant

# OR use wpa_supplicant fallback (already supported)
```

#### Issue: "Cannot connect to server" when using JetHome API
**Solution:**
```bash
# Test network connectivity
ping -c 3 fw.jethome.com

# Check DNS resolution
nslookup fw.jethome.com

# Verify SSL certificates
apt-get install ca-certificates
update-ca-certificates
```

#### Issue: "Permission denied" on /dev/mmcblk1
**Solution:**
```bash
# Run with sudo
sudo ./console-application/main.py

# Check device permissions
ls -l /dev/mmcblk1
```

### OLED Grid Application Issues

#### Issue: "Cannot open framebuffer /dev/fb1"
**Solution:**
```bash
# Check if framebuffer exists
ls -l /dev/fb1

# Check kernel support
dmesg | grep -i fb
dmesg | grep -i sh1106

# Verify Device Tree
cat /sys/firmware/devicetree/base/i2c*/oled*/compatible
# Should show: sinowealth,sh1106
```

#### Issue: "Cannot find input device"
**Solution:**
```bash
# List input devices
cat /proc/bus/input/devices

# Check event devices
ls -l /dev/input/event*

# Test buttons
evtest /dev/input/event0
# Press buttons to see if events are generated
```

#### Issue: OLED display shows garbage or nothing
**Solution:**
```bash
# Check I2C connection
i2cdetect -y 1
# Should show device at address 0x3c

# Verify framebuffer is active
cat /sys/class/graphics/fb1/name
# Should show: SH1106 framebuffer

# Test framebuffer directly
dd if=/dev/zero of=/dev/fb1
# Should clear the display
```

#### Issue: Font not found
**Solution:**
```bash
# Install DejaVu fonts
apt-get install fonts-dejavu-core

# Verify font exists
ls -l /usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf

# Update font cache
fc-cache -fv
```

#### Issue: Grid keyboard input not working
**Solution:**
```bash
# Test button events
evtest /dev/input/event0

# Check button key codes in dmesg
dmesg | grep -i gpio-keys

# Verify input permissions
ls -l /dev/input/event0
sudo chmod 666 /dev/input/event0  # Temporary fix
```

#### Issue: Text overflow/wrapping on OLED
**Solution:**
```python
# Adjust font size in oled-grid-application/config.py
FONT_SMALL = 11  # Try smaller (10-12)
MAX_LINE_LENGTH = 16  # Adjust character limit
```

#### Issue: "Wrong password" even with correct password
**Solution:**
```bash
# Check wpa_supplicant is running
ps aux | grep wpa_supplicant

# Manually test connection
wpa_passphrase "SSID" "password" | sudo tee /etc/wpa_supplicant/wpa_supplicant.conf
sudo wpa_supplicant -B -i wlan0 -c /etc/wpa_supplicant/wpa_supplicant.conf

# Check WiFi interface
ip link show wlan0
sudo ip link set wlan0 up
```

### General Issues

#### Issue: Download speed is very slow
**Solution:**
- Check network signal strength
- Try different WiFi network
- Use Ethernet instead of WiFi
- Check available bandwidth

#### Issue: Flash operation fails
**Solution:**
```bash
# Verify eMMC device
lsblk
# Should show mmcblk1 with correct size

# Check if eMMC is mounted (should NOT be mounted)
mount | grep mmcblk1

# Unmount all partitions
sudo umount /dev/mmcblk1*

# Check for corruption
sudo badblocks -n -s -v /dev/mmcblk1
```

#### Issue: Out of space during download
**Solution:**
```bash
# Check available space
df -h /tmp

# Clear old downloads
rm -rf /tmp/rescue/*.img.xz

# Use different temp directory (edit config.py)
TEMP_DIR = "/var/rescue"
```

---

## 📄 License

This project is designed for JetHome rescue systems.

## 🤝 Support

For issues and questions:
- JetHome Firmware: https://fw.jethome.com/
- JetHub Info: https://jethome.ru/devices/

## 📝 Version

**Current Version**: 1.3.0

### Changelog

**v1.3.0**
- Fixed to JetHub (j200) only
- Simplified main menu (removed device selection and exit)
- Updated JetHome API integration
- Improved OLED grid navigation
- Added on-screen keyboard for WiFi passwords
- Enhanced error handling for WiFi connections
- Automatic return to menu after successful operations

**v1.2.0**
- Added OLED grid interface with 2x2 menu
- Implemented hardware button navigation
- Added multi-language support (EN/RU)
- Grid keyboard for text input
- Progress bars and animations

**v1.1.0**
- Initial JetHome API integration
- Interactive menu with arrow keys
- WiFi and Ethernet support
- Resume downloads capability

---

## 🎯 Project Structure

```
rescue-consoleview/
│
├── console-application/          # Full-featured console version
│   ├── config.py                # Configuration settings
│   ├── main.py                  # Main entry point
│   ├── download.py              # HTTP download + JetHome API
│   ├── network.py               # Network management (wpa_supplicant)
│   ├── flash.py                 # eMMC flashing with xz support
│   ├── usb.py                   # USB device detection and mounting
│   └── utils.py                 # Helper functions and display
│
├── oled-grid-application/        # Compact OLED version
│   ├── config.py                # OLED-specific configuration
│   ├── main.py                  # OLED entry point
│   ├── display.py               # OLED drawing (grid, keyboard, progress)
│   ├── menu.py                  # Navigation and input handling
│   ├── input.py                 # GPIO button handler
│   ├── language.py              # Translations (EN/RU)
│   ├── requirements.txt         # Python dependencies
│   └── screens/                 # Application screens
│       ├── network.py           # WiFi setup with grid keyboard
│       ├── flash.py             # Firmware download and flash
│       ├── info.py              # System information display
│       └── reboot.py            # Reboot functionality
│
└── README.md                     # This file
```

---

**Made for JetHub Rescue Systems** 🚀


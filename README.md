# Rescue Console Application

**eMMC Image Flasher for JetHub Rescue Systems**

Complete rescue system with three interfaces:
- **Console Application** - Terminal interface with arrow-key (curses) menus
- **Web Application** - Browser UI served on port 8124
- **OLED Grid Application** - Compact 128x64 OLED interface with hardware buttons

---

## 📋 Table of Contents

- [Overview](#-overview)
- [Console Application](#-console-application)
- [Web Application](#-web-application)
- [OLED Grid Application](#-oled-grid-application)
- [Usage Examples](#-usage-examples)
- [Project Structure](#-project-structure)

---

## 🎯 Overview

This is a professional rescue system application for **JetHub devices (J100/D1, J200/D2, J310/D3 — auto-detected from the environment or device tree)** that allows you to:

- 🌐 **Configure WiFi/Ethernet** - Connect to networks using NetworkManager (nmcli)
- 📥 **Download firmware** - Fetch latest images from the JetHome API (fw.jethome.com)
- 💾 **Flash eMMC** - Write compressed `.img.xz` images directly to eMMC
- 🔌 **USB support** - Load images from USB drives
- ⚡ **Progress tracking** - Real-time progress with speed and ETA
- 🔒 **Safety features** - Multiple confirmations before destructive operations

### Key Features

- **Three Interfaces**: Terminal (curses), browser (port 8124) and OLED display
- **JetHome API Integration**: Automatic firmware discovery for the auto-detected board
- **Smart Decompression**: Stream `.xz` files directly to eMMC (no extra space needed)
- **Resume Support**: Continue interrupted downloads
- **Network Management**: Uses NetworkManager (nmcli)
- **Recovery-Safe Flashing**: The first 336 MiB (bootloader + recovery slots) are never overwritten
- **Zero Dependencies**: Only Python standard library (+ Pillow and python-evdev for OLED)

---

## 💻 Console Application

**Location**: `/usr/lib/jrescue-app/console-application/`

Terminal interface with arrow-key (curses) navigation and color output. In the
recovery image it is started on the serial console by `jrescue-console@.service`.

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
cd /usr/lib/jrescue-app/console-application
sudo ./main.py
```

**Requirements:**
- Python 3.14 with the `curses` module (as shipped in the recovery image; 3.7+ elsewhere)
- Root privileges
- Terminal with UTF-8 support
- NetworkManager (nmcli) for networking

---

## 🌐 Web Application

**Location**: `/usr/lib/jrescue-app/web-application/`

Browser UI with the same capabilities (network setup, image download, flashing,
system info). Served by a Python stdlib HTTP server on **port 8124**; started
automatically in the recovery image by `jrescue-web.service`. Open
`http://<device-ip>:8124` from any device on the same network.

---

## 📺 OLED Grid Application

**Location**: `/usr/lib/jrescue-app/oled-grid-application/`

Compact interface designed for 128x64 OLED displays with hardware button
navigation. Present on **JetHub D3 (J310)**; started there by
`jrescue-oled.service`.

### Hardware Configuration

- **Display**: 128x64 OLED (SSD130x family, managed by the kernel framebuffer driver)
- **Connection**: I2C (framebuffer `/dev/fb0`)
- **Buttons**: GPIO buttons via gpio-keys/evdev (UP, DOWN, LEFT, RIGHT, ENTER, BACK, HOME)
- **Font Size**: 12px (optimized for readability)

### OLED Display Examples

#### Main Menu (2x2 Grid)

```
┌────────────────┬────────────────┐
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

Grid cells fill the whole screen; selection is a thick border around the active
cell. Interface language (EN/RU) is chosen on a dedicated startup screen.

#### Network Menu

```
┌─────────────────────────────────┐
│ Network                         │ ← Title
├─────────────────────────────────┤
│                                 │
│ ❯ WiFi                          │ ← Selected
│   Status                        │
│                                 │
└─────────────────────────────────┘
```

Going back is done with the hardware BACK button (HOME jumps to the main menu).

#### WiFi Networks List

```
┌─────────────────────────────────┐
│ Select WiFi            [Scroll] │
├─────────────────────────────────┤
│                                 │
│ ❯ MyHomeNet                     │ ← Selected
│   OfficeWiFi                    │
│   GuestNet                      │
│                                 │
└─────────────────────────────────┘
```

#### Grid Keyboard for Password Input

```
┌─────────────────────────────────┐
│ Pass: mypassw                   │ ← Typed text
├─────────────────────────────────┤
│ a b c d e f g h                 │
│ i j k l m n o p                 │ ← Selected: 'l'
│ q r s t u v w x                 │
│ y z _ Sp ← OK AB                │
└─────────────────────────────────┘
         ↑  ↑  ↑  ↑
         │  │  │  └─ Mode: ab → AB → 12
         │  │  └─ Submit
         │  └─ Backspace
         └─ Space
```

4x8 character grid. Navigation with UP/DOWN/LEFT/RIGHT buttons, ENTER to select
a key; the mode key cycles lowercase → uppercase → numbers/symbols.

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
│ Info                            │
├─────────────────────────────────┤
│                                 │
│      jrescueOS 2026.02          │ ← Firmware name/version
│                                 │
│            ┌────┐               │
│            │ OK │               │
│            └────┘               │
└─────────────────────────────────┘
```

### Features

- ✅ **Grid Navigation** - 2x2 grid menu with directional buttons
- ✅ **On-Screen Keyboard** - 4x8 character grid (lowercase/uppercase/numbers modes)
- ✅ **Visual Feedback** - Thick borders for selection highlighting
- ✅ **Word Wrapping** - Automatic text wrapping for Russian/English
- ✅ **Progress Animations** - Spinner and progress bars
- ✅ **Error Handling** - Wrong password retry with clear messages
- ✅ **Multi-Language** - English and Russian support
- ✅ **Auto-Return** - Returns to menu after 2 seconds on success

## 📖 Usage Examples

### OLED Grid Application Examples

#### Example 1: Connect to WiFi via OLED

```
Hardware Buttons Navigation:

1. Power on → Main menu appears
2. UP/DOWN/LEFT/RIGHT → Navigate to "Network" cell
3. ENTER → Open Network menu
4. ENTER → Select "WiFi"
5. Wait for scan → Select your network with UP/DOWN
6. ENTER → Confirm
7. Use the grid keyboard for the password:
   - UP/DOWN/LEFT/RIGHT to navigate characters
   - ENTER to type a character
   - The mode key cycles ab → AB → 12
   - Navigate to 'OK' and press ENTER to submit
8. Wait for connection (2 seconds auto-return)
9. Back in Network menu
```

#### Example 2: Flash Firmware via OLED

```
1. Main menu → Navigate to "Flash to disk"
2. ENTER → Open Flash menu
3. ENTER → Select "From API" (also: "From USB", "From RAM")
4. Wait for the firmware list from the JetHome API
5. UP/DOWN → Scroll through available images
6. ENTER → Select image
7. ENTER → Confirm download
8. Wait for download (progress bar shown)
9. LEFT/RIGHT → select YES in the NO/YES dialog, ENTER → confirm flashing
10. Wait for flashing (progress bar shown)
11. ENTER → Reboot now or return to menu
```

#### Example 3: View System Info

```
1. Main menu → Navigate to "Info" cell
2. ENTER → Display firmware name and version
3. ENTER (OK) → Return to main menu
```

---

## 📄 License

This project is designed for JetHome rescue systems.

## 🤝 Support

For issues and questions:
- JetHome Firmware: https://fw.jethome.com/
- JetHub Info: https://jethome.ru/devices/

## 📝 Version

**Current version:** v1.4.0

## 🎯 Project Structure

```
jrescue-app/
│
├── core/                         # Shared modules used by all frontends
│   ├── config.py                # Settings + board auto-detection (env/device-tree)
│   ├── network.py               # NetworkManager (nmcli) wrapper, device auto-detect
│   ├── download.py              # JetHome API image list + HTTP downloads (resume)
│   ├── flash.py                 # eMMC flashing (xz streaming, protected recovery region)
│   ├── usb.py                   # USB device detection, mounting, image scan
│   ├── utils.py                 # curses menus/dialogs, system info, helpers
│   └── translations.py          # i18n (EN/RU)
│
├── console-application/          # Arrow-key TUI on the (serial) console
│   └── main.py
│
├── web-application/              # Browser UI on port 8124
│   ├── main.py                  # stdlib HTTP server + routing
│   ├── api_handler.py           # REST API (network, flash, system)
│   ├── config.py                # Web-specific overrides
│   └── static/                  # index.html, css/, js/
│
├── oled-grid-application/        # 128x64 OLED UI with GPIO buttons
│   ├── main.py                  # OLED entry point
│   ├── display.py               # Framebuffer rendering (Pillow)
│   ├── menu.py                  # Navigation, on-screen keyboard
│   ├── input.py                 # GPIO button handler (evdev)
│   ├── language.py              # OLED translations (EN/RU)
│   ├── config.py                # OLED-specific configuration
│   └── screens/                 # network / flash / info / reboot
│
├── AGENTS.md                     # Project guide for AI agents (CLAUDE.md imports it)
└── README.md                     # This file
```

---

**Made for JetHub Rescue Systems** 🚀


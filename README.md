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
- [Updating the application](#updating-the-application)
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
- **RAM Cleanup**: Old images are removed before every download
- **Network Management**: Uses NetworkManager (nmcli)
- **Recovery-Safe Flashing**: Only the 128–336 MiB recovery window is preserved; image data before and after it, including MBR/GPT, is written at its original offsets
- **Zero Dependencies**: Only Python standard library (+ Pillow and python-evdev for OLED)

Flashing expects a full-disk `.img` or `.img.xz` with OS data after 336 MiB.
The writer replaces bytes `[0, 128 MiB)` and `[336 MiB, image end)` at their
original offsets and never writes `[128 MiB, 336 MiB)`. Both recovery slots
survive even when the source image contains zeros there. The target is not
truncated or erased beyond the end of the image. MBR/GPT is copied from the
source; an SD-card layout is not automatically converted to an eMMC layout.
Amlogic `.burn.img` containers must not be passed to the disk-image writer.

---

## Updating the application

The recovery system provides `jrescue-update` to install an application archive
and restart the interfaces. On the board:

```bash
jrescue-update http://<server>/jrescue-app.tar.gz
```

Replace the URL with the archive to install. The previous installation can be
restored with:

```bash
jrescue-update --rollback
```

The recovery root filesystem is in RAM, so application updates last until reboot.
Persistent updates require including the release in the recovery image.

## 💻 Console Application

**Location**: `/usr/lib/jrescue-app/console-application/`

Terminal interface with arrow-key (curses) navigation and color output. In the
recovery image it is started on the serial console by `jrescue-console@.service`.

### Features

- ✅ **Arrow Key Navigation** - Intuitive menu navigation with ↑↓ keys
- ✅ **Color Output** - Visual highlighting for selected items
- ✅ **Progress Bars** - Real-time progress with percentage and ETA
- ✅ **Ethernet Status** - Interface, cable link and IP address
- ✅ **Device Auto-Detection** - Finds all mmcblk devices automatically
- ✅ **Smart Filtering** - Only shows flashable `sdcard` images
- ✅ **Disposable Downloads** - Fresh downloads with automatic RAM cleanup
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
- **Fonts**: Regular weight throughout: the approved grid keeps DejaVu Sans Condensed
  (13–14px); inner screens use bundled Liberation Sans (14px headers and body,
  up to 19px progress numbers), with Liberation Sans Narrow keyboard glyphs up to 15px.
  The password field uses 15px Liberation Sans Narrow text, matching the keyboard.
  Both Liberation font files ship in application updates, without a Buildroot rebuild.

### OLED Display Examples

#### Main Menu (2×2)

```
┌──────────┐
│ Network  │   Flash
└──────────┘
    Info      Settings
        128 x 64 pixels
```

All four actions remain visible. UP/DOWN/LEFT/RIGHT selects a card without
wrapping across edges; ENTER opens it, and HOME resets to Network. Captions are
regular and fitted to the 128×64 panel, with wider, stronger pixel icons for the
0.96-inch display. Settings uses a single cog icon. Info contains Device,
Version and Web, showing the model, recovery build version and current web links. It has no Memory
entry, app version, uptime or telemetry gauges.
Inner screens use the selected 02 Liberation Sans style, plain white titles with
a thin underline, compact text spacing and
circular feedback. Page changes are immediate, without slide transitions.
The password keyboard retains all layouts and controls.

Future visual changes are shown as PNG and GIF previews first and applied only
after the user selects a variant.

The OLED and console interfaces start in English without a language prompt.
The OLED opens its 2×2 main menu directly, without a startup splash or delay.
Settings contains Language, Reboot, Power off and Display, in that order. Display offers
30 seconds, 1 minute (default), or Never; changes are kept in RAM only. Lists
focus the current setting, and Back/Home leaves it unchanged.
Selection lists and Network status pages show their position and total (e.g. `2/4`) at the top
right. The numeric counter is the only paging indicator; headers have no scroll arrows.
The OLED goes dark after one minute without button input. The first press wakes
the display and is consumed until release. Downloads, writes and hold
confirmations remain visible; finishing an operation starts a fresh idle period.
Language changes apply immediately and reset on reboot. Flash sources are API
and USB; there is no separate RAM/downloaded-images menu.

Downloaded images use the temporary RAM cache `/tmp/rescue`. Every application
download first removes old images and partial files, then starts from zero.
Canceling the flash hold confirmation with BACK or HOME discards the downloaded image;
it is also removed after the write, before the reboot screen. Failed or canceled
transfers leave no partial file. Cleanup uses ordinary file deletion, with no
content overwrite, and excludes USB sources and images currently being flashed.

Server downloads can be canceled while running: Back returns to the Flash
menu on OLED, Home returns to the main grid, and Esc cancels in the console.
The web interface has a download cancel button. Cancellation waits for the HTTP
worker to close its response and release the RAM cache before returning; a
stalled request may need its network timeout to expire. A cancellation arriving
just after completion also removes that image. Writing to eMMC cannot be
canceled through any frontend: the application waits for the writer to finish.

#### Network Menu

```
┌─────────────────────────────────┐
│ Network                         │ ← Title
├─────────────────────────────────┤
│                                 │
│ ❯ WiFi connect                  │ ← Selected
│   Network status                │
│                                 │
└─────────────────────────────────┘
```

Going back is done with the hardware BACK button (HOME jumps to the main menu).
The two OLED network actions are WiFi connect and Network status. The setup AP is
started automatically by the systemd boot decision; there is no Phone AP or
manual AP start/stop item in the application. Network status shows every detected
Ethernet and Wi-Fi adapter, including disconnected ones, on separate pages.
UP/DOWN changes the page; the top right shows only its number/total.
ENTER refreshes the status while keeping the current page; BACK/HOME returns.
Each page shows the adapter type, IPv4 address and Internet or link state.
MAC and speed are omitted. Viewing status does not interrupt Wi-Fi or the AP.

Internet status uses bounded TCP/443 checks through each adapter separately,
binding both the socket's interface and its source IPv4 address. The targets are
1.1.1.1 and 8.8.8.8, with a 1.5-second timeout per target; adapters are checked in
parallel. An unavailable interface binding shows unknown status. This checks
external TCP reachability; DNS, TLS and captive portals are not diagnosed here.
The indicator does not prevent image downloads.
Wi-Fi SSID lists use 12px text; wrapped names use a 13px line pitch, keeping
the lines close together without changing the typography of other menus.
Other inner menus and two-line messages use a 20px line pitch instead of 25px.

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

#### Password Keyboard

```
[key]: mypass|
 q w e r t y u i o p
  a s d f g h j k l
 ⇧ z x c v b n m ⌫
 123  .    ␣    _  OK
```

Selecting a secured network opens the editor directly, without an extra
confirmation. The password field has no white fill and starts at the left edge;
long input scrolls horizontally while the full value is retained.
Connection failures show their cause and a next step in two visible rows.
Password errors reopen the editor; unavailable networks, DHCP failures and
timeouts return to the network menu. Long SSIDs cannot hide the error reason.

The three QWERTY rows and separate bottom controls stay visible together, with no
vertical scrolling. UP/DOWN/LEFT/RIGHT moves between keys and ENTER selects.
Shift cycles through one uppercase letter, Caps Lock, and lowercase on three
presses, with no timing requirement. Typing a letter consumes one-shot Shift;
Caps Lock stays on until Shift is pressed again.
`123` opens numbers, `#+=` opens more symbols, and `ABC` returns to letters.
The bracket key inserts a space, backspace deletes, and OK submits. BACK/HOME cancels.
Space occupies 46 pixels at the center of the bottom row, with `.` to its left
and `_` to its right. These shortcuts are shared by all layouts and do not
repeat in the other symbol rows; `$`, `/` and `-` remain on the number page.
All 32 special characters remain available. Unused positions stay blank and
navigation skips them. The `#+=` symbols are packed from the left without gaps
between characters. `123`/`ABC` and OK occupy the bottom corners; backspace
remains at the right of the third row. The symbol-page toggle is at the lower left.
Ambiguous punctuation has distinct pixel contours. Lowercase `l` has a top hook
on its key and in the password; cursor and scroll widths account for it.
Menu `f` and `F` use a single-pixel vertical stroke to match the surrounding
regular text; their size and spacing are unchanged.
The password strip is 14px high and uses a small key icon followed by a colon
and a 3px gap instead of `Pass:`. When empty, it shows the key, colon and a
blinking caret, without placeholder text.
The field reuses the exact bitmaps drawn on the keys, including custom symbols
and fitted letters, so their size and shape match. Cursor and scrolling use
the same character widths.
UP from the top row focuses the password, LEFT/RIGHT moves the text cursor and
scrolls the visible window, and DOWN returns to the selected key. Characters
and backspace edit at the cursor without losing the hidden suffix or spaces.
ENTER in the password field returns to the keyboard; only its OK key submits.
There is no eye button or separate password-view screen.

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

#### Download and Flash Progress

The OLED displays the measured percentage inside a circular progress indicator,
with the image name on the right. Download details come from the shared core;
the OLED omits the target device label. Unknown progress uses an animated arc.

#### Confirmation Dialog

```
┌─────────────────────────────────┐
│          Flash image?           │
│                                 │
│       ◯       All data will     │
│               be erased!        │
│                                 │
└─────────────────────────────────┘
```

Download and flash confirmations use the same three-second center hold as
reboot. Download shows Download image and the size beside the circle, without
a header. Before writing a downloaded or USB image, Flash image? appears above
the circle and All data will / be erased! beside it. There is no divider or
Hold center for 3 s text.
A fresh press is required, releasing resets the circle, and
BACK/HOME cancels; stick directions do not cancel. Button input errors never start the operation.

#### System Information

Info opens a numbered selection list with the same highlighted rows as Network:
Device, Version and Web. UP/DOWN selects an entry and ENTER opens it. BACK
returns to the same selection; HOME returns to the main grid. ENTER on a detail
screen does nothing. Model/version are read once per Info visit without a
loading animation.

Model comes from the device tree with board detection as a fallback. Version
shows the recovery build's name/version from os-release, not the application
release. Memory, app version and uptime were removed. Opening Info does not
collect RAM/eMMC statistics or read filesystem metadata.

Web displays `http://` above the complete current `IP:8124`. With multiple
addresses, UP/DOWN changes pages and the header shows `1/2`, without arrows.
Addresses are read again when opening Web, including an active setup AP even
when NetworkManager does not manage it. This reads configured primary IPv4
addresses directly from the kernel; it sends no traffic and does not change
connections. With no address, it shows `No address`. The port is shared with
the web server through `core/config.py`.

### Reboot and Power off

Settings and the post-flash screen require a fresh continuous three-second hold
of the center button. Releasing retracts the circle; Back/Home cancels.
The opening press and autorepeat do not count. The systemd reboot request is
nonblocking, so shutdown does not wait on the application's own service.
Settings' Power off action uses the same guard and a nonblocking systemd poweroff
request. After the completed hold, it shows `Powering off...`.

### Features

- ✅ **Four-Item Grid** - All four actions visible, with directional selection
- ✅ **On-Screen Keyboard** - Full QWERTY with Shift and explicit number/symbol pages
- ✅ **Visual Feedback** - Underlined headers, circular progress and completion animations
- ✅ **Word Wrapping** - Automatic text wrapping for Russian/English
- ✅ **Progress Animations** - Circular activity and measured progress indicators
- ✅ **Error Handling** - Wrong password retry with clear messages
- ✅ **Multi-Language** - English and Russian support
- ✅ **Auto-Return** - Returns to menu after 2 seconds on success

## 📖 Usage Examples

### OLED Grid Application Examples

#### Example 1: Connect to WiFi via OLED

```
Hardware Buttons Navigation:

1. Power on → Main menu appears
2. UP/DOWN/LEFT/RIGHT → Navigate to "Network"
3. ENTER → Open Network menu
4. ENTER → Select "WiFi"
5. Wait for scan → Select your network with UP/DOWN
6. ENTER → Open password editor directly
7. Use the QWERTY keyboard for the password:
   - UP/DOWN/LEFT/RIGHT to navigate characters
   - ENTER to type a character
   - Shift: one uppercase letter → Caps Lock → lowercase, with no timing limit
   - 123 / #+= / ABC switch number, symbol and alphabet pages
   - Navigate to OK and press ENTER to submit
8. Wait for connection (2 seconds auto-return)
9. Back in Network menu
```

#### Example 2: Flash Firmware via OLED

```
1. Main menu → Navigate to "Flash"
2. ENTER → Open Flash menu
3. ENTER → Select "JetHome images" (or "From USB")
4. Wait for the firmware list from the JetHome API
5. UP/DOWN → Scroll through available images
6. ENTER → Select image
7. Hold center for 3 seconds to confirm downloading
8. Wait for download (circular progress shown)
9. Hold center for 3 seconds on the erase warning to confirm flashing
10. Wait for flashing (circular progress shown)
11. Hold center for 3 seconds to reboot, or BACK/HOME to return
```

#### Example 3: View System Info

```
1. Main menu → Navigate to "Info"
2. ENTER → Open device information
3. UP/DOWN → Select Device or Version
4. ENTER → Open details; center and directions have no action inside
5. BACK → Return to Info; HOME → Return to the main grid
```

---

## 📄 License

This project is designed for JetHome rescue systems.

## 🤝 Support

For issues and questions:
- JetHome Firmware: https://fw.jethome.com/
- JetHub Info: https://jethome.ru/devices/

## 📝 Version

**Current version:** v2.2.0

## 🎯 Project Structure

```
jrescue-app/
│
├── core/                         # Shared modules used by all frontends
│   ├── config.py                # Settings + board auto-detection (env/device-tree)
│   ├── network.py               # NetworkManager (nmcli) wrapper, device auto-detect
│   ├── download.py              # JetHome API + fresh RAM downloads
│   ├── image_cache.py           # Image cleanup and active-reader coordination
│   ├── flash.py                 # eMMC flashing (xz streaming, protected recovery region)
│   ├── image_writer.py          # Protected streaming writer for every flash path
│   ├── usb.py                   # USB device detection, mounting, image scan
│   ├── utils.py                 # curses menus/dialogs, system info, helpers
│   ├── system_info.py           # Device model and recovery build version
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
│   ├── render.py                # Shared OLED screen drawing and geometry
│   ├── menu.py                  # Navigation, on-screen keyboard
│   ├── keyboard_layout.py       # QWERTY state, Shift and key geometry
│   ├── fonts/                   # Bundled Liberation fonts and their licenses
│   ├── input.py                 # GPIO button handler (evdev)
│   ├── language.py              # OLED translations (EN/RU)
│   ├── config.py                # OLED-specific configuration
│   └── screens/                 # network / flash / info / settings / reboot
│
├── AGENTS.md                     # Project guide for AI agents
└── README.md                     # This file
```

---

**Made for JetHub Rescue Systems** 🚀


# Rescue Web Application

**Browser-based Interface for JetHub Rescue Operations**

A modern web interface for managing network configuration, downloading firmware, and flashing eMMC on JetHub devices. Built with Python standard library (no external dependencies) and Bootstrap 5.

---

## 📋 Features

- 🌐 **Network Management** - Configure WiFi and Ethernet connections
- 📥 **Firmware Download** - Fetch images from JetHome API
- 💾 **eMMC Flashing** - Write images directly to eMMC with progress tracking
- 📊 **Real-time Progress** - Live updates for downloads and flashing operations
- 📱 **Responsive Design** - Works on desktop, tablet, and mobile
- 🔒 **Safety Features** - Multiple confirmations for destructive operations

---

## 🚀 Quick Start

### Prerequisites

- Python 3.14 (as shipped in the recovery image; 3.7+ to run elsewhere)
- Root access (required for network configuration and flashing)
- Network connection (for downloading firmware)

### Starting the Server

```bash
cd /root/rescue-consoleview/web-application
sudo python3 main.py
```

The server will start on port **8124**. Access it from your browser:

```
http://<device-ip>:8124
```

For example:
- `http://192.168.1.100:8124` (local network)
- `http://10.0.0.50:8124` (VPN/remote)

### Stopping the Server

Press `Ctrl+C` in the terminal to stop the server.

---

## 💻 User Interface

### Network Tab

Configure network connections and check connectivity status.

**Features:**
- View current network status (all interfaces)
- Scan for available WiFi networks
- Connect to WiFi with password
- Ethernet status monitoring (auto-connects via DHCP)
- Real-time connection status

**Usage:**
1. Click **"Scan for Networks"** to find WiFi networks
2. Select a network from the dropdown
3. Enter the password
4. Click **"Connect"**

**Note:** Ethernet connects automatically via DHCP when cable is plugged in. No manual action needed.

### Flash eMMC Tab

Download firmware images and flash them to eMMC.

**Features:**
- Browse available firmware images (JetHome API)
- Download images with progress tracking
- Flash images to eMMC
- Real-time progress updates
- Safety confirmations

**Usage:**
1. Click **"Refresh List"** to load available images
2. Click **"Download"** on your desired image
3. Wait for download to complete
4. Confirm flashing to eMMC
5. Wait for flashing to complete (do not power off!)

**⚠️ WARNING:** Flashing will erase all data on eMMC. Make sure you have backups if needed.

### System Tab

View system information and manage the device.

**Features:**
- Device information (model, platform, eMMC size)
- Free RAM/disk space
- System reboot

**Usage:**
- Review system information
- Click **"Reboot System"** to restart the device

---

## 🔌 API Documentation

The web application provides a REST API on the same port (8124).

### Network Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/network/status` | Get current network status |
| POST | `/api/network/wifi/scan` | Scan for WiFi networks |
| POST | `/api/network/wifi/connect` | Connect to WiFi |
| GET | `/api/network/test` | Test internet connectivity |

**Note:** Ethernet connects automatically via DHCP - no API endpoint needed.

#### Example: Connect to WiFi

```bash
curl -X POST http://localhost:8124/api/network/wifi/connect \
  -H "Content-Type: application/json" \
  -d '{"ssid": "MyNetwork", "password": "mypassword"}'
```

Response:
```json
{
  "success": true,
  "message": "Connected to MyNetwork",
  "status": {
    "interface": "wlan0",
    "connected": true,
    "ip": "192.168.1.100",
    "ssid": "MyNetwork"
  }
}
```

### Flash Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/flash/images` | List available images |
| POST | `/api/flash/download` | Start image download |
| GET | `/api/flash/progress` | Get download/flash progress |
| POST | `/api/flash/start` | Start flashing to eMMC |
| DELETE | `/api/flash/cancel` | Cancel operation |

#### Example: Get Available Images

```bash
curl http://localhost:8124/api/flash/images
```

Response:
```json
{
  "success": true,
  "images": [
    {
      "source": "jethome",
      "name": "JetHome Armbian Bookworm",
      "version": "25.11.0",
      "date": "2025-10-09T15:27:11+00:00",
      "size": 562558628,
      "url": "https://fw.jethome.com/...",
      "filename": "jethome_j200_armbian.img.xz"
    }
  ]
}
```

### USB Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/usb/status` | Check USB device status |
| POST | `/api/usb/mount` | Mount USB drive |
| GET | `/api/usb/images` | List images on USB |

### System Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/system/info` | Get system information |
| POST | `/api/system/reboot` | Reboot the system |

---

## ⚙️ Configuration

Configuration is in `config.py`:

```python
# Web server settings
WEB_SERVER_HOST = "0.0.0.0"  # Listen on all interfaces
WEB_SERVER_PORT = 8124       # HTTP port

# Import settings from console-application
# (network, flash, download settings)
```

To change the port, edit `WEB_SERVER_PORT` and restart the server.

---

## 🔧 Troubleshooting

### Port Already in Use

```
❌ Error: Port 8124 is already in use
```

**Solution:** Stop any existing server or change the port in `config.py`.

### Permission Denied

```
⚠️ WARNING: Not running as root!
```

**Solution:** Run with `sudo python3 main.py`

### Cannot Connect to Server

**Check:**
1. Server is running (`sudo python3 main.py`)
2. Firewall allows port 8124
3. Using correct IP address
4. Device is on the same network

### Network Operations Fail

**Check:**
1. Running as root
2. NetworkManager (nmcli) is available
3. Network interfaces exist (`ip link show`)

### Flash Operations Fail

**Check:**
1. Running as root
2. eMMC device exists (`/dev/mmcblk1`)
3. Enough free space in `/tmp` (600MB+)
4. Image file is valid (.img.xz format)

---

## 🏗️ Architecture

### Backend (Python)

- **HTTP Server:** `http.server.BaseHTTPRequestHandler`
- **Routing:** Custom path-based routing
- **Threading:** Background threads for long operations
- **State Management:** Global dictionaries for progress tracking

### Frontend (HTML/JS)

- **Framework:** Bootstrap 5 (CDN)
- **JavaScript:** Vanilla ES6 (no frameworks)
- **API Communication:** Fetch API
- **Updates:** Polling-based (500ms interval)

### File Structure

```
web-application/
├── main.py              # HTTP server entry point
├── config.py            # Configuration
├── api_handler.py       # REST API logic
├── __init__.py          # Package init
├── static/
│   ├── index.html       # Main UI
│   ├── css/
│   │   └── style.css    # Custom styles
│   └── js/
│       └── app.js       # Frontend logic
└── README.md            # This file
```

---

## 🔒 Security Notes

- **No Authentication:** Designed for local network use only
- **Root Required:** Many operations need root privileges
- **CORS Enabled:** For development flexibility
- **Input Validation:** All API inputs are validated
- **Confirmations:** Multiple confirmations for destructive operations

**⚠️ Do not expose this server to the public internet without adding authentication!**

---

## 🐛 Known Issues

- Download cancellation is not fully implemented (resets state only)
- Flash progress shows spinner (no actual percentage)
- USB image listing not yet implemented

---

## 📚 Related Documentation

- [Console Application](../console-application/README.md)
- [OLED Application](../oled-grid-application/README.md)

---

## 📧 Support

For issues with the web application, check:
1. Server logs (terminal output)
2. Browser console (F12)
3. Network tab in browser dev tools

---

## 📄 License

Part of the Rescue Console Application project for JetHub.

---

**Version:** 1.0.0
**Last Updated:** 2025-01-11


#!/usr/bin/env python3
"""
Rescue Web Application - HTTP Server

Browser-based interface for JetHub D2 rescue operations.
Runs on port 8124 using only Python standard library.
"""

import http.server
import socketserver
import json
import os
import sys
import urllib.parse
import mimetypes
from pathlib import Path

# Add current directory to path
sys.path.insert(0, os.path.dirname(__file__))

import config
from api_handler import APIHandler

class RescueWebHandler(http.server.BaseHTTPRequestHandler):
    """HTTP request handler for Rescue Web Application"""

    def __init__(self, *args, **kwargs):
        self.api_handler = APIHandler()
        super().__init__(*args, **kwargs)

    def log_message(self, format, *args):
        """Override to suppress HTTP access logs (respects VERBOSE_LOGS)"""
        if getattr(config, 'VERBOSE_LOGS', True):
            super().log_message(format, *args)

    def send_json_response(self, data, status=200):
        """Send JSON response"""
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode('utf-8'))

    def send_error_response(self, message, status=400):
        """Send error response"""
        self.send_json_response({'success': False, 'error': message}, status)

    def serve_static_file(self, path):
        """Serve static files"""
        # Default to index.html
        if path == '/' or path == '':
            path = '/index.html'

        # Remove leading slash
        if path.startswith('/'):
            path = path[1:]

        # Build full path
        static_dir = os.path.join(os.path.dirname(__file__), config.STATIC_DIR)
        file_path = os.path.join(static_dir, path)

        # Security: prevent directory traversal
        file_path = os.path.abspath(file_path)
        static_dir = os.path.abspath(static_dir)
        if not file_path.startswith(static_dir):
            self.send_error(403, 'Forbidden')
            return

        # Check if file exists
        if not os.path.exists(file_path) or not os.path.isfile(file_path):
            self.send_error(404, 'File not found')
            return

        # Guess content type
        content_type, _ = mimetypes.guess_type(file_path)
        if content_type is None:
            content_type = 'application/octet-stream'

        # Send file
        try:
            with open(file_path, 'rb') as f:
                self.send_response(200)
                self.send_header('Content-Type', content_type)
                self.send_header('Content-Length', os.path.getsize(file_path))
                self.end_headers()
                self.wfile.write(f.read())
        except Exception as e:
            self.send_error(500, f'Error reading file: {e}')

    def do_OPTIONS(self):
        """Handle OPTIONS requests (CORS preflight)"""
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, DELETE, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def do_GET(self):
        """Handle GET requests"""
        parsed_path = urllib.parse.urlparse(self.path)
        path = parsed_path.path

        # API routes
        if path.startswith('/api/'):
            self.handle_api_get(path)
        else:
            # Static files
            self.serve_static_file(path)

    def do_POST(self):
        """Handle POST requests"""
        parsed_path = urllib.parse.urlparse(self.path)
        path = parsed_path.path

        if path.startswith('/api/'):
            self.handle_api_post(path)
        else:
            self.send_error(404, 'Not found')

    def do_DELETE(self):
        """Handle DELETE requests"""
        parsed_path = urllib.parse.urlparse(self.path)
        path = parsed_path.path

        if path.startswith('/api/'):
            self.handle_api_delete(path)
        else:
            self.send_error(404, 'Not found')

    def handle_api_get(self, path):
        """Route GET API requests"""
        try:
            # Network endpoints
            if path == '/api/network/status':
                result = self.api_handler.get_network_status()
                self.send_json_response(result)

            elif path == '/api/network/test':
                result = self.api_handler.get_network_test()
                self.send_json_response(result)

            # Flash endpoints
            elif path == '/api/flash/images':
                result = self.api_handler.get_flash_images()
                self.send_json_response(result)

            elif path == '/api/flash/progress':
                result = self.api_handler.get_flash_progress()
                self.send_json_response(result)

            elif path == '/api/flash/files':
                result = self.api_handler.get_flash_files()
                self.send_json_response(result)

            # USB endpoints
            elif path == '/api/usb/status':
                result = self.api_handler.get_usb_status()
                self.send_json_response(result)

            elif path == '/api/usb/images':
                result = self.api_handler.get_usb_images()
                self.send_json_response(result)

            # System endpoints
            elif path == '/api/system/info':
                result = self.api_handler.get_system_info()
                self.send_json_response(result)

            else:
                self.send_error_response('Unknown endpoint', 404)

        except Exception as e:
            import traceback
            traceback.print_exc()
            self.send_error_response(str(e), 500)

    def handle_api_post(self, path):
        """Route POST API requests"""
        try:
            # Read request body
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length)

            # Parse JSON
            try:
                data = json.loads(body.decode('utf-8')) if body else {}
            except json.JSONDecodeError:
                self.send_error_response('Invalid JSON')
                return

            # Network endpoints
            if path == '/api/network/wifi/scan':
                result = self.api_handler.post_wifi_scan()
                self.send_json_response(result)

            elif path == '/api/network/wifi/connect':
                result = self.api_handler.post_wifi_connect(data)
                self.send_json_response(result)

            # Ethernet connects automatically - no manual endpoint needed

            # Flash endpoints
            elif path == '/api/flash/download':
                result = self.api_handler.post_flash_download(data)
                self.send_json_response(result)

            elif path == '/api/flash/start':
                result = self.api_handler.post_flash_start(data)
                self.send_json_response(result)

            # USB endpoints
            elif path == '/api/usb/mount':
                result = self.api_handler.post_usb_mount()
                self.send_json_response(result)

            # System endpoints
            elif path == '/api/system/reboot':
                result = self.api_handler.post_system_reboot()
                self.send_json_response(result)

            else:
                self.send_error_response('Unknown endpoint', 404)

        except Exception as e:
            import traceback
            traceback.print_exc()
            self.send_error_response(str(e), 500)

    def handle_api_delete(self, path):
        """Route DELETE API requests"""
        try:
            # Read request body if present
            content_length = int(self.headers.get('Content-Length', 0))
            data = {}
            if content_length > 0:
                body = self.rfile.read(content_length)
                data = json.loads(body.decode('utf-8'))

            if path == '/api/flash/cancel':
                result = self.api_handler.delete_flash_cancel()
                self.send_json_response(result)

            elif path == '/api/flash/file':
                result = self.api_handler.delete_flash_file(data)
                self.send_json_response(result)

            else:
                self.send_error_response('Unknown endpoint', 404)

        except Exception as e:
            import traceback
            traceback.print_exc()
            self.send_error_response(str(e), 500)


def check_root():
    """Check if running as root"""
    if os.geteuid() != 0 and getattr(config, 'VERBOSE_LOGS', True):
        print("⚠️  WARNING: Not running as root!")
        print("Some operations (network config, flashing) will fail.")
        print("Run with: sudo python3 main.py")
        print()


def main():
    """Main entry point"""
    verbose = getattr(config, 'VERBOSE_LOGS', True)

    if verbose:
        print("╔═══════════════════════════════════════════════════════════════╗")
        print("║                                                               ║")
        print("║              RESCUE WEB APPLICATION                           ║")
        print("║                                                               ║")
        print("║           eMMC Image Flasher - Web Interface                 ║")
        print("║                  Device: JetHub D2                            ║")
        print("║                                                               ║")
        print("╚═══════════════════════════════════════════════════════════════╝")
        print()

    check_root()

    # Create temp directory if needed
    os.makedirs(config.TEMP_DIR, exist_ok=True)

    # Start server
    host = config.WEB_SERVER_HOST
    port = config.WEB_SERVER_PORT

    try:
        with socketserver.TCPServer((host, port), RescueWebHandler) as httpd:
            if verbose:
                print(f"🌐 Web server started on {host}:{port}")
                print()
                print(f"Access the web interface at:")
                print(f"  http://<device-ip>:{port}")
                print()
                print("Press Ctrl+C to stop")
                print()

            httpd.serve_forever()

    except KeyboardInterrupt:
        if verbose:
            print("\n\n✓ Server stopped")
    except OSError as e:
        if e.errno == 98:
            print(f"❌ Error: Port {port} is already in use")
            print(f"   Stop any existing server or use a different port")
        else:
            print(f"❌ Error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()


/**
 * Rescue Web Application - Frontend JavaScript
 * Handles all API calls and UI interactions
 */

// Global state
let progressInterval = null;
let currentDownloadPath = null;

// ==================== UTILITY FUNCTIONS ====================

/**
 * Make API call
 */
async function apiCall(endpoint, method = 'GET', data = null) {
    try {
        const options = {
            method: method,
            headers: {}
        };

        if (data) {
            options.headers['Content-Type'] = 'application/json';
            options.body = JSON.stringify(data);
        }

        const response = await fetch(`/api${endpoint}`, options);
        return await response.json();
    } catch (error) {
        console.error('API call failed:', error);
        return { success: false, error: error.message };
    }
}

/**
 * Show toast notification
 */
function showNotification(title, message, type = 'info') {
    const toastEl = document.getElementById('notification-toast');
    const toast = new bootstrap.Toast(toastEl);

    document.getElementById('toast-title').textContent = title;
    document.getElementById('toast-body').textContent = message;

    // Change color based on type
    toastEl.className = 'toast';
    if (type === 'success') {
        toastEl.classList.add('bg-success', 'text-white');
    } else if (type === 'error') {
        toastEl.classList.add('bg-danger', 'text-white');
    } else if (type === 'warning') {
        toastEl.classList.add('bg-warning');
    }

    toast.show();
}

/**
 * Format bytes to human readable
 */
function formatBytes(bytes) {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
}

/**
 * Format date string
 */
function formatDate(dateStr) {
    if (!dateStr || dateStr === 'N/A') return 'N/A';
    const date = new Date(dateStr);
    return date.toLocaleDateString() + ' ' + date.toLocaleTimeString();
}

/**
 * Escape HTML to prevent XSS
 */
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// ==================== NETWORK FUNCTIONS ====================

/**
 * Load network status
 * @param {boolean} showLoading - Show loading spinner (default: false for silent updates)
 */
async function loadNetworkStatus(showLoading = false) {
    const statusDiv = document.getElementById('network-status');
    const connectionStatus = document.getElementById('connection-status');

    // Show loading indicator only if explicitly requested (first load or manual refresh)
    if (showLoading) {
        statusDiv.innerHTML = `
            <div class="text-center text-muted">
                <div class="spinner-border spinner-border-sm" role="status"></div>
                <span class="ms-2">Loading...</span>
            </div>
        `;
    }

    const result = await apiCall('/network/status');

    if (result.success && result.interfaces) {
        let html = '<div class="list-group">';

        for (const iface of result.interfaces) {
            const icon = iface.interface === 'wlan0' ? 'bi-wifi' : 'bi-ethernet';
            const statusClass = iface.connected ? 'text-success' : 'text-secondary';

            // Show IP acquisition status
            let ipStatus = '';
            if (iface.connected && !iface.ip) {
                ipStatus = `
                    <div class="mt-2">
                        <small class="text-warning">
                            <i class="bi bi-hourglass-split"></i> Acquiring IP address...
                        </small>
                    </div>
                `;
            } else if (iface.ip) {
                ipStatus = `<div class="mt-2"><small class="text-success"><i class="bi bi-check-circle"></i> IP: ${iface.ip}</small></div>`;
            }

            html += `
                <div class="list-group-item">
                    <div class="d-flex justify-content-between align-items-center">
                        <div>
                            <i class="bi ${icon} ${statusClass}"></i>
                            <strong>${iface.interface}</strong>
                        </div>
                        <span class="badge ${iface.connected ? 'bg-success' : 'bg-secondary'}">
                            ${iface.connected ? 'Connected' : 'Disconnected'}
                        </span>
                    </div>
                    ${ipStatus}
                    ${iface.ssid ? `<div><small>SSID: ${iface.ssid}</small></div>` : ''}
                </div>
            `;
        }

        html += '</div>';
        statusDiv.innerHTML = html;

        // Update header status
        const connected = result.interfaces.some(i => i.connected);
        const hasIp = result.interfaces.some(i => i.connected && i.ip);

        if (connected && hasIp) {
            connectionStatus.innerHTML = '<i class="bi bi-circle-fill text-success"></i> Connected';
        } else if (connected && !hasIp) {
            connectionStatus.innerHTML = '<i class="bi bi-circle-fill text-warning"></i> Connecting...';
        } else {
            connectionStatus.innerHTML = '<i class="bi bi-circle-fill text-danger"></i> Disconnected';
        }
    } else {
        statusDiv.innerHTML = '<p class="text-danger">Failed to load network status</p>';
        connectionStatus.innerHTML = '<i class="bi bi-circle-fill text-secondary"></i> Error';
    }
}

/**
 * Scan for WiFi networks
 */
async function scanWiFi() {
    const btn = document.getElementById('scan-wifi-btn');
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Scanning...';

    const result = await apiCall('/network/wifi/scan', 'POST');

    btn.disabled = false;
    btn.innerHTML = '<i class="bi bi-search"></i> Scan for Networks';

    if (result.success && result.networks) {
        const select = document.getElementById('wifi-ssid');
        const networksDiv = document.getElementById('wifi-networks');

        select.innerHTML = '<option value="">Select network...</option>';

        for (const network of result.networks) {
            const option = document.createElement('option');
            option.value = network.ssid;
            option.textContent = `${network.ssid} (${network.signal}%)`;
            select.appendChild(option);
        }

        networksDiv.classList.remove('d-none');
        showNotification('Success', `Found ${result.networks.length} networks`, 'success');
    } else {
        showNotification('Error', result.error || 'Failed to scan WiFi', 'error');
    }
}

/**
 * Toggle password visibility
 */
function togglePasswordVisibility() {
    const passwordInput = document.getElementById('wifi-password');
    const passwordIcon = document.getElementById('password-icon');

    if (passwordInput.type === 'password') {
        passwordInput.type = 'text';
        passwordIcon.classList.remove('bi-eye');
        passwordIcon.classList.add('bi-eye-slash');
    } else {
        passwordInput.type = 'password';
        passwordIcon.classList.remove('bi-eye-slash');
        passwordIcon.classList.add('bi-eye');
    }
}

/**
 * Connect to WiFi
 */
async function connectWiFi() {
    const ssid = document.getElementById('wifi-ssid').value;
    const password = document.getElementById('wifi-password').value;
    const connectBtn = document.getElementById('connect-wifi-btn');
    const statusDiv = document.getElementById('wifi-connection-status');
    const statusText = document.getElementById('wifi-status-text');

    if (!ssid) {
        showNotification('Error', 'Please select a network', 'warning');
        return;
    }

    // Disable button and show loading state
    connectBtn.disabled = true;
    connectBtn.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Connecting...';
    statusDiv.classList.remove('d-none');
    statusText.textContent = `Connecting to ${ssid}...`;

    try {
        const result = await apiCall('/network/wifi/connect', 'POST', {
            ssid: ssid,
            password: password
        });

        if (result.success) {
            statusText.textContent = 'Connected! Waiting for IP address...';

            // Poll for IP address with visual feedback
            let attempts = 0;
            const maxAttempts = 30; // 30 seconds max
            const pollInterval = setInterval(async () => {
                attempts++;
                const statusResult = await apiCall('/network/status');

                if (statusResult.success && statusResult.interfaces) {
                    const wifiInterface = statusResult.interfaces.find(i => i.interface === 'wlan0');

                    if (wifiInterface && wifiInterface.connected && wifiInterface.ip) {
                        clearInterval(pollInterval);
                        statusText.textContent = `Connected! IP: ${wifiInterface.ip}`;
                        statusDiv.classList.remove('alert-info');
                        statusDiv.classList.add('alert-success');

                        // Update network status display (silent update)
                        loadNetworkStatus(false);

                        // Reset button after 3 seconds
                        setTimeout(() => {
                            connectBtn.disabled = false;
                            connectBtn.innerHTML = '<i class="bi bi-plug"></i> Connect';
                            setTimeout(() => {
                                statusDiv.classList.add('d-none');
                                statusDiv.classList.remove('alert-success');
                                statusDiv.classList.add('alert-info');
                            }, 2000);
                        }, 3000);

                        showNotification('Success', `Connected to ${ssid}. IP: ${wifiInterface.ip}`, 'success');
                    } else if (attempts >= maxAttempts) {
                        clearInterval(pollInterval);
                        statusText.textContent = 'Connected but IP address not assigned yet';
                        statusDiv.classList.remove('alert-info');
                        statusDiv.classList.add('alert-warning');
                        connectBtn.disabled = false;
                        connectBtn.innerHTML = '<i class="bi bi-plug"></i> Connect';
                        loadNetworkStatus();
                        showNotification('Warning', 'Connected but IP address not assigned yet', 'warning');
                    } else {
                        statusText.textContent = `Connected! Waiting for IP address... (${attempts}s)`;
                    }
                }
            }, 1000);
        } else {
            statusDiv.classList.remove('alert-info');
            statusDiv.classList.add('alert-danger');
            statusText.textContent = result.error || 'Failed to connect';
            connectBtn.disabled = false;
            connectBtn.innerHTML = '<i class="bi bi-plug"></i> Connect';
            showNotification('Error', result.error || 'Failed to connect', 'error');

            setTimeout(() => {
                statusDiv.classList.add('d-none');
                statusDiv.classList.remove('alert-danger');
                statusDiv.classList.add('alert-info');
            }, 5000);
        }
    } catch (error) {
        statusDiv.classList.remove('alert-info');
        statusDiv.classList.add('alert-danger');
        statusText.textContent = 'Connection error';
        connectBtn.disabled = false;
        connectBtn.innerHTML = '<i class="bi bi-plug"></i> Connect';
        showNotification('Error', 'Connection error occurred', 'error');

        setTimeout(() => {
            statusDiv.classList.add('d-none');
            statusDiv.classList.remove('alert-danger');
            statusDiv.classList.add('alert-info');
        }, 5000);
    }
}

/**
 * Ethernet connects automatically via DHCP when cable is plugged in.
 * No manual connection needed - status is shown in Network Status card.
 */

// ==================== FLASH FUNCTIONS ====================

/**
 * Load available images
 */
async function loadImages() {
    const listDiv = document.getElementById('image-list');
    listDiv.innerHTML = '<div class="text-center"><div class="spinner-border spinner-border-sm"></div> Loading...</div>';

    const result = await apiCall('/flash/images');

    if (result.success && result.images) {
        if (result.images.length === 0) {
            listDiv.innerHTML = '<p class="text-muted">No images available</p>';
            return;
        }

        let html = '<div class="list-group">';

        for (const image of result.images) {
            html += `
                <div class="list-group-item">
                    <div class="d-flex justify-content-between align-items-start">
                        <div class="flex-grow-1">
                            <h6 class="mb-1">${image.name}</h6>
                            <p class="mb-1 small text-muted">
                                Version: ${image.version || 'N/A'}<br>
                                Size: ${formatBytes(image.size)}<br>
                                Date: ${formatDate(image.date)}
                            </p>
                        </div>
                        <button class="btn btn-sm btn-primary" onclick='downloadImage(${JSON.stringify(image)})'>
                            <i class="bi bi-download"></i> Download
                        </button>
                    </div>
                </div>
            `;
        }

        html += '</div>';
        listDiv.innerHTML = html;
    } else {
        listDiv.innerHTML = '<p class="text-danger">Failed to load images</p>';
        showNotification('Error', result.error || 'Failed to load images', 'error');
    }
}

/**
 * Download image
 */
async function downloadImage(image) {
    const result = await apiCall('/flash/download', 'POST', {
        url: image.url,
        filename: image.filename,
        size: image.size
    });

    if (result.success) {
        showNotification('Download Started', `Downloading ${image.name} (${formatBytes(image.size)})`, 'info');
        currentDownloadPath = null;
        startProgressMonitoring();
    } else {
        showNotification('Error', result.error || 'Failed to start download', 'error');
    }
}

/**
 * Start progress monitoring
 */
function startProgressMonitoring() {
    const downloadDiv = document.getElementById('download-progress');
    const flashingDiv = document.getElementById('flashing-progress');
    const statusDiv = document.getElementById('flash-status');

    downloadDiv.classList.remove('d-none');
    statusDiv.classList.add('d-none');

    if (progressInterval) {
        clearInterval(progressInterval);
    }

    progressInterval = setInterval(async () => {
        const result = await apiCall('/flash/progress');

        if (!result.success) {
            return;
        }

        // Download progress
        if (result.download.active) {
            const progress = result.download.progress || 0;
            const total = result.download.total || 0;

            let percent = 0;
            if (total > 0) {
                percent = Math.round((progress / total) * 100);
            }

            const progressBar = document.getElementById('download-progress-bar');
            const statusText = document.getElementById('download-status');

            progressBar.style.width = percent + '%';
            progressBar.textContent = percent + '%';
            statusText.textContent = `${formatBytes(progress)} / ${formatBytes(total)} (${percent}%)`;
        }

        // Download complete
        if (!result.download.active && result.download.path) {
            downloadDiv.classList.add('d-none');
            currentDownloadPath = result.download.path;

            clearInterval(progressInterval);
            progressInterval = null;

            showNotification('Download Complete', 'Image downloaded successfully! Check Downloaded Files section below.', 'success');

            // Reload downloaded files list
            loadDownloadedFiles();

            statusDiv.classList.remove('d-none');
            statusDiv.innerHTML = `<p class="text-success"><i class="bi bi-check-circle"></i> Download complete! File is ready in Downloaded Files section.</p>`;
        }

        // Download error
        if (result.download.error) {
            downloadDiv.classList.add('d-none');
            statusDiv.classList.remove('d-none');
            statusDiv.innerHTML = `<p class="text-danger">Download failed: ${result.download.error}</p>`;
            clearInterval(progressInterval);
            progressInterval = null;
            showNotification('Error', result.download.error, 'error');
        }

        // Flash progress
        if (result.flash.active) {
            downloadDiv.classList.add('d-none');
            flashingDiv.classList.remove('d-none');
            statusDiv.classList.add('d-none');
        }

        // Flash complete
        if (result.flash.status === 'complete') {
            flashingDiv.classList.add('d-none');
            statusDiv.classList.remove('d-none');
            statusDiv.innerHTML = `
                <div class="alert alert-success" role="alert">
                    <i class="bi bi-check-circle"></i>
                    <strong>Flash Complete!</strong>
                    <p class="mb-0">eMMC has been flashed successfully. You can now reboot the system.</p>
                </div>
            `;
            clearInterval(progressInterval);
            progressInterval = null;
            showNotification('Success', 'Flash complete!', 'success');
        }

        // Flash error
        if (result.flash.error) {
            flashingDiv.classList.add('d-none');
            statusDiv.classList.remove('d-none');
            statusDiv.innerHTML = `<p class="text-danger">Flash failed: ${result.flash.error}</p>`;
            clearInterval(progressInterval);
            progressInterval = null;
            showNotification('Error', result.flash.error, 'error');
        }
    }, 500);
}

/**
 * Flash image to eMMC
 */
async function flashImage(path) {
    if (!confirm('FINAL CONFIRMATION\n\nThis will ERASE ALL DATA on eMMC!\n\nAre you absolutely sure?')) {
        return;
    }

    const result = await apiCall('/flash/start', 'POST', {
        path: path
    });

    if (result.success) {
        showNotification('Flashing Started', 'Writing to eMMC...', 'warning');
        startProgressMonitoring();
    } else {
        showNotification('Error', result.error || 'Failed to start flashing', 'error');
    }
}

/**
 * Cancel current download
 */
async function cancelDownload() {
    if (!confirm('Cancel the current download?')) {
        return;
    }

    const result = await apiCall('/flash/cancel', 'DELETE');

    if (result.success) {
        showNotification('Canceled', 'Download canceled', 'info');

        // Hide progress
        const downloadDiv = document.getElementById('download-progress');
        const statusDiv = document.getElementById('flash-status');
        downloadDiv.classList.add('d-none');
        statusDiv.classList.remove('d-none');
        statusDiv.innerHTML = `<p class="text-muted">No operation in progress</p>`;

        // Stop polling
        if (progressInterval) {
            clearInterval(progressInterval);
            progressInterval = null;
        }
    } else {
        showNotification('Error', result.error || 'Failed to cancel', 'error');
    }
}

/**
 * Load downloaded files list
 */
async function loadDownloadedFiles() {
    const filesDiv = document.getElementById('downloaded-files');

    const result = await apiCall('/flash/files');

    if (result.success) {
        const files = result.files || [];

        if (files.length === 0) {
            filesDiv.innerHTML = '<p class="text-muted">No downloaded files</p>';
            return;
        }

        let html = '<div class="list-group">';
        files.forEach(file => {
            html += `
                <div class="list-group-item d-flex justify-content-between align-items-center">
                    <div>
                        <h6 class="mb-1">${escapeHtml(file.filename)}</h6>
                        <small class="text-muted">${file.size_human}</small>
                    </div>
                    <div class="btn-group" role="group">
                        <button class="btn btn-sm btn-warning" onclick="flashDownloadedFile('${escapeHtml(file.path)}', '${escapeHtml(file.filename)}')">
                            <i class="bi bi-hdd"></i> Flash
                        </button>
                        <button class="btn btn-sm btn-danger" onclick="deleteFile('${escapeHtml(file.path)}', '${escapeHtml(file.filename)}')">
                            <i class="bi bi-trash"></i> Delete
                        </button>
                    </div>
                </div>
            `;
        });
        html += '</div>';

        filesDiv.innerHTML = html;
    } else {
        filesDiv.innerHTML = '<p class="text-danger">Failed to load files</p>';
        showNotification('Error', result.error || 'Failed to load files', 'error');
    }
}

/**
 * Delete downloaded file
 */
async function deleteFile(path, filename) {
    if (!confirm(`Delete file: ${filename}?`)) {
        return;
    }

    const result = await apiCall('/flash/file', 'DELETE', {
        path: path
    });

    if (result.success) {
        showNotification('Deleted', `File ${filename} deleted`, 'success');
        loadDownloadedFiles();
    } else {
        showNotification('Error', result.error || 'Failed to delete file', 'error');
    }
}

/**
 * Flash downloaded file to eMMC
 */
async function flashDownloadedFile(path, filename) {
    if (!confirm(`Flash ${filename} to eMMC?\n\nWARNING: This will ERASE ALL DATA on eMMC!\n\nAre you absolutely sure?`)) {
        return;
    }

    const result = await apiCall('/flash/start', 'POST', {
        path: path
    });

    if (result.success) {
        showNotification('Flashing Started', `Writing ${filename} to eMMC...`, 'warning');
        startProgressMonitoring();
    } else {
        showNotification('Error', result.error || 'Failed to start flashing', 'error');
    }
}

// ==================== SYSTEM FUNCTIONS ====================

/**
 * Load system information
 */
async function loadSystemInfo() {
    const infoDiv = document.getElementById('system-info');

    const result = await apiCall('/system/info');

    if (result.success && result.info) {
        const info = result.info;
        const disk = result.disk_space;

        let html = '<table class="table table-sm">';
        html += '<tbody>';
        html += `<tr><th>Device</th><td>${info.device_name || 'Unknown'}</td></tr>`;
        html += `<tr><th>Platform</th><td>${info.platform || 'Unknown'}</td></tr>`;
        html += `<tr><th>eMMC Device</th><td>${info.emmc_device || 'Unknown'}</td></tr>`;
        html += `<tr><th>eMMC Size</th><td>${info.emmc_size_human || 'Unknown'}</td></tr>`;
        if (disk) {
            html += `<tr><th>Free RAM</th><td>${disk.free_human || 'Unknown'}</td></tr>`;
        }
        html += '</tbody>';
        html += '</table>';

        infoDiv.innerHTML = html;
    } else {
        infoDiv.innerHTML = '<p class="text-danger">Failed to load system information</p>';
    }
}

/**
 * Reboot system
 */
async function rebootSystem() {
    if (!confirm('Are you sure you want to reboot the system?')) {
        return;
    }

    const result = await apiCall('/system/reboot', 'POST');

    if (result.success) {
        showNotification('Rebooting', result.message, 'warning');

        // Show countdown
        let countdown = 5;
        const interval = setInterval(() => {
            countdown--;
            if (countdown <= 0) {
                clearInterval(interval);
                document.body.innerHTML = `
                    <div class="container text-center mt-5">
                        <h2>System is rebooting...</h2>
                        <p>Please wait a moment and refresh the page.</p>
                    </div>
                `;
            } else {
                showNotification('Rebooting', `System will reboot in ${countdown} seconds...`, 'warning');
            }
        }, 1000);
    } else {
        showNotification('Error', result.error || 'Failed to reboot', 'error');
    }
}

// ==================== INITIALIZATION ====================

/**
 * Initialize application
 */
document.addEventListener('DOMContentLoaded', () => {
    // Load initial data (show loading on first load)
    loadNetworkStatus(true);  // Show loading spinner on first load
    loadImages();
    loadDownloadedFiles();
    loadSystemInfo();

    // Refresh network status every 10 seconds (silent update, no loading spinner)
    setInterval(() => loadNetworkStatus(false), 10000);

    // Listen for tab changes
    const tabEls = document.querySelectorAll('button[data-bs-toggle="tab"]');
    tabEls.forEach(tabEl => {
        tabEl.addEventListener('shown.bs.tab', (event) => {
            const target = event.target.getAttribute('data-bs-target');

            if (target === '#network') {
                loadNetworkStatus(true);  // Show loading when switching to network tab
            } else if (target === '#flash') {
                loadImages();
                loadDownloadedFiles();
            } else if (target === '#system') {
                loadSystemInfo();
            }
        });
    });
});


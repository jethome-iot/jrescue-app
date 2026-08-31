# AGENTS.md — jrescue-app

Guidance for AI agents (and humans) working in this repository. Read this before
making changes; it captures the non-obvious context and the safety invariants.

## What this is

`jrescue-app` is the recovery/rescue application for JetHome ARM (Amlogic) devices.
It runs **inside a minimal systemd Linux recovery image** that lives in a
hardware-write-protected slot on eMMC. It lets the user get online, download an OS
image from the JetHome REST API, and flash it to eMMC. Three frontends share one
`core/`.

## Platform context (why the app behaves the way it does)

- The recovery image is built by **buildroot** (`../buildroot-recovery-build`) as an
  initramfs inside `recovery.fit`: systemd + NetworkManager + RAUC + Python 3.14.
  The rootfs is a **RAM initramfs — nothing persists across reboot.**
- eMMC layout: `0–4 MiB` u-boot (env at `0x380000`), recovery **slot A @132 MiB**,
  **slot B @234 MiB** (102 MiB each; A/B for self-update), **main OS ext4 @336 MiB**.
- On a normal boot u-boot hardware-write-protects `0–336 MiB`. **Inside recovery that
  WP is OFF** (recovery is entered by holding the button + cold boot). So the app is
  the *only* guard against destroying the boot area / recovery slots when flashing —
  see **Flash safety** below.
- Boards: **J100 = D1**, **J200 = D2**, **J310 = D3**. Current target is **J100**
  (console + web; J100 has **no OLED hardware**). J310 later runs all three frontends
  from the same codebase.
- **OLED framebuffer format is auto-detected via ioctl, never hardcoded**
  (`oled-grid-application/display.py`): the vendor **5.15 `ssd1307fb`** driver is
  **1 bpp, LSB = leftmost pixel** → pack with PIL rawmode `'1;R'`; a mainline DRM
  **`ssd130x`** panel is **32 bpp XRGB**. Hardcoding 32bpp size onto the 1bpp buffer
  SIGBUSes; using PIL's default MSB-first `tobytes()` on `ssd1307fb` mirrors every
  8-px group.
- Sibling repos: `../buildroot-recovery-build` (recovery image + u-boot WP patches),
  `../armbian-build` (main OS), `../jethome-tools` (burn-image conversion).

## Architecture

```
core/                     shared modules (config, network, flash, download, usb, utils, translations)
console-application/      curses TUI            (main.py)
web-application/          stdlib http.server :8124 + static/ (vanilla ES6 + Bootstrap)
oled-grid-application/    /dev/fb0 + Pillow + evdev (main.py, display.py, input.py, menu.py, screens/)
```

- Frontends add `core/` to `sys.path` then import modules bare
  (`import config`, `from utils import run_command`, `from network import get_network_handler`).
- Core modules are independent (no cross-imports between frontends).
- Handler pattern: `get_network_handler()`, `FlashHandler`, `DownloadHandler`, `USBHandler`.

> ⚠️ **Config shadowing gotcha.** `web-application/` and `oled-grid-application/` each
> have their **own** `config.py`. Because each frontend dir is on `sys.path`, a bare
> `import config` can resolve to `core/config.py` **or** the frontend copy depending on
> import order. When you add or read a config value, check **all three** `config.py`
> files, and keep safety flags consistent across them (see below).

## Key current facts — don't regress these

- **Networking is NetworkManager via `nmcli`** (`core/network.py: NetworkManagerHandler`).
  There is **no** `wpa_cli` / `wpa_supplicant` / `udhcpc` / `dhclient` code — that whole
  layer was removed. NM runs its own DHCP.
- **Interfaces are auto-detected** (nmcli device enumeration). Do **not** hardcode
  `wlan0` / `eth0`. `config.WIFI_INTERFACE` / `ETHERNET_INTERFACE` are fallbacks only.
- **Board is auto-detected** in `core/config.py: detect_board()`, in priority order:
  env `JETHOME_DEVICE` / `JETHOME_PLATFORM` (manual override) → env `BOARD` /
  `BOARD_NAME` set by the recovery system (`BOARD=jethub-j100`) →
  `/proc/device-tree/model` (`"JetHome JetHub D1 (J100)"` → `d1` / `j100`) →
  fallback `d1` / `j100`. Do **not** hardcode `d2` / `j200`. Note: `BOARD` lives in
  the login-shell env only — systemd services won't see it, which is why the
  device-tree source must stay.
- **Downloads are JetHome-API-only.** `core/download.py` lists images from
  `/api/devices/{id}/info` (only entries with a `sdcard` image, newest first) and
  downloads by full URL. There is no static server / `AVAILABLE_IMAGES` /
  `DEFAULT_SERVER` path anymore; offline flashing goes through USB.
- **The console UI is curses-only, including waits and progress.** Menus/dialogs:
  `show_menu`, `show_horizontal_menu`, `input_dialog`, `confirm_action`; screens:
  `show_text_screen` (scrollable report), `show_wait_screen` (spinner around a
  blocking call, captures its stdout), `show_progress_screen` (bar; runs a
  `worker(progress)` in a thread), `show_confirm_screen` (info + NO/YES),
  `show_settings_screen` (menuconfig-style; declarative bool/choice/string/int
  items with get/set callables — runtime-only, resets on reboot). All in
  `core/utils.py`; Python `curses` is guaranteed via `select BR2_PACKAGE_PYTHON3_CURSES`.
  Esc = cancel. Do NOT add plain `print`/`press_enter` steps between curses screens —
  they flash and corrupt the flow; route long operations through
  `progress_cb` (supported by `download_file` and `flash_image`/`pv -n`) or a wait
  screen, and show captured output via `show_text_screen`.
- **Version lives in the git tag only.** `core/config.py: APP_VERSION = "dev"` in
  checkouts; the release workflow (`.github/workflows/release.yml`) stamps the
  `vX.Y.Z` tag into the tarball on release and updates the README version line.
  Never hand-edit APP_VERSION. Buildroot pins the consumed release via
  `JRESCUE_APP_VERSION` in `jrescue-app.mk`.
- **Python 3.14** in the image (3.7+ to run elsewhere). Standard library only, except
  **Pillow** and **python-evdev** (OLED). No build tools, no web frameworks.
- **No `__init__.py`** except `oled-grid-application/screens/` (the only real
  package). Do not re-add them — modules are imported bare via `sys.path`.
- **Buildroot side:** `package/jrescue-app/Config.in` `select`s all runtime deps
  (python3 + curses/ssl/xz/zlib, Pillow/freetype/dejavu, evdev, ncurses, pv, plus
  the Wi-Fi setup-AP stack: `HOSTAPD`(+`_DRIVER_NL80211`), `DNSMASQ`,
  `UTIL_LINUX_RFKILL`, `PYTHON_QRCODE`, `AVAHI`(+`_DAEMON`)) — defconfigs only set
  `BR2_PACKAGE_JRESCUE_APP=y`. NetworkManager + wpa_supplicant stay in the
  defconfig (system stack). See **Wi-Fi setup-AP provisioning** below.

## Flash safety (CRITICAL)

`core/flash.py` writes the OS image with a **masked write**: it skips
`config.RECOVERY_PROTECT_MB` (**336 MiB**) on **both** input and output
(`iflag=fullblock,skip_bytes` / `oflag=seek_bytes`), preserving u-boot, its env, and
both recovery slots. This is required because flashing runs **inside recovery where WP
is off** — a naïve whole-disk `dd` from sector 0 would overwrite the bootloader and
recovery slots and brick the recovery path itself.

- Never remove the offset from the `dd` pipeline (or the equivalent seek in the
  pure-Python lzma fallback).
- It assumes a **full-disk source image** built with `OFFSET=336` (image byte X → eMMC
  byte X). Set `RECOVERY_PROTECT_MB = 0` only for non-recovery targets (blank SD card).
- `SKIP_MOUNT_CHECK` must stay **`False`** in *every* `config.py` (shadowing — see above).

## Wi-Fi setup-AP provisioning

Router-style first run: with no ethernet the device raises its own Wi-Fi AP; a
phone joins it, a captive web portal collects the home Wi-Fi credentials, the
device joins that network and the AP is torn down. Ethernet present at boot → no
AP. On join failure → roll back to the AP.

**The radio is single — AP and STA are mutually exclusive (sequential).** The
phone WILL disconnect the instant the handoff starts; the portal warns and points
at `http://jethub.local:8124` (avahi/mDNS) for re-discovery. Scan the air BEFORE
raising the AP (cached to `/run/jrescue/wifi-scan.txt`). The AP is **hostapd-
driven, not `nmcli hotspot`**, because the RTL8821CU vendor driver brings
NM/wpa_supplicant APs up **OPEN**.

- **System** (buildroot overlay `usr/bin/` + `usr/lib/systemd/system/`):
  `jrescue-netdecide.service` (boot decision: ethernet-carrier or wifi-connected →
  nothing; else scan + `systemctl start jrescue-ap.service`; globally enabled),
  `jrescue-ap.service` (**no `[Install]`** — started only by the decider or the
  app), `jrescue-ap-up` (rfkill, `nmcli dev set managed no`, `10.42.0.1/24`,
  dnsmasq DHCP + captive `--address=/#/`, `exec hostapd`), `jrescue-ap-down`
  (ExecStopPost: flush IP, `managed yes`), `jrescue-eth-carrier`. The two halves
  talk via `systemctl` + `/run/jrescue/{ap-creds.txt,wifi-scan.txt}`.
- **App** `core/ap.py: APHandler` — `start_ap`/`stop_ap`, `provision(ssid,psk)`
  (stop AP → `nmcli --wait` connect → verify **IP AND pingable gateway** → on
  failure delete the profile + re-raise AP), `status()`. `web-application/main.py`
  runs a second captive HTTP server on **`10.42.0.1:80`** *only while the AP is up*
  (OS captive probes only hit :80) serving `static/portal.html`; endpoints
  `/api/provision/{networks,connect,status}` + `/api/network/ap/status`. Console
  `provision_ap()` and OLED `screens/network.py: ap_setup` (join-QR via
  python-qrcode) surface SSID/PSK/URL.

AP creds are the **static** `jethub`/`jethub123` (WPA2) for now — a per-device
`sha256(mac)` scheme was considered and deferred. The web API stays
unauthenticated; WPA2 + tearing the AP down on STA success bound the exposure.
`AP_*` constants live in `core/config.py` **and** are mirrored in
`oled-grid-application/config.py` (shadowing — `core/ap.py`'s `import config`
resolves to the OLED copy under the OLED app). **Hardware-unverified:** whether
RTL8821CU actually beacons WPA2 under hostapd (the whole premise — if it won't,
set `country_code`/`ieee80211d` in `jrescue-ap.conf`), and single-radio handoff
release timing.

## Conventions

- **Python:** `snake_case` functions/vars, `UPPER_SNAKE_CASE` constants, `PascalCase`
  classes. Module + function docstrings. Type hints where they help. Shell out through
  `utils.run_command([...], check=False)`. User-facing messages via
  `print_error/print_warning/print_info/print_success`.
- **JavaScript:** vanilla ES6, `camelCase`, `const` by default, `async`/`await` + Fetch,
  no build step.
- Comments explain **why**, not what. Match the surrounding code's style.

## Verifying changes

- Syntax: `python3 -m py_compile <files>` (or every `.py`).
- Import smoke test: `PYTHONPATH=core python3 -c "import config, utils, network, download, flash, usb"`.
- There is **no hardware here** — flash / nmcli / mount paths cannot be fully exercised
  locally. Reason carefully and call out any path you could not actually run.

## Known rough edges (as of this writing)

- **Web USB endpoints** (`api_handler`: `get_usb_status` / `post_usb_mount` /
  `get_usb_images`) call methods that don't exist on `USBHandler` **and** are not called
  by the bundled frontend — broken and vestigial. Decide fix-vs-remove before relying on them.
- **Two i18n systems:** `core/translations.py` and `oled-grid-application/language.py`
  duplicate each other.
- The web UI loads **Bootstrap from a CDN** → broken offline (recovery has no internet
  by default). Should be vendored into `static/`.
- Autostart units live in the buildroot overlay (`jrescue-console@.service` per-tty,
  `jrescue-web.service` global, `jrescue-oled.service` J310-only wants-symlink).
- **Wi-Fi setup-AP provisioning** is now **implemented** (see its section above) —
  not hardware-verified end to end. The web `portal.html` is self-contained (no
  CDN); the main `index.html` still loads Bootstrap from a CDN.
- A larger modernization (single daemon backend, RAUC-based recovery self-update,
  download checksum/signature verification — note: the fw API's `hash` field is a
  PGP signature) is planned but deferred.

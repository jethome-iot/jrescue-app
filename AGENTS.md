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
- **Board is auto-detected** in `core/config.py: detect_board()`:
  env `JETHOME_DEVICE` / `JETHOME_PLATFORM` override → `/proc/device-tree/model`
  (`"JetHome JetHub D1 (J100)"` → `d1` / `j100`; regex `Dx`→`dx`, `(Jxxx)`→`jxxx`) →
  fallback `d1` / `j100`. Do **not** hardcode `d2` / `j200`.
- **Python 3.14** in the image (3.7+ to run elsewhere). Standard library only, except
  **Pillow** and **python-evdev** (OLED). No build tools, no web frameworks.

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
- jrescue-app has **no systemd autostart unit** in the recovery image yet.
- A larger modernization (single daemon backend, RAUC-based recovery self-update,
  download checksum/signature verification) is planned but deferred.

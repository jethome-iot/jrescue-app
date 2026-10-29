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
- On a normal boot u-boot requests hardware write protection of `128–336 MiB`
  (rounded outward to the eMMC's WP-group boundaries). **Inside cold-boot recovery that
  WP is OFF** (recovery is entered by holding the button + cold boot). So the app is
  the *only* guard against overwriting the recovery slots when flashing —
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
- **Downloaded images are disposable RAM files** in `config.TEMP_DIR` (`/tmp/rescue`).
  Before every application download, unlink old `.img`/`.xz` images and `.partial`
  files; never reuse/resume the RAM cache. Failed/canceled downloads remove their
  partials. OLED/TUI discard on NO/Back/Home and after the write, before reboot
  dialogs; web confirmations discard through `DELETE /api/flash/file`.
  `core/image_cache.py` coordinates exclusive download/cleanup and shared flash
  readers with a nonblocking flock, across processes and frontends. Never delete
  an active source or mark a canceled download idle before its worker closes it.
  Cleanup unlinks files without reading/overwriting contents or following links;
  it does not recurse into directories or delete USB sources. Completed download
  identities keep repeated cleanup from deleting a replacement at the same path.
  Explicit generic download destinations outside the cache still support resume.
- **OLED and console start in English.** Language selection and reboot live in
  Settings, with no startup language screen or separate RAM image source.
  OLED opens the 2×2 main menu directly, without a Rescue/version splash or delay.
  OLED's four-item grid is Network / Flash / Info / Settings. Downloads use only the API's
  `images.sdcard` raw `.img`/`.img.xz` entry; burn and RAUC files are excluded.
- **OLED uses the approved 2×2 main grid with HAOS-style inner screens.**
  UP/DOWN/LEFT/RIGHT selects a card without wrapping across edges, ENTER opens
  it, and HOME resets selection to the first card. All four captions remain
  visible, in 13–14px regular type: the user dislikes bold main-menu captions.
  Selection uses a frame, with the same font weight in every card.
  The pixel-drawn icons are up to 21px wide with
  stronger strokes for the 0.96-inch screen. Settings uses one 15px cog with eight
  teeth and a clear center hole, replacing the old slider icon at the user's request.
  There is no main header or telemetry
  polling. **Do not restore CPU/RAM gauges:** Info shows the firmware only.
  All OLED text uses regular weight, including headers and selected rows.
  Inner screens use bundled Liberation Sans Regular; the keyboard uses bundled
  Liberation Sans Narrow Regular. Main captions keep system DejaVu Sans Condensed.
  Inner headers are 14px white on black with a thin underline, body text 14px,
  keyboard glyphs up to 15px, progress up to 19px. Body text was reduced by 1px
  at the user's request; preserve header, main-grid and keyboard sizes.
  Do not restore inverse headers.
  Wi-Fi SSID lists use 12px regular names; a wrapped name has 13px line pitch.
  Other inner lists, messages, progress and hold screens use 20px line pitch
  instead of the previous 25px; confirmation buttons sit 2px closer to the text.
  Keep list measuring and drawing in sync
  with `compact=True` through Menu, DisplayManager and OledRenderer.
  Text uses two compact rows, with glyphs centered inside confirmation frames.
  Pages update in one write with no slide transitions. **The main grid is fixed:**
  do not restyle it while changing inner screens.
- **The password editor is phone-style QWERTY**, with all three letter rows and
  a separate bottom control row visible at once. `keyboard_layout.py` shares state and geometry
  between navigation and rendering. Shift affects one letter; double Shift within
  0.5 seconds locks caps. `123`, `#+=` and `ABC` switch directly between layouts.
  Space, backspace and OK remain visible, with no vertical keyboard scrolling.
  The space key is 24px wide. Each special
  character appears exactly once across the number/symbol pages, with no quick
  duplicates among the controls. `None` slots are invisible and skipped by navigation;
  never insert repeated characters to fill the screen.
  The password field uses 14px of height and 15px Liberation Sans Narrow text,
  with a small key icon instead of a permanent `Pass:` label.
  Empty input contains no `Password` placeholder: only the key and a caret that
  blinks every 0.5 seconds. Keyboard input uses a timed wait so blinking remains
  on the UI thread; any real button press makes the caret visible again.
  The three letter rows remain 14px each, with unchanged character glyph sizes.
  The bottom control row is 8px high, with `123`/`ABC`, space and OK in their
  previous positions; its captions are 11px. `#+=`/`123` toggles symbol pages at
  the left of row three. All 32 punctuation characters occur once across those
  two pages. Navigation uses the same rectangles as the renderer.
  UP from the top keyboard row focuses the password; LEFT/RIGHT moves its
  insertion cursor and DOWN returns to the same selected key. ENTER while the
  field is focused returns to the keys; only the explicit OK key submits.
  Insert/delete acts at the cursor and preserves hidden suffixes and spaces.
  The field is unfilled; arrows indicate hidden input on either side, without
  changing the actual password. Selecting a secured SSID opens this editor
  directly, without an extra NO/YES step. Back/Home still cancel safely.
- **Visual changes require PNG and GIF previews first.** The user explicitly
  requested preview → user selection → implementation. Further visual changes
  need their previews chosen first. Keep the **02_haos** inner style, with no
  eMMC label on Flash and with the Wi-Fi password keyboard retained.
  The user approved restoring the 2×2 grid and requested more legible icons.
  Preview scripts are local development aids and are not part of the repository.
  **Keep only the latest generated previews** in `~/jrescue-oled-previews/`:
  the user explicitly requested deleting previous versions because they were
  hard to find. Update `02_haos/` in place and remove superseded generated
  variant folders; do not maintain duplicate historical copies to preserve old
  links. Keep the latest main files directly in the root as `01-menu.png`,
  `02-wifi-keyboard.png`, `03-demo.gif`, and `04-wifi.gif`, with a short README;
  `05-inner-menus.png` shows the current inner-screen typography.
  `06-wifi-networks.png` shows compact short and wrapped SSIDs in ENG/RUS.
  The user approved trying the four-row password-cursor preview; it is now
  implemented. The user rejected an eye button and a separate password overview:
  do not add them. Further symbol/footer variants still require preview selection.
  The user approved **02 Liberation Sans**; its plain titles and keyboard glyphs
  are implemented. Keep only the current design in the preview folder.
  Font binaries and their individual licenses live in `oled-grid-application/fonts/`
  and ship with app-only updates; do not depend on a board-side font installation.
- **OLED reboot requires a fresh continuous three-second center hold**, both
  in Settings and after flashing. The opening press and key autorepeat do not
  count; release rolls back, and Back/Left/Home cancel. Lost button state must
  never trigger a reboot. Flash/download confirmations still default to NO.
  Keep the nonblocking systemd
  reboot request so shutdown cannot wait on the application's own service.
  Blocking network/download/flash operations still draw only on the UI thread
  and use one joined worker through `Menu.run_working` / `run_progress`.
- **Network menus expose WiFi connect and Ethernet status only.** The setup AP
  is raised by systemd boot scripts; there is no Phone AP / manual AP action.
  Direct Wi-Fi connect still releases the single radio from an active AP.
  Ethernet status screens show interface, cable link and IP; omit MAC and speed.
- **The console UI is curses-only, including waits and progress.** Menus/dialogs:
  `show_menu`, `show_horizontal_menu`, `input_dialog`, `confirm_action`; screens:
  `show_text_screen` (scrollable report), `show_wait_screen` (spinner around a
  blocking call, captures its stdout), `show_progress_screen` (bar; runs a
  `worker(progress)` in a thread), `show_confirm_screen` (info + NO/YES),
  `show_settings_screen` (menuconfig-style; declarative bool/choice/string/int/action
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
  the Wi-Fi setup-AP stack: `HOSTAPD`(+`_DRIVER_NL80211`), `DNSMASQ`, `IW`,
  `UTIL_LINUX_RFKILL`, `AVAHI`(+`_DAEMON`)) — defconfigs only set
  `BR2_PACKAGE_JRESCUE_APP=y`. NetworkManager + wpa_supplicant stay in the
  defconfig (system stack). See **Wi-Fi setup-AP provisioning** below.

## Flash safety (CRITICAL)

`core/flash.py` uses `core/image_writer.py` for **every** write path (pv/xz
pipelines and Python fallback). It writes image byte X to eMMC byte X except
inside `[RECOVERY_PROTECT_START_MB, RECOVERY_PROTECT_END_MB)` = **[128, 336) MiB**.
The input bytes in that window are consumed, and the target is seeked over without
writing or truncating it. Both recovery slots stay intact; image data below
128 MiB (including MBR/GPT and any boot/environment data there) is replaced.

- Never bypass the protected writer. Cold-boot recovery does not arm hardware WP.
- The writer opens the existing target without truncation, locks it against other
  writers, checks short writes, and fsyncs before reporting success.
- Protection settings are mandatory: missing or invalid bounds must fail closed.
- It assumes a compatible **full-disk source image** with OS data beyond 336 MiB
  (image byte X → eMMC byte X). It does not convert SD MBR layouts into eMMC GPT.
  Set **both** bounds to 0 only for non-recovery targets (blank SD card).
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
  and OLED do not start the setup AP; its lifecycle starts in systemd, while the
  web portal handles the AP-to-STA handoff and rollback through those services.

AP creds are the **static** `jethub`/`jethub123` (WPA2) for now — a per-device
`sha256(mac)` scheme was considered and deferred. The web API stays
unauthenticated; WPA2 + tearing the AP down on STA success bound the exposure.
`AP_*` constants live in `core/config.py`; the web and OLED configs import the
shared settings so their shadowing copies also expose all safety and AP flags.

**Hardware-confirmed on J310:** RTL8821CU does beacon WPA2 under hostapd, the
phone joins, and the captive sheet pops the portal. (`country_code`/`ieee80211d`
in `jrescue-ap.conf` remain the first knob to try if a board won't beacon.)

- **AP+STA concurrency is impossible on J310** — the vendor driver is built with
  `CONFIG_CONCURRENT_MODE` commented out (`rtl8821CU/Makefile`), so
  `CONFIG_IFACE_NUMBER 1`, no iface-combinations are advertised and a second vif
  is refused. **Credentials therefore cannot be verified before the AP drops** —
  a WPA2 PSK is only proven by the 4-way handshake, which needs the radio as an
  STA. Check any other board with `iw list | sed -n '/interface combinations/,/^\t[^\t]/p'`;
  even where it works, every combination is `#channels <= 1`, so the AP would
  have to follow the home network's channel.
- What we do instead: `APHandler.preflight()` rejects everything checkable
  *without* the radio (empty/short/non-ASCII PSK, WPA-Enterprise, WEP, bad SSID)
  so hopeless attempts cost no disconnect; failures are classified into `ERR_*`
  codes (`classify_nmcli_error()`); and the outcome is persisted to
  `/run/jrescue/provision-state.json` so the portal explains the failure when the
  user rejoins the re-raised AP (`POST /api/provision/dismiss` clears it). Each
  frontend translates the `ERR_*` code — `core/ap.py` emits no user-facing prose.
- **`jrescue-ap.service` needs a high `StartLimitBurst`** (10): the app cycles the
  unit once per provisioning attempt, and a low burst limit makes systemd refuse
  to restart the AP — leaving the user with no UI at all. `_rollback()` also runs
  `systemctl reset-failed` before retrying, and re-raises the AP *before*
  recording the reason (else `start_ap()` overwrites it).
- `nmcli device wifi connect` does **not** scan — `_wait_ssid_visible()` must run
  a `--rescan yes` first, or a correct password fails with "No network with SSID
  found" because NM's cache is empty right after it re-owns the device.
- The scan cache is `SSID,SIGNAL,SECURITY,RSN-FLAGS,WPA-FLAGS,CHAN,FREQ`;
  `read_scan_cache()` still tolerates the old 3-field form.

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
- If the local development test harness is available, run
  `python3 -m unittest discover -s tests -v` (temporary files only; covers actual
  128/336 MiB boundaries and pv/xz/Python paths). The harness and preview tools
  stay local and are not committed at the user's request.
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

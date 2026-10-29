"""Reboot only after a fresh, continuous three-second center-button hold."""

import time

from language import t
from utils import run_command


def _request_reboot(menu):
    """Keep the existing systemd request safe from its own service shutdown."""
    menu.display.draw_hold_confirmation(t('reboot_title'), t('wait'), '', 100)
    code, _, error = run_command(['systemctl', '--no-block', 'reboot'], check=False)
    if code:
        print('Reboot request failed: {}'.format(error))
        return menu.show_message(t('error'), t('reboot_failed'))
    while True:
        time.sleep(1)


def reboot_system(menu):
    """Cancel safely on release, navigation or an unavailable button device."""
    try:
        result = menu.hold_to_confirm(t('reboot_title'), t('reboot_hold_center'),
                                      t('reboot_hold_time'), seconds=3.0)
    except (OSError, RuntimeError):
        return menu.show_message(t('error'), t('reboot_input_failed'))
    if result == -1:
        return -1
    if result is not True:
        return None
    return _request_reboot(menu)


def reboot_after_flash(menu):
    """Use the same hold guard after flashing; returning never requests a reboot."""
    return reboot_system(menu)

"""Request system power actions after a fresh, continuous three-second hold."""

import time

from language import t
from utils import run_command


def _request_reboot(menu):
    """Keep Settings and the post-flash reboot on the same command path."""
    return _request_power_action(menu, 'reboot')


def _request_power_action(menu, action):
    """Do not let systemd wait for the service making the shutdown request."""
    if action not in ('reboot', 'poweroff'):
        raise ValueError('Unsupported power action')
    menu.display.draw_hold_confirmation(t(action+'_title'), t(action+'_wait'), '', 100)
    code, _, error = run_command(['systemctl', '--no-block', action], check=False)
    if code:
        print('{} request failed: {}'.format(action, error))
        return menu.show_message(t('error'), t(action+'_failed'))
    while True:
        time.sleep(1)


def reboot_system(menu):
    """Cancel safely on release, navigation or an unavailable button device."""
    return _confirm_power_action(menu, 'reboot', _request_reboot)


def _confirm_power_action(menu, action, request):
    """Share the physical hold guard without accepting truthy menu results."""
    try:
        result = menu.hold_to_confirm(t(action+'_title'), t('reboot_hold_center'),
                                      t('reboot_hold_time'), seconds=3.0)
    except (OSError, RuntimeError):
        return menu.show_message(t('error'), t('reboot_input_failed'))
    if result == -1:
        return -1
    if result is not True:
        return None
    return request(menu)


def poweroff_system(menu):
    """Power off only on an explicitly completed hold; Back/Home cancel."""
    return _confirm_power_action(menu, 'poweroff', lambda menu: _request_power_action(menu, 'poweroff'))


def reboot_after_flash(menu):
    """Use the same hold guard after flashing; returning never requests a reboot."""
    return reboot_system(menu)

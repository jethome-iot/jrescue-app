"""Selected Info entries and one-screen RAM/eMMC usage for OLED."""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from language import t

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'core'))
from system_info import get_recovery_info


def info_items():
    """Use the same numbered, highlighted selection list as Network."""
    return [t('info_device'), t('info_memory'), t('info_versions')]


def info_details(info, selected):
    """Keep the model and both versions separate from the memory indicators."""
    if selected == 0:
        model = info.get('model') or '--'
        if model.startswith('JetHome '):
            model = model[len('JetHome '):]
        return {'title': t('info_device'), 'value': model}
    if selected == 2:
        return {'title': t('info_versions'), 'value': info.get('firmware') or '--',
                'detail': t('info_app_short')+': '+str(info.get('app_version') or '--')}
    raise ValueError('Info section has no text details')


def _memory_gauge(name, total, available, approximate=False, busy=False):
    """Use matched counters; unavailable data must not look like zero usage."""
    gauge = {'name': name, 'percent': None, 'unit': '',
             'amounts': t('info_writing') if busy else '--'}
    if (busy or type(total) is not int or type(available) is not int
            or total <= 0 or not 0 <= available <= total):
        return gauge
    used = total-available
    divisor, unit = next((scale, unit) for scale, unit in
                         ((1024**4, 'TiB'), (1024**3, 'GiB'), (1024**2, 'MiB'))
                         if total >= scale or unit == 'MiB')
    precision = 0 if total/divisor >= 100 else 1
    pair = '{:.{p}f}/{:.{p}f}'.format(used/divisor, total/divisor, p=precision)
    gauge.update(percent=100*used/total, unit=unit, amounts=('~' if approximate else '')+pair)
    return gauge


def memory_usage(info):
    """Pair filesystem usage with its own total, never the whole eMMC capacity."""
    emmc = info.get('emmc') or {}
    return [_memory_gauge('RAM', info.get('ram_total'), info.get('ram_available')),
            _memory_gauge('eMMC', emmc.get('filesystem_total'), emmc.get('free'),
                          emmc.get('approximate', False), emmc.get('busy', False))]


def show_system_info(menu):
    """Open highlighted entries; refresh details on Enter and preserve Back/Home."""
    selected = 0
    while True:
        choice = menu.select_from_list(t('info_title'), info_items(), show_index=False,
                                       show_counter=True, initial_index=selected)
        if choice is None or choice == -1:
            return choice
        selected = choice
        while True:
            info = menu.run_working(t('info_title'), t('wait'), get_recovery_info)
            if selected == 1:
                action = menu.show_memory_usage(memory_usage(info))
            else:
                action, _ = menu.show_info_pages([info_details(info, selected)])
            if action == -1:
                return -1
            if action is not True:
                break


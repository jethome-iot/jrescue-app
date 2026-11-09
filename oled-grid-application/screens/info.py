"""Device model, recovery build version and current Web links for OLED."""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from language import t

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'core'))
from system_info import get_recovery_info
from network import get_web_urls


def info_items():
    """Use the same numbered, highlighted selection list as Network."""
    return [t('info_device'), t('info_version'), t('info_web')]


def info_details(info, selected):
    """Show only the model and the recovery build's os-release version."""
    if selected == 0:
        model = info.get('model') or '--'
        if model.startswith('JetHome '):
            model = model[len('JetHome '):]
        return {'title': t('info_device'), 'value': model}
    if selected == 1:
        return {'title': t('info_version'), 'value': info.get('firmware') or '--'}
    raise ValueError('Info section has no text details')


def show_system_info(menu):
    """Read static facts once and show passive details without working animations."""
    selected = 0
    info = None
    while True:
        choice = menu.select_from_list(t('info_title'), info_items(), show_index=False,
                                       show_counter=True, initial_index=selected)
        if choice is None or choice == -1:
            return choice
        selected = choice
        if selected == 2:
            if menu.show_web_pages(web_pages(get_web_urls())) == -1:
                return -1
            continue
        if info is None:
            info = get_recovery_info()
        if menu.show_info_page(info_details(info, selected)) == -1:
            return -1


def web_pages(urls):
    """Keep the protocol and complete IP:port visible on separate rows."""
    pages = []
    for url in urls:
        scheme, _, address = url.partition('://')
        pages.append({'title': t('info_web'), 'value': scheme+'://', 'detail': address})
    return pages or [{'title': t('info_web'), 'value': t('info_web_no_address')}]


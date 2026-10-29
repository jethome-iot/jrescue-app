"""Runtime language selection and reboot actions for the OLED interface."""

import language
from language import t
from .reboot import reboot_system


def select_language(menu):
    """Change language without treating Back or Home as a selection."""
    languages = [('ENG', 'English'), ('RUS', 'Русский')]
    choice = menu.select_from_list(t('lang_title'),
                                   [label for _, label in languages],
                                   show_index=False, show_counter=False)
    if choice == -1:
        return -1
    if choice is not None:
        language.set_language(languages[choice][0])
    return None


def settings_menu(menu):
    """Rebuild labels after a language change; settings reset on reboot."""
    while True:
        current = 'EN' if language.get_language() == 'ENG' else 'RU'
        choice = menu.select_from_list(
            t('settings_title'),
            [t('settings_language') + ': ' + current, t('reboot_title')],
            show_index=False, show_counter=False)
        if choice is None or choice == -1:
            return choice
        if choice == 0:
            result = select_language(menu)
        else:
            result = reboot_system(menu)
        if result == -1:
            return -1

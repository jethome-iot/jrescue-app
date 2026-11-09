"""Runtime language/display settings and guarded system power actions."""

import language
from language import t
from idle import TIMEOUT_OPTIONS
from .reboot import reboot_system, poweroff_system


def settings_items(timeout):
    """Share translated menu labels with the approved screen previews."""
    current = 'EN' if language.get_language() == 'ENG' else 'RU'
    delay = {30: t('display_30_short'), 60: t('display_60_short'), 0: t('display_never')}[timeout]
    return [t('settings_language')+': '+current, t('reboot_title'),
            t('poweroff_title'), t('settings_display')+': '+delay]


def display_timeout_items():
    """Keep labels in the same order as the inactivity controller's options."""
    return [t('display_30_seconds'), t('display_1_minute'), t('display_never')]


def select_language(menu):
    """Change language without treating Back or Home as a selection."""
    languages = [('ENG', 'English'), ('RUS', 'Русский')]
    choice = menu.select_from_list(t('lang_title'),
                                   [label for _, label in languages],
                                   show_index=False, show_counter=True,
                                   initial_index=0 if language.get_language() == 'ENG' else 1)
    if choice == -1:
        return -1
    if choice is not None:
        language.set_language(languages[choice][0])
    return None


def select_display_timeout(menu):
    """Apply a new RAM-only timeout only when an option is selected."""
    choice = menu.select_from_list(t('display_title'), display_timeout_items(),
                                   show_index=False, show_counter=True,
                                   initial_index=TIMEOUT_OPTIONS.index(menu.idle.timeout))
    if choice == -1:
        return -1
    if choice is not None:
        menu.idle.set_timeout(TIMEOUT_OPTIONS[choice])
    return None


def settings_menu(menu):
    """Keep the selected action while rebuilding language and timeout labels."""
    selected = 0
    actions = (select_language, reboot_system, poweroff_system, select_display_timeout)
    while True:
        choice = menu.select_from_list(
            t('settings_title'), settings_items(menu.idle.timeout),
            show_index=False, show_counter=True, initial_index=selected)
        if choice is None or choice == -1:
            return choice
        selected = choice
        result = actions[choice](menu)
        if result == -1:
            return -1

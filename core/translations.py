"""
Localization/Translation system for Console Application

NOTE: This module is named 'translations.py' (not 'locale.py') to avoid
conflicts with Python's standard 'locale' module.
"""

# Current language (default: English)
CURRENT_LANGUAGE = "en"

# Translation dictionary
TRANSLATIONS = {
    "en": {
        # Language selection
        "select_language": "Select Language / Выберите язык",
        "language_english": "English",
        "language_russian": "Русский",

        # Application
        "app_title": "RESCUE CONSOLE APPLICATION",
        "app_subtitle": "eMMC Image Flasher for Rescue Systems",

        # Main menu
        "main_menu": "MAIN MENU",
        "network_setup": "Network Setup (WiFi/Ethernet)",
        "flash_image": "Flash Image to eMMC",
        "system_info": "System Information",

        # Network menu
        "network_menu": "NETWORK SETUP",
        "network_options": "Network Options",
        "back_to_main": "← Back to Main Menu",
        "connect_wifi": "Connect to WiFi",
        "test_connection": "Test Internet Connection",
        "status_connected": "Connected",
        "status_not_connected": "Status: Not connected",
        "ip_address": "IP Address",
        "wifi_network": "WiFi Network",

        # WiFi setup
        "wifi_setup": "WiFi SETUP",
        "scanning_networks": "Scanning for networks...",
        "no_networks": "No WiFi networks found",
        "make_sure_wifi": "Make sure WiFi adapter is enabled",
        "found_networks": "Found {count} network(s)",
        "use_arrows": "Use ↑↓ arrow keys to navigate, Enter to select",
        "select_network": "Select WiFi Network",
        "selected": "Selected",
        "enter_password": "Enter password: ",
        "password_empty": "Password cannot be empty",
        "wifi_connected": "WiFi connection established!",
        "wifi_failed": "Failed to connect to WiFi",
        "back_cancel": "← Back / Cancel",

        # Flash menu
        "flash_menu": "FLASH IMAGE TO eMMC",
        "select_source": "Select image source:",
        "source_http": "Download from HTTP/JetHome API",
        "source_usb": "Load from USB drive",
        "source_ram": "Flash from Downloaded",
        "select_image_source": "Select Image Source",
        "manage_ram": "MANAGE IMAGES IN RAM",
        "images_in_ram": "Images in RAM",
        "no_images_ram": "No images found in RAM",
        "download_first": "Download an image first using 'Download from HTTP' option",
        "found_images_ram": "Found {count} image(s) in RAM:",
        "select_image_manage": "Select an image to manage:",
        "manage_colon": "MANAGE: {filename}",
        "select_action": "Select Action",
        "back_to_image_list": "← Back to image list",
        "action_flash": "Flash this image to eMMC",
        "action_delete": "Delete this image from Downloaded",
        "confirm_delete": "Delete {filename}?",
        "will_free": "This will free {size} of RAM",
        "confirm_deletion": "Confirm Deletion",
        "yes_delete": "Yes, delete this image",
        "deleted": "Deleted: {filename}",
        "freed": "Freed {size} of RAM",
        "failed_delete": "Failed to delete: {error}",
        "proceed_with_flashing": "Proceed with flashing?",
        "confirm_flash_operation": "CONFIRM FLASH OPERATION",
        "image_to_flash": "Image to flash",
        "size": "Size",
        "compressed": "compressed",
        "all_data_erased": "All data on {device} will be ERASED!",
        "cannot_be_undone": "This operation cannot be undone!",

        # Download
        "download_http": "DOWNLOAD IMAGE VIA HTTP",
        "checking_network": "Checking network connection...",
        "no_internet": "No internet connection",
        "configure_network": "Please configure network first",
        "low_disk_space": "Low disk space: {space} available",
        "need_space": "Need at least {space} for safe operation",
        "download_success": "Image downloaded successfully!",
        "download_location": "Location",
        "download_cancelled": "Download cancelled or failed",

        # USB
        "load_usb": "LOAD IMAGE FROM USB",
        "no_usb_selected": "No USB device selected",
        "already_mounted": "Device already mounted at",
        "mount_failed": "Failed to mount USB device",
        "no_images_usb": "No image files found on USB",
        "found_images": "Found {count} image file(s) on USB",
        "select_image_usb": "Select Image from USB",
        "do_not_remove": "DO NOT REMOVE USB drive until flashing is complete!",

        # Flash
        "flash_downloaded": "FLASH DOWNLOADED IMAGE",
        "select_target": "Select target device for flashing:",
        "target_device": "Target device",
        "flashing_success": "Flashing completed successfully!",
        "flashing_failed": "Flashing failed",
        "reboot_now": "Reboot now",
        "return_menu": "Return to menu",
        "rebooting": "Rebooting...",
        "safe_remove": "You can now safely remove USB drive",

        # System info
        "system_information": "SYSTEM INFORMATION",
        "hostname": "Hostname",
        "kernel": "Kernel",
        "architecture": "Architecture",
        "memory": "Memory",
        "free_space": "Free Space",
        "device": "Device",
        "platform": "Platform",
        "emmc_device": "eMMC Device",
        "temp_dir": "Temp Dir",
        "usb_mount": "USB Mount",
        "server_url": "Server URL",
        "network": "Network",

        # Common
        "press_enter": "Press Enter to continue...",
        "settings": "Settings",
        "error": "ERROR",
        "warning": "WARNING",
        "info": "INFO",
        "ok": "OK",
        "cancel": "Cancel",
        "yes": "Yes",
        "no": "No",
        "flash": "Flash",
    },

    "ru": {
        # Language selection
        "select_language": "Select Language / Выберите язык",
        "language_english": "English",
        "language_russian": "Русский",

        # Application
        "app_title": "КОНСОЛЬНОЕ ПРИЛОЖЕНИЕ RESCUE",
        "app_subtitle": "Запись образов на eMMC для Rescue-систем",

        # Main menu
        "main_menu": "ГЛАВНОЕ МЕНЮ",
        "network_setup": "Настройка сети (WiFi/Ethernet)",
        "flash_image": "Записать образ на eMMC",
        "system_info": "Информация о системе",

        # Network menu
        "network_menu": "НАСТРОЙКА СЕТИ",
        "network_options": "Параметры сети",
        "back_to_main": "← Назад в главное меню",
        "connect_wifi": "Подключиться к WiFi",
        "test_connection": "Проверить интернет-соединение",
        "status_connected": "Подключено",
        "status_not_connected": "Статус: Не подключено",
        "ip_address": "IP-адрес",
        "wifi_network": "WiFi сеть",

        # WiFi setup
        "wifi_setup": "НАСТРОЙКА WiFi",
        "scanning_networks": "Поиск сетей...",
        "no_networks": "WiFi сети не найдены",
        "make_sure_wifi": "Убедитесь, что WiFi адаптер включен",
        "found_networks": "Найдено сетей: {count}",
        "use_arrows": "Используйте стрелки ↑↓ для навигации, Enter для выбора",
        "select_network": "Выберите WiFi сеть",
        "selected": "Выбрано",
        "enter_password": "Введите пароль: ",
        "password_empty": "Пароль не может быть пустым",
        "wifi_connected": "WiFi соединение установлено!",
        "wifi_failed": "Не удалось подключиться к WiFi",
        "back_cancel": "← Назад / Отмена",

        # Flash menu
        "flash_menu": "ЗАПИСЬ ОБРАЗА НА eMMC",
        "select_source": "Выберите источник образа:",
        "source_http": "Скачать по HTTP/JetHome API",
        "source_usb": "Загрузить с USB накопителя",
        "source_ram": "Записать из RAM (скачанные образы)",
        "select_image_source": "Выберите источник образа",
        "manage_ram": "УПРАВЛЕНИЕ ОБРАЗАМИ В RAM",
        "images_in_ram": "Образы в RAM",
        "no_images_ram": "Образы в RAM не найдены",
        "download_first": "Сначала скачайте образ через 'Скачать по HTTP'",
        "found_images_ram": "Найдено образов в RAM: {count}",
        "select_image_manage": "Выберите образ для управления:",
        "manage_colon": "УПРАВЛЕНИЕ: {filename}",
        "select_action": "Выберите действие",
        "back_to_image_list": "← Назад к списку образов",
        "action_flash": "Записать этот образ на eMMC",
        "action_delete": "Удалить этот образ из RAM",
        "confirm_delete": "Удалить {filename}?",
        "will_free": "Это освободит {size} RAM",
        "confirm_deletion": "Подтверждение удаления",
        "yes_delete": "Да, удалить этот образ",
        "deleted": "Удалено: {filename}",
        "freed": "Освобождено {size} RAM",
        "failed_delete": "Не удалось удалить: {error}",
        "proceed_with_flashing": "Продолжить запись?",
        "confirm_flash_operation": "ПОДТВЕРЖДЕНИЕ ЗАПИСИ",
        "image_to_flash": "Образ для записи",
        "size": "Размер",
        "compressed": "сжатый",
        "all_data_erased": "Все данные на {device} будут СТЁРТЫ!",
        "cannot_be_undone": "Эта операция необратима!",

        # Download
        "download_http": "СКАЧИВАНИЕ ОБРАЗА ПО HTTP",
        "checking_network": "Проверка сетевого подключения...",
        "no_internet": "Нет интернет-соединения",
        "configure_network": "Пожалуйста, сначала настройте сеть",
        "low_disk_space": "Мало места на диске: {space} доступно",
        "need_space": "Требуется минимум {space} для безопасной работы",
        "download_success": "Образ успешно скачан!",
        "download_location": "Расположение",
        "download_cancelled": "Скачивание отменено или не удалось",

        # USB
        "load_usb": "ЗАГРУЗКА ОБРАЗА С USB",
        "no_usb_selected": "USB устройство не выбрано",
        "already_mounted": "Устройство уже смонтировано в",
        "mount_failed": "Не удалось смонтировать USB устройство",
        "no_images_usb": "Файлы образов на USB не найдены",
        "found_images": "Найдено файлов образов на USB: {count}",
        "select_image_usb": "Выберите образ с USB",
        "do_not_remove": "НЕ ИЗВЛЕКАЙТЕ USB накопитель до завершения записи!",

        # Flash
        "flash_downloaded": "ЗАПИСЬ СКАЧАННОГО ОБРАЗА",
        "select_target": "Выберите целевое устройство для записи:",
        "target_device": "Целевое устройство",
        "flashing_success": "Запись успешно завершена!",
        "flashing_failed": "Запись не удалась",
        "reboot_now": "Перезагрузить сейчас",
        "return_menu": "Вернуться в меню",
        "rebooting": "Перезагрузка...",
        "safe_remove": "Теперь можно безопасно извлечь USB накопитель",

        # System info
        "system_information": "ИНФОРМАЦИЯ О СИСТЕМЕ",
        "hostname": "Имя хоста",
        "kernel": "Ядро",
        "architecture": "Архитектура",
        "memory": "Память",
        "free_space": "Свободное место",
        "device": "Устройство",
        "platform": "Платформа",
        "emmc_device": "Устройство eMMC",
        "temp_dir": "Временная папка",
        "usb_mount": "Точка монтирования USB",
        "server_url": "URL сервера",
        "network": "Сеть",

        # Common
        "press_enter": "Нажмите Enter для продолжения...",
        "settings": "Настройки",
        "error": "ОШИБКА",
        "warning": "ПРЕДУПРЕЖДЕНИЕ",
        "info": "ИНФОРМАЦИЯ",
        "ok": "ОК",
        "cancel": "Отмена",
        "yes": "Да",
        "no": "Нет",
        "flash": "Записать",
    }
}


def set_language(lang_code: str):
    """Set current language"""
    global CURRENT_LANGUAGE
    if lang_code in TRANSLATIONS:
        CURRENT_LANGUAGE = lang_code


def get_language():
    """Get current language code"""
    return CURRENT_LANGUAGE


def t(key: str, **kwargs) -> str:
    """
    Translate a key to current language

    Args:
        key: Translation key
        **kwargs: Format arguments for string interpolation

    Returns:
        Translated string
    """
    translation = TRANSLATIONS.get(CURRENT_LANGUAGE, {}).get(key, key)

    # Handle string formatting
    if kwargs:
        try:
            translation = translation.format(**kwargs)
        except (KeyError, ValueError):
            pass

    return translation


def select_language_interactive():
    """
    Interactive language selection using curses
    Returns selected language code
    """
    try:
        import curses

        def _select_lang(stdscr):
            curses.curs_set(0)
            stdscr.erase()

            # Initialize colors
            if curses.has_colors():
                curses.start_color()
                curses.init_pair(1, curses.COLOR_BLACK, curses.COLOR_WHITE)  # Selected
                curses.init_pair(2, curses.COLOR_CYAN, curses.COLOR_BLACK)   # Title

            languages = [
                ("en", t("language_english")),
                ("ru", t("language_russian"))
            ]
            current = 0

            while True:
                stdscr.erase()
                h, w = stdscr.getmaxyx()

                # Title
                title = t("select_language")
                title_width = len(title) + 4
                start_x = max(0, (w - title_width - 2) // 2)

                if curses.has_colors():
                    stdscr.attron(curses.color_pair(2) | curses.A_BOLD)

                stdscr.addstr(1, start_x, "╔" + "═" * title_width + "╗")
                stdscr.addstr(2, start_x, "║ " + title.center(title_width - 2) + " ║")
                stdscr.addstr(3, start_x, "╚" + "═" * title_width + "╝")

                if curses.has_colors():
                    stdscr.attroff(curses.color_pair(2) | curses.A_BOLD)

                # Options
                start_y = 6
                for idx, (code, name) in enumerate(languages):
                    y = start_y + (idx * 4)

                    if idx == current:
                        text = f" ► {name} "
                        border = "─" * len(text)
                        start_x = max(2, (w - len(text)) // 2)

                        if curses.has_colors():
                            stdscr.attron(curses.color_pair(1) | curses.A_BOLD | curses.A_REVERSE)

                        if y < h - 1:
                            stdscr.addstr(y, start_x, border)
                        if y + 1 < h - 1:
                            stdscr.addstr(y + 1, start_x, text)
                        if y + 2 < h - 1:
                            stdscr.addstr(y + 2, start_x, border)

                        if curses.has_colors():
                            stdscr.attroff(curses.color_pair(1) | curses.A_BOLD | curses.A_REVERSE)
                    else:
                        text = f"   {name}"
                        start_x = max(2, (w - len(text)) // 2)
                        if y + 1 < h - 1:
                            stdscr.addstr(y + 1, start_x, text)

                # Instructions
                instr = "↑↓: Navigate  |  Enter: Select"
                if len(instr) < w - 4:
                    instr_x = max(2, (w - len(instr)) // 2)
                    if h - 2 >= 0:
                        stdscr.addstr(h - 2, instr_x, instr)

                stdscr.refresh()

                # Input
                key = stdscr.getch()

                if key == curses.KEY_UP and current > 0:
                    current -= 1
                elif key == curses.KEY_DOWN and current < len(languages) - 1:
                    current += 1
                elif key == curses.KEY_ENTER or key in [10, 13]:
                    return languages[current][0]
                elif key == ord('1'):
                    return languages[0][0]
                elif key == ord('2'):
                    return languages[1][0]

        return curses.wrapper(_select_lang)

    except Exception:
        # Fallback to simple menu
        print("\n" + "=" * 60)
        print(t("select_language").center(60))
        print("=" * 60 + "\n")
        print(f"  1. {t('language_english')}")
        print(f"  2. {t('language_russian')}")
        print()

        try:
            choice = input("Choice / Выбор: ").strip()
            if choice == "2":
                return "ru"
            return "en"
        except (KeyboardInterrupt, EOFError):
            return "en"


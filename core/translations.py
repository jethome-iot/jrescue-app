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
        "provision_ap": "Setup via phone (Wi-Fi AP)",
        "ap_on": "AP ON",
        "ap_starting": "Starting access point...",
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

        # Console screens / dialogs / status
        "nm_unavailable": "NetworkManager not available.",
        "nm_unavailable_hint": "nmcli was not found — the recovery image must ship NetworkManager.",
        "testing_conn": "Testing connection...",
        "collecting_info": "Collecting system info...",
        "no_output": "No output",
        "wifi_pass_for": "WiFi password for {ssid}",
        "connecting_to": "Connecting to {ssid}...",
        "connected_to": "✓ Connected to {ssid}",
        "connect_failed_to": "✗ Failed to connect to {ssid}",
        "ap_start_failed": "Failed to start the access point.",
        "ap_on_line": "Wi-Fi setup access point is ON.",
        "ap_on_phone": "On your phone:",
        "ap_step_join": "1. Join Wi-Fi network:  {ssid}",
        "ap_step_pass": "   Password:            {psk}",
        "ap_step_open": "2. Open in a browser:   {url}",
        "ap_body1": "There, choose your home Wi-Fi and enter its",
        "ap_body2": "password. This device joins it and the setup",
        "ap_body3": "network closes — your phone disconnects (that",
        "ap_body4": "is normal). Reconnect it to your home Wi-Fi",
        "ap_body5": "and open",
        "title_download": "Download",
        "title_flashing": "Flashing eMMC",
        "flashing_failed_body": "Flashing failed.",
        "mounting_dev": "Mounting {device}...",
        "mount_usb_failed": "Failed to mount USB device.",
        "scanning_images": "Scanning for images...",
        "no_images_on_usb": "No image files found on USB.",
        "ram_dir_missing": "RAM directory not found: {dir}",
        "no_images_ram_dir": "No images found in RAM ({dir}).",
        "download_first_hint": "Download an image first using the API download option.",
        "back_to_flash_menu": "← Back to Flash Menu",
        "deleting_frees_ram": "Deleting frees RAM for new downloads.",
        "low_ram_space": "Low RAM space: {space} available.",
        "need_ram_space": "Need at least {space} for safe operation.",
        "version": "Version",
        "web_ui": "Web UI",
        "web_ui_running": "Running",
        "web_ui_stopped": "Not running (port {port})",
        "access_url": "Access URL",
        "net_connected": "Connected ({iface})",
        "net_not_connected": "Not connected",
        # Curses chrome (bottom hint bars)
        "hint_menu": "↑↓ move   Enter select   1-9 jump   Esc back",
        "hint_hmenu": "←→ move   Enter select   Esc back",
        "hint_input": "Tab/↑↓ focus   Enter select   Esc cancel",
        "hint_text_scroll": "↑↓ PgUp/PgDn scroll   Enter/Esc — back",
        "hint_text": "Enter/Esc — back",
        "hint_settings": "↑↓ move   Space/Enter change   ? help   Esc back   (resets on reboot)",
        "hint_settings_str": "Enter save   Esc cancel   Backspace delete",
        "hint_anykey": "any key — back",
        "hint_hchoice": "←→ move   Enter select   Esc cancel",
        "hint_settings_choice": "↑↓ move   Enter select   Esc cancel",
        "confirm_title": "Confirm",

        # Common
        "press_enter": "Press Enter to continue...",
        "settings": "Settings",
        "shell": "Shell (advanced)",
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
        "provision_ap": "Настройка со смартфона (Wi-Fi AP)",
        "ap_on": "AP ВКЛ",
        "ap_starting": "Запуск точки доступа...",
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

        # Console screens / dialogs / status
        "nm_unavailable": "NetworkManager недоступен.",
        "nm_unavailable_hint": "nmcli не найден — в recovery-образе должен быть NetworkManager.",
        "testing_conn": "Проверка соединения...",
        "collecting_info": "Сбор информации о системе...",
        "no_output": "Нет вывода",
        "wifi_pass_for": "Пароль WiFi для {ssid}",
        "connecting_to": "Подключение к {ssid}...",
        "connected_to": "✓ Подключено к {ssid}",
        "connect_failed_to": "✗ Не удалось подключиться к {ssid}",
        "ap_start_failed": "Не удалось запустить точку доступа.",
        "ap_on_line": "Точка доступа для настройки включена.",
        "ap_on_phone": "На телефоне:",
        "ap_step_join": "1. Подключитесь к сети:  {ssid}",
        "ap_step_pass": "   Пароль:              {psk}",
        "ap_step_open": "2. Откройте в браузере:  {url}",
        "ap_body1": "Там выберите домашнюю сеть Wi-Fi и введите",
        "ap_body2": "её пароль. Устройство подключится к ней, а",
        "ap_body3": "сеть настройки закроется — телефон отключится",
        "ap_body4": "(это нормально). Переподключите его к домашней",
        "ap_body5": "сети Wi-Fi и откройте",
        "title_download": "Загрузка",
        "title_flashing": "Запись на eMMC",
        "flashing_failed_body": "Запись не удалась.",
        "mounting_dev": "Монтирование {device}...",
        "mount_usb_failed": "Не удалось смонтировать USB.",
        "scanning_images": "Поиск образов...",
        "no_images_on_usb": "Образы на USB не найдены.",
        "ram_dir_missing": "Папка RAM не найдена: {dir}",
        "no_images_ram_dir": "Образы в RAM не найдены ({dir}).",
        "download_first_hint": "Сначала скачайте образ через загрузку по API.",
        "back_to_flash_menu": "← Назад в меню записи",
        "deleting_frees_ram": "Удаление освобождает RAM для новых загрузок.",
        "low_ram_space": "Мало RAM: доступно {space}.",
        "need_ram_space": "Нужно минимум {space} для безопасной работы.",
        "version": "Версия",
        "web_ui": "Веб-интерфейс",
        "web_ui_running": "Работает",
        "web_ui_stopped": "Не запущен (порт {port})",
        "access_url": "Адрес",
        "net_connected": "Подключено ({iface})",
        "net_not_connected": "Не подключено",
        # Curses chrome (bottom hint bars)
        "hint_menu": "↑↓ выбор   Enter выбрать   1-9 переход   Esc назад",
        "hint_hmenu": "←→ выбор   Enter выбрать   Esc назад",
        "hint_input": "Tab/↑↓ фокус   Enter выбрать   Esc отмена",
        "hint_text_scroll": "↑↓ PgUp/PgDn прокрутка   Enter/Esc — назад",
        "hint_text": "Enter/Esc — назад",
        "hint_settings": "↑↓ выбор   Space/Enter изменить   ? справка   Esc назад   (сброс при перезагрузке)",
        "hint_settings_str": "Enter сохранить   Esc отмена   Backspace стереть",
        "hint_anykey": "любая клавиша — назад",
        "hint_hchoice": "←→ выбор   Enter выбрать   Esc отмена",
        "hint_settings_choice": "↑↓ выбор   Enter выбрать   Esc отмена",
        "confirm_title": "Подтверждение",

        # Common
        "press_enter": "Нажмите Enter для продолжения...",
        "settings": "Настройки",
        "shell": "Терминал (shell)",
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
    Interactive language selection (delegates to the shared menuconfig-style
    menu in utils so the very first screen matches the rest of the UI).
    Returns selected language code.
    """
    try:
        from utils import show_menu

        languages = [
            ("ru", t("language_russian")),
            ("en", t("language_english")),
        ]
        choice = show_menu(t("select_language"), [name for _, name in languages])
        if 1 <= choice <= len(languages):
            return languages[choice - 1][0]
        return "ru"

    except Exception:
        # Fallback to simple menu
        print("\n" + "=" * 60)
        print(t("select_language").center(60))
        print("=" * 60 + "\n")
        print(f"  1. {t('language_russian')}")
        print(f"  2. {t('language_english')}")
        print()

        try:
            choice = input("Choice / Выбор: ").strip()
            if choice == "2":
                return "en"
            return "ru"
        except (KeyboardInterrupt, EOFError):
            return "ru"

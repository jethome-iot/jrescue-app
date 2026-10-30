"""
Language/Translation Support for OLED Application
Supports Russian and English
"""

# Language changes are runtime-only; every boot starts in English.
current_language = "ENG"

# Translation dictionary
TRANSLATIONS = {
    "RUS": {
        # Main menu
        "main_network": "Сеть",
        "main_flash": "Запись",
        "main_info": "Инфо",
        "main_settings": "Настр.",
        "main_images": "Образы",
        "main_no_network": "Нет сети",
        "keyboard_password": "Пароль",
        "settings_title": "Настройки",
        "settings_language": "Язык",

        # Network menu
        "net_title": "Сеть",
        "net_test": "Статус",
        "net_wifi": "Подключить WiFi",
        "net_ethernet": "Статус Ethernet",
        "eth_missing": "Нет Ethernet",
        "eth_link": "Кабель",
        "eth_up": "Подключён",
        "eth_down": "Отключён",
        "net_ip": "IP адрес",
        "net_back": "Назад",
        "ap_start": "Запуск AP",
        "ap_fail": "AP не создан",
        "ap_stopping": "Остановка AP",

        # WiFi menu
        "wifi_title": "WiFi",
        "wifi_scan": "Поиск сетей",
        "wifi_manual": "Вручную",
        "wifi_disconnect": "Отключить",
        "wifi_back": "Назад",
        "wifi_scanning": "Поиск...",
        "wifi_found": "Найдено",
        "wifi_select": "Выберите сеть",
        "wifi_password": "Пароль WiFi",
        "wifi_connecting": "Подключение",
        "wifi_connected": "Подключено",
        "wifi_failed": "Ошибка WiFi",
        "wifi_wrong_password": "Неверный пароль",
        "wifi_bad_password": "Формат пароля",
        "wifi_auth_failed": "Ошибка входа",
        "wifi_not_found": "Сеть не найдена",
        "wifi_no_dhcp": "Нет IP-адреса",
        "wifi_timeout": "Время истекло",
        "wifi_radio_busy": "WiFi недоступен",
        "wifi_no_adapter": "Нет WiFi-адапт.",
        "wifi_unavailable": "Сбой WiFi",
        "wifi_connect_failed": "Нет подключения",
        "wifi_no_networks": "Нет сетей",
        "wifi_enter_again": "Введи заново",
        "wifi_check_password": "Проверь пароль",
        "wifi_scan_again": "Повтори поиск",
        "wifi_check_router": "Проверьте сеть",
        "wifi_check_adapter": "Проверьте WiFi",
        "wifi_try_again": "Повтори попытку",
        "wifi_restart": "Перезапустите",

        # Ethernet menu
        "eth_title": "Ethernet",
        "eth_dhcp": "DHCP",
        "eth_static": "Статич. IP",
        "eth_status": "Статус",
        "eth_back": "Назад",

        # Flash menu
        "flash_title": "Запись",
        "flash_api": "Образы jethome",
        "flash_usb": "С USB",
        "flash_list": "Список",
        "flash_back": "Назад",
        "flash_select": "Выбор образа",
        "flash_confirm_download": "Скачать?",
        "flash_downloaded": "Скачан",
        "flash_confirm_flash": "Записать?",
        "flash_warning": "Стереть всё?",
        "flash_downloading": "Скачивание",
        "flash_confirm": "Записать?",
        "flash_progress": "Запись",
        "flash_done": "Готово",
        "flash_complete": "Запись завершена",
        "flash_error": "Ошибка",
        "flash_failed": "Ошибка записи",
        "download_failed": "Ошибка скачивания",
        "download_cancelling": "Отмена",
        "no_images": "Нет образов",
        "size": "Размер",
        "usb_title": "USB",
        "usb_detecting": "Поиск...",
        "usb_mounting": "Монтирование",
        "usb_scanning": "Сканирование",
        "usb_images": "Образы USB",
        "usb_not_found": "USB не найден",
        "usb_wait": "Ждать USB?",
        "usb_waiting": "Ожидание USB",
        "usb_no_device": "Нет USB",
        "usb_mount_failed": "Монтирование неудачно",
        "usb_no_images": "Нет образов на USB",
        "usb_safe_remove": "Можно извлечь USB",

        "info": "Инфо",

        # Reboot menu
        "reboot_title": "Перезагрузка",
        "reboot_short": "Рестарт",
        "reboot_now": "Сейчас",
        "reboot_cancel": "Отмена",
        "reboot_confirm": "Перезагрузить?",
        "reboot_wait": "Перезагрузка...",
        "reboot_hold_center": "Удержи",
        "reboot_hold_time": "центр 3с",
        "reboot_input_failed": "Нет связи с кнопками",
        "reboot_failed": "Ошибка перезагрузки",

        # Info screen
        "info_title": "Информация",

        # Common
        "yes": "Да",
        "no": "Нет",
        "ok": "ОК",
        "cancel": "Отмена",
        "back": "Назад",
        "select": "Выбрать",
        "wait": "Ждите...",
        "error": "Ошибка",
        "success": "Успешно",

        # Language selection
        "lang_title": "Язык",
        "lang_russian": "Русский",
        "lang_english": "English",
    },

    "ENG": {
        # Main menu
        "main_network": "Network",
        "main_flash": "Flash",
        "main_info": "Info",
        "main_settings": "Settings",
        "main_images": "Images",
        "main_no_network": "No network",
        "keyboard_password": "Password",
        "settings_title": "Settings",
        "settings_language": "Language",

        # Network menu
        "net_title": "Network",
        "net_test": "Status",
        "net_wifi": "WiFi connect",
        "net_ethernet": "Ethernet status",
        "eth_missing": "No Ethernet",
        "eth_link": "Link",
        "eth_up": "Up",
        "eth_down": "Down",
        "net_ip": "IP Address",
        "net_back": "Back",
        "ap_start": "Starting AP",
        "ap_fail": "AP failed",
        "ap_stopping": "Stopping AP",

        # WiFi menu
        "wifi_title": "WiFi",
        "wifi_scan": "Scan Networks",
        "wifi_manual": "Manual",
        "wifi_disconnect": "Disconnect",
        "wifi_back": "Back",
        "wifi_scanning": "Scanning...",
        "wifi_found": "Found",
        "wifi_select": "Select Network",
        "wifi_password": "WiFi Password",
        "wifi_connecting": "Connecting",
        "wifi_connected": "Connected",
        "wifi_failed": "WiFi error",
        "wifi_wrong_password": "Wrong password",
        "wifi_bad_password": "Invalid password",
        "wifi_auth_failed": "Auth failed",
        "wifi_not_found": "Network not found",
        "wifi_no_dhcp": "No IP address",
        "wifi_timeout": "Timed out",
        "wifi_radio_busy": "WiFi unavailable",
        "wifi_no_adapter": "No WiFi adapter",
        "wifi_unavailable": "WiFi service off",
        "wifi_connect_failed": "Connection failed",
        "wifi_no_networks": "No networks found",
        "wifi_enter_again": "Enter again",
        "wifi_check_password": "Check password",
        "wifi_scan_again": "Scan again",
        "wifi_check_router": "Check router",
        "wifi_check_adapter": "Check WiFi",
        "wifi_try_again": "Try again",
        "wifi_restart": "Restart device",

        # Ethernet menu
        "eth_title": "Ethernet",
        "eth_dhcp": "DHCP",
        "eth_static": "Static IP",
        "eth_status": "Status",
        "eth_back": "Back",

        # Flash menu
        "flash_title": "Flash",
        "flash_api": "JetHome images",
        "flash_usb": "From USB",
        "flash_list": "List",
        "flash_back": "Back",
        "flash_select": "Select Image",
        "flash_confirm_download": "Download?",
        "flash_downloaded": "Downloaded",
        "flash_confirm_flash": "Flash image?",
        "flash_warning": "Erase all data?",
        "flash_downloading": "Downloading",
        "flash_confirm": "Flash?",
        "flash_progress": "Flashing",
        "flash_done": "Done",
        "flash_complete": "Flash complete",
        "flash_error": "Error",
        "flash_failed": "Flash failed",
        "download_failed": "Download failed",
        "download_cancelling": "Canceling",
        "no_images": "No images",
        "size": "Size",
        "usb_title": "USB",
        "usb_detecting": "Detecting...",
        "usb_mounting": "Mounting",
        "usb_scanning": "Scanning",
        "usb_images": "USB Images",
        "usb_not_found": "USB not found",
        "usb_wait": "Wait for USB?",
        "usb_waiting": "Waiting USB",
        "usb_no_device": "No USB device",
        "usb_mount_failed": "Mount failed",
        "usb_no_images": "No images on USB",
        "usb_safe_remove": "Safe to remove USB",

        "info": "Info",

        # Reboot menu
        "reboot_title": "Reboot",
        "reboot_short": "Reboot",
        "reboot_now": "Now",
        "reboot_cancel": "Cancel",
        "reboot_confirm": "Reboot?",
        "reboot_wait": "Rebooting...",
        "reboot_hold_center": "Hold center",
        "reboot_hold_time": "for 3 s",
        "reboot_input_failed": "Buttons unavailable",
        "reboot_failed": "Reboot failed",

        # Info screen
        "info_title": "Information",

        # Common
        "yes": "Yes",
        "no": "No",
        "ok": "OK",
        "cancel": "Cancel",
        "back": "Back",
        "select": "Select",
        "wait": "Wait...",
        "error": "Error",
        "success": "Success",

        # Language selection
        "lang_title": "Language",
        "lang_russian": "Русский",
        "lang_english": "English",
    }
}


def set_language(lang):
    """Set current language"""
    global current_language
    if lang in TRANSLATIONS:
        current_language = lang
        return True
    return False


def t(key):
    """Translate a key to current language"""
    global current_language

    if current_language in TRANSLATIONS:
        if key in TRANSLATIONS[current_language]:
            return TRANSLATIONS[current_language][key]

    # Fallback to English
    if "ENG" in TRANSLATIONS:
        if key in TRANSLATIONS["ENG"]:
            return TRANSLATIONS["ENG"][key]

    # If not found, return key itself
    return key


def get_language():
    """Get current language"""
    return current_language


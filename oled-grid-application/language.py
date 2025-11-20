"""
Language/Translation Support for OLED Application
Supports Russian and English
"""

# Current language (default to Russian)
current_language = "RUS"

# Translation dictionary
TRANSLATIONS = {
    "RUS": {
        # Main menu
        "main_network": "Сеть",
        "main_flash": "Запись eMMC",
        "main_flash_grid": "Запись\nна диск",  # For grid menu (2 lines)
        "main_info": "Инфор\nмация",  # For grid menu (2 lines)
        "main_reboot": "Пере\nзагр.",  # For grid menu (2 lines)

        # Network menu
        "net_title": "Сеть",
        "net_test": "Статус",
        "net_wifi": "WiFi",
        "net_ethernet": "Ethernet",
        "net_ip": "IP адрес",
        "net_back": "Назад",

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
        "wifi_failed": "Ошибка",
        "wifi_wrong_password": "Неверный пароль",

        # Ethernet menu
        "eth_title": "Ethernet",
        "eth_dhcp": "DHCP",
        "eth_static": "Статич. IP",
        "eth_status": "Статус",
        "eth_back": "Назад",

        # Flash menu
        "flash_title": "Запись eMMC",
        "flash_api": "Из API",
        "flash_usb": "С USB",
        "flash_ram": "Из RAM",
        "flash_list": "Список",
        "flash_back": "Назад",
        "flash_select": "Выбор образа",
        "flash_confirm_download": "Скачать?",
        "flash_downloaded": "Скачан",
        "flash_confirm_flash": "Записать на eMMC?",
        "flash_warning": "Все данные будут стерты!",
        "flash_downloading": "Скачивание",
        "flash_confirm": "Записать?",
        "flash_progress": "Запись",
        "flash_done": "Готово",
        "flash_complete": "Запись завершена",
        "flash_error": "Ошибка",
        "flash_failed": "Ошибка записи",
        "download_failed": "Ошибка скачивания",
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

        # RAM (downloaded) images
        "ram_title": "Образы в RAM",
        "ram_no_images": "Нет скачанных образов",
        "ram_action": "Выберите действие",
        "ram_flash": "Прошить",
        "ram_delete": "Удалить",
        "ram_deleted": "Удалено",

        "info": "Инфо",

        # Reboot menu
        "reboot_title": "Перезагрузка",
        "reboot_now": "Сейчас",
        "reboot_cancel": "Отмена",
        "reboot_confirm": "Перезагрузить?",
        "reboot_wait": "Перезагрузка...",

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
        "main_flash": "Flash eMMC",
        "main_flash_grid": "Flash\nto disk",  # For grid menu (2 lines)
        "main_info": "Info",
        "main_reboot": "Reboot",

        # Network menu
        "net_title": "Network",
        "net_test": "Status",
        "net_wifi": "WiFi",
        "net_ethernet": "Ethernet",
        "net_ip": "IP Address",
        "net_back": "Back",

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
        "wifi_failed": "Failed",
        "wifi_wrong_password": "Wrong password",

        # Ethernet menu
        "eth_title": "Ethernet",
        "eth_dhcp": "DHCP",
        "eth_static": "Static IP",
        "eth_status": "Status",
        "eth_back": "Back",

        # Flash menu
        "flash_title": "Flash eMMC",
        "flash_api": "From API",
        "flash_usb": "From USB",
        "flash_ram": "From RAM",
        "flash_list": "List",
        "flash_back": "Back",
        "flash_select": "Select Image",
        "flash_confirm_download": "Download?",
        "flash_downloaded": "Downloaded",
        "flash_confirm_flash": "Flash to eMMC?",
        "flash_warning": "All data will be erased!",
        "flash_downloading": "Downloading",
        "flash_confirm": "Flash?",
        "flash_progress": "Flashing",
        "flash_done": "Done",
        "flash_complete": "Flash complete",
        "flash_error": "Error",
        "flash_failed": "Flash failed",
        "download_failed": "Download failed",
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

        # RAM (downloaded) images
        "ram_title": "Images in RAM",
        "ram_no_images": "No downloaded images",
        "ram_action": "Choose action",
        "ram_flash": "Flash",
        "ram_delete": "Delete",
        "ram_deleted": "Deleted",

        "info": "Info",

        # Reboot menu
        "reboot_title": "Reboot",
        "reboot_now": "Now",
        "reboot_cancel": "Cancel",
        "reboot_confirm": "Reboot?",
        "reboot_wait": "Rebooting...",

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


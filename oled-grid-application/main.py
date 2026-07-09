#!/usr/bin/env python3
"""
OLED Rescue Console Application - Main Entry Point

This application provides a hardware button-driven interface
for the rescue console on a 0.96" OLED display.
"""

import sys
import os
import time

# ВАЖНО: Импортировать локальные модули ДО добавления core/ в path!
from display import DisplayManager
from input import InputHandler, TestInputHandler
from menu import Menu
import config as oled_config
import language

# Import screen modules
from screens import network, flash, info, reboot

# Теперь добавляем core/ в path для импорта core/config
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'core'))

# Import from core/
import config as src_config


def initialize():
    """
    Initialize the application

    Returns:
        Tuple of (display, input_handler, menu) or None if failed
    """
    try:
        # Board (device id / platform) is auto-detected in core config
        # (env override -> /proc/device-tree/model -> fallback); do not clobber it.

        # Initialize display
        print("Initializing OLED display...")
        display = DisplayManager()

        # Show splash screen
        display.draw_splash(oled_config.APP_NAME, src_config.APP_VERSION)
        time.sleep(2)

        # Initialize input
        print("Initializing input handler...")
        if oled_config.TEST_MODE_NO_BUTTONS:
            print("⚠️  TEST MODE: Using TestInputHandler (no physical buttons)")
            input_handler = TestInputHandler()
        else:
            input_handler = InputHandler()

        # Initialize menu
        menu = Menu(display, input_handler)

        print("Initialization complete!")
        return display, input_handler, menu

    except Exception as e:
        print(f"ERROR: Failed to initialize: {e}")
        import traceback
        traceback.print_exc()
        return None


def select_language(menu):
    """Language selection screen"""
    lang_items = [
        language.TRANSLATIONS["RUS"]["lang_russian"],
        language.TRANSLATIONS["ENG"]["lang_english"]
    ]

    choice = menu.show_menu("", lang_items)  # No title, just languages

    if choice == 0:
        language.set_language("RUS")
        return "RUS"
    else:
        language.set_language("ENG")
        return "ENG"


def main():
    """Main application loop"""
    # Ensure temp directory exists
    os.makedirs(src_config.TEMP_DIR, exist_ok=True)
    print(f"Using temp directory: {src_config.TEMP_DIR}")

    # Initialize
    result = initialize()
    if not result:
        print("Failed to initialize. Exiting.")
        sys.exit(1)

    display, input_handler, menu = result

    # Language selection
    print("Language selection...")
    selected_lang = select_language(menu)
    print(f"Language set to: {selected_lang}")

    # Main menu items for grid (translated, with line breaks for long text)
    def get_main_items():
        return [
            language.t("main_network"),           # Top-left (0)
            language.t("main_flash_grid"),        # Top-right (1)
            language.t("main_info"),              # Bottom-left (2)
            language.t("main_reboot")             # Bottom-right (3)
    ]

    print("Starting main loop...")

    # Main loop
    try:
        while True:
            choice = menu.show_grid_menu(get_main_items())

            if choice is None or choice == -1:
                # Back/Home pressed - already in main menu, continue
                continue
            elif choice == 0:
                # Network Setup
                result = network.network_menu(menu)
                if result == -1:
                    # HOME pressed - return to main menu
                    continue
            elif choice == 1:
                # Flash to eMMC
                result = flash.flash_menu(menu)
                if result == -1:
                    # HOME pressed - return to main menu
                    continue
            elif choice == 2:
                # System Info
                result = info.show_system_info(menu)
                if result == -1:
                    # HOME pressed - return to main menu
                    continue
            elif choice == 3:
                # Reboot
                result = reboot.reboot_system(menu)
                if result == -1:
                    # HOME pressed - return to main menu
                    continue

            # Flush any pending input events
            input_handler.flush_events()

    except KeyboardInterrupt:
        print("\nApplication interrupted by user")
        # Cleanup resources
        try:
            input_handler.cleanup()
        except:
            pass
        display.clear()
        sys.exit(0)
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()

        try:
            menu.show_message("Error", f"Fatal error:\n{str(e)[:40]}")
            time.sleep(5)
        except:
            pass

        # Cleanup resources
        try:
            input_handler.cleanup()
        except:
            pass
        display.clear()
        sys.exit(1)


if __name__ == "__main__":
    main()


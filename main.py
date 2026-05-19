import os
import sys


def hide_console_window():
    if os.name != "nt":
        return
    try:
        import ctypes
        kernel32 = ctypes.WinDLL("kernel32")
        user32 = ctypes.WinDLL("user32")
        hwnd = kernel32.GetConsoleWindow()
        if hwnd:
            user32.ShowWindow(hwnd, 0)
    except Exception:
        pass


hide_console_window()

from gui_menu import MainMenuWindow


if __name__ == "__main__":
    MainMenuWindow().run()

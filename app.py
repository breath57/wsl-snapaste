import ctypes
import logging
import os
import tempfile
import threading
import time

import win32gui
from infi.systray import SysTrayIcon
from PIL import Image as PilImage, ImageDraw

from clipboard import has_clipboard_image, snapaste_save, snapaste_path, get_last_saved_path

APP_NAME = "WSL Snapaste"
LOG_PATH = os.path.join(tempfile.gettempdir(), "snapaste.log")

WM_DRAWCLIPBOARD = 0x0308
WM_CHANGECBCHAIN = 0x030D
WM_USER_EXIT = 0x0400

MODE_IMAGE = "image"
MODE_PATH = "path"

logging.basicConfig(
    filename=LOG_PATH,
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger(__name__)

_tray = None
_hwnd = None
_next_hwnd = None
_mode = MODE_PATH
_processing = False
_recent_saved = None


def _create_icon_image():
    size = 64
    img = PilImage.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle([4, 4, 60, 60], radius=10, fill="#2d2d2d", outline="#4ec9b0", width=2)
    draw.text((14, 8), "WSL", fill="#4ec9b0")
    draw.text((14, 30), "Snp", fill="#dcdcaa")
    icon_path = os.path.join(tempfile.gettempdir(), "snapaste_icon.ico")
    img.save(icon_path, format="ICO", sizes=[(16, 16), (32, 32), (64, 64)])
    return icon_path


def _process_clipboard():
    global _processing, _recent_saved
    if _processing:
        return
    _processing = True
    try:
        time.sleep(0.1)
        if not has_clipboard_image():
            return
        if _mode == MODE_IMAGE:
            filepath = snapaste_save()
            if filepath:
                log.info("Auto save: %s", filepath)
                _recent_saved = filepath
        elif _mode == MODE_PATH:
            filepath = snapaste_path()
            if filepath:
                log.info("Auto path: %s", filepath)
                _recent_saved = filepath
    except Exception as e:
        log.error("Error: %s", e)
    finally:
        _processing = False


def _on_to_path_mode(systray):
    global _mode
    _mode = MODE_PATH
    _update_tray(systray)


def _on_to_image_mode(systray):
    global _mode
    _mode = MODE_IMAGE
    _update_tray(systray)


def _on_path_now(systray):
    filepath = snapaste_path()
    if filepath:
        log.info("Manual path: %s", filepath)


def _on_exit(systray):
    global _hwnd, _next_hwnd
    if _hwnd:
        try:
            if _next_hwnd:
                ctypes.windll.user32.ChangeClipboardChain(_hwnd, _next_hwnd)
        except Exception:
            pass
        ctypes.windll.user32.DestroyWindow(_hwnd)
        _hwnd = None
    systray.shutdown()


def _update_tray(systray):
    if _mode == MODE_PATH:
        systray.update(hover_text=f"{APP_NAME} - 路径模式")
    else:
        systray.update(hover_text=f"{APP_NAME} - 图片模式")


def _build_menu():
    if _mode == MODE_PATH:
        menu_options = (
            ("当前: 路径模式 (WSL)", None, lambda s: None),
            ("切换为图片模式", None, _on_to_image_mode),
            ("---", None, lambda s: None),
            ("立即转换为路径", None, _on_path_now),
            ("退出", None, _on_exit),
        )
    else:
        menu_options = (
            ("当前: 图片模式 (原样)", None, lambda s: None),
            ("切换为路径模式", None, _on_to_path_mode),
            ("---", None, lambda s: None),
            ("退出", None, _on_exit),
        )
    return menu_options


def _wnd_proc(hwnd, msg, wparam, lparam):
    global _next_hwnd
    if msg == WM_DRAWCLIPBOARD:
        threading.Thread(target=_process_clipboard, daemon=True).start()
        if _next_hwnd:
            win32gui.SendMessage(_next_hwnd, msg, wparam, lparam)
    elif msg == WM_CHANGECBCHAIN:
        if _next_hwnd == wparam:
            _next_hwnd = lparam
        elif _next_hwnd:
            win32gui.SendMessage(_next_hwnd, msg, wparam, lparam)
    elif msg == WM_USER_EXIT:
        if _next_hwnd:
            ctypes.windll.user32.ChangeClipboardChain(hwnd, _next_hwnd)
        win32gui.PostQuitMessage(0)
        return 0
    return win32gui.DefWindowProc(hwnd, msg, wparam, lparam)


def run():
    global _hwnd, _next_hwnd, _tray

    icon_path = _create_icon_image()

    menu_options = _build_menu()
    _tray = SysTrayIcon(icon_path, APP_NAME, menu_options, on_quit=_on_exit)
    _tray.start()

    wc = win32gui.WNDCLASS()
    wc.lpszClassName = "SnapasteListener"
    wc.lpfnWndProc = _wnd_proc
    wc.hInstance = win32gui.GetModuleHandle(None)
    class_atom = win32gui.RegisterClass(wc)

    _hwnd = win32gui.CreateWindowEx(
        0, class_atom, "SnapasteListener", 0, 0, 0, 0, 0, 0, None, wc.hInstance, None
    )

    _next_hwnd = ctypes.windll.user32.SetClipboardViewer(_hwnd)

    log.info("Started. mode=%s hwnd=%s next=%s", _mode, _hwnd, _next_hwnd)

    win32gui.PumpMessages()

    log.info("Exited")


if __name__ == "__main__":
    run()

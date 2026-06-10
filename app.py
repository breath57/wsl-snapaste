import ctypes
import ctypes.wintypes
import logging
import os
import tempfile
import threading
import time

import win32gui
from PIL import Image as PilImage, ImageDraw

from clipboard import has_clipboard_image, snapaste, restore_clipboard_image

APP_NAME = "WSL Snapaste"
LOG_PATH = os.path.join(tempfile.gettempdir(), "snapaste.log")

WM_DRAWCLIPBOARD = 0x0308
WM_CHANGECBCHAIN = 0x030D
WM_COMMAND = 0x0111
WM_TRAYICON = 0x0401
ID_ON = 1
ID_OFF = 2
ID_QUIT = 3
ID_TRAYICON = 1

NIM_ADD = 0x00000000
NIM_DELETE = 0x00000002
NIF_MESSAGE = 0x00000001
NIF_ICON = 0x00000002
NIF_TIP = 0x00000004

MF_STRING = 0x00000000
MF_POPUP = 0x00000010
MF_SEPARATOR = 0x00000800
MF_CHECKED = 0x00000008

TPM_RIGHTBUTTON = 0x0020
TPM_BOTTOMALIGN = 0x0020

logging.basicConfig(
    filename=LOG_PATH,
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger(__name__)

_clip_hwnd = None
_tray_hwnd = None
_next_hwnd = None
_enabled = True
_processing = False


class NOTIFYICONDATAW(ctypes.Structure):
    _fields_ = [
        ("cbSize", ctypes.c_uint),
        ("hWnd", ctypes.wintypes.HWND),
        ("uID", ctypes.c_uint),
        ("uFlags", ctypes.c_uint),
        ("uCallbackMessage", ctypes.c_uint),
        ("hIcon", ctypes.wintypes.HANDLE),
        ("szTip", ctypes.c_wchar * 128),
        ("dwState", ctypes.c_uint),
        ("dwStateMask", ctypes.c_uint),
        ("szInfo", ctypes.c_wchar * 256),
        ("uTimeoutOrVersion", ctypes.c_uint),
        ("szInfoTitle", ctypes.c_wchar * 64),
        ("dwInfoFlags", ctypes.c_uint),
        ("guidItem", ctypes.c_wchar * 39),
        ("hBalloonIcon", ctypes.wintypes.HANDLE),
    ]


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


def _add_tray_icon(hwnd):
    hicon = win32gui.LoadImage(
        0, os.path.join(tempfile.gettempdir(), "snapaste_icon.ico"),
        1, 16, 16, 0x00000010
    )
    nid = NOTIFYICONDATAW()
    nid.cbSize = ctypes.sizeof(NOTIFYICONDATAW)
    nid.hWnd = hwnd
    nid.uID = ID_TRAYICON
    nid.uFlags = NIF_MESSAGE | NIF_ICON | NIF_TIP
    nid.uCallbackMessage = WM_TRAYICON
    nid.hIcon = hicon
    nid.szTip = APP_NAME
    ctypes.windll.shell32.Shell_NotifyIconW(NIM_ADD, ctypes.byref(nid))


def _remove_tray_icon(hwnd):
    nid = NOTIFYICONDATAW()
    nid.cbSize = ctypes.sizeof(NOTIFYICONDATAW)
    nid.hWnd = hwnd
    nid.uID = ID_TRAYICON
    ctypes.windll.shell32.Shell_NotifyIconW(NIM_DELETE, ctypes.byref(nid))


def _show_menu(hwnd):
    hmenu = win32gui.CreatePopupMenu()

    hsub = win32gui.CreatePopupMenu()
    on_flag = MF_CHECKED if _enabled else 0
    off_flag = MF_CHECKED if not _enabled else 0
    win32gui.AppendMenu(hsub, MF_STRING | on_flag, ID_ON, "\u5f00\u542f")
    win32gui.AppendMenu(hsub, MF_STRING | off_flag, ID_OFF, "\u5173\u95ed")
    win32gui.AppendMenu(hmenu, MF_POPUP, hsub, "\u72b6\u6001")

    win32gui.AppendMenu(hmenu, MF_SEPARATOR, 0, "")
    win32gui.AppendMenu(hmenu, MF_STRING, ID_QUIT, "\u9000\u51fa")

    pt = win32gui.GetCursorPos()
    win32gui.SetForegroundWindow(hwnd)
    win32gui.TrackPopupMenu(hmenu, TPM_RIGHTBUTTON | TPM_BOTTOMALIGN, pt[0], pt[1], 0, hwnd, None)
    win32gui.PostMessage(hwnd, 0, 0, 0)


def _on_exit():
    global _clip_hwnd, _next_hwnd
    if _tray_hwnd:
        _remove_tray_icon(_tray_hwnd)
        win32gui.DestroyWindow(_tray_hwnd)
    if _clip_hwnd:
        try:
            if _next_hwnd:
                ctypes.windll.user32.ChangeClipboardChain(_clip_hwnd, _next_hwnd)
        except Exception:
            pass
        win32gui.DestroyWindow(_clip_hwnd)
        _clip_hwnd = None
    win32gui.PostQuitMessage(0)


def _tray_proc(hwnd, msg, wparam, lparam):
    global _enabled
    if msg == WM_TRAYICON:
        if lparam == 0x0204:
            _show_menu(hwnd)
    elif msg == WM_COMMAND:
        cmd = wparam & 0xFFFF
        if cmd == ID_ON:
            was_off = not _enabled
            _enabled = True
            log.info("ON")
            if was_off:
                threading.Thread(target=_toggle_clipboard, args=(True,), daemon=True).start()
        elif cmd == ID_OFF:
            was_on = _enabled
            _enabled = False
            log.info("OFF")
            if was_on:
                threading.Thread(target=_toggle_clipboard, args=(False,), daemon=True).start()
        elif cmd == ID_QUIT:
            _on_exit()
    return win32gui.DefWindowProc(hwnd, msg, wparam, lparam)


def _toggle_clipboard(to_enabled: bool):
    """Trigger clipboard conversion on state toggle."""
    global _processing
    if _processing:
        return
    _processing = True
    try:
        time.sleep(0.1)
        if to_enabled:
            filepath = snapaste()
            if filepath:
                log.info("Toggle ON -> Path: %s", filepath)
        else:
            if restore_clipboard_image():
                log.info("Toggle OFF -> Restored image")
    except Exception as e:
        log.error("Toggle error: %s", e)
    finally:
        _processing = False


def _process_clipboard():
    global _processing
    if _processing or not _enabled:
        return
    _processing = True
    try:
        time.sleep(0.1)
        if not has_clipboard_image():
            return
        filepath = snapaste()
        if filepath:
            log.info("Path: %s", filepath)
    except Exception as e:
        log.error("Error: %s", e)
    finally:
        _processing = False


def _clip_proc(hwnd, msg, wparam, lparam):
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
    return win32gui.DefWindowProc(hwnd, msg, wparam, lparam)


def run():
    global _clip_hwnd, _tray_hwnd, _next_hwnd

    _create_icon_image()

    wc = win32gui.WNDCLASS()
    wc.lpszClassName = "SnapasteTray"
    wc.lpfnWndProc = _tray_proc
    wc.hInstance = win32gui.GetModuleHandle(None)
    _tray_hwnd = win32gui.CreateWindowEx(
        0, win32gui.RegisterClass(wc), "SnapasteTray",
        0, 0, 0, 0, 0, 0, None, wc.hInstance, None
    )
    _add_tray_icon(_tray_hwnd)

    wc2 = win32gui.WNDCLASS()
    wc2.lpszClassName = "SnapasteListener"
    wc2.lpfnWndProc = _clip_proc
    wc2.hInstance = win32gui.GetModuleHandle(None)
    _clip_hwnd = win32gui.CreateWindowEx(
        0, win32gui.RegisterClass(wc2), "SnapasteListener",
        0, 0, 0, 0, 0, 0, None, wc2.hInstance, None
    )
    _next_hwnd = ctypes.windll.user32.SetClipboardViewer(_clip_hwnd)

    log.info("Started")
    win32gui.PumpMessages()
    log.info("Exited")


if __name__ == "__main__":
    run()
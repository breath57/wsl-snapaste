import sys
import ctypes
import ctypes.wintypes
import logging
import os
import tempfile
import threading
import time

import win32gui
from PIL import Image as PilImage, ImageDraw

from clipboard import has_clipboard_image, restore_clipboard_image, snapaste
from version import __version__

def _get_resource_path(relative_path):
    """Get absolute path to resource, works for dev and for PyInstaller"""
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)

APP_NAME = "WSL Snapaste"
LOG_PATH = os.path.join(tempfile.gettempdir(), "snapaste.log")

MUTEX_NAME = "WSL-Snapaste-SingleInstance"
_mutex_handle = None

WM_CLIPBOARDUPDATE = 0x031D
WM_COMMAND = 0x0111
WM_TRAYICON = 0x0401
ID_ON = 1
ID_OFF = 2
ID_QUIT = 3
ID_TRAYICON = 1

# Watchdog settings
WATCHDOG_INTERVAL = 5  # seconds
_last_clipboard_time = 0
_watchdog_thread = None
_watchdog_running = False

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
    icon_path = os.path.join(tempfile.gettempdir(), "snapaste_icon.ico")
    logo_path = _get_resource_path("assets/icon.png")

    try:
        img = PilImage.open(logo_path).convert("RGBA")
        img.save(
            icon_path,
            format="ICO",
            sizes=[(16, 16), (20, 20), (24, 24), (32, 32), (40, 40), (48, 48), (64, 64), (128, 128), (256, 256)],
        )
    except FileNotFoundError:
        size = 256
        img = PilImage.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        draw.rounded_rectangle([16, 16, 240, 240], radius=44, fill="#2d2d2d", outline="#4ec9b0", width=10)
        draw.text((56, 52), "WSL", fill="#4ec9b0")
        draw.text((56, 132), "Snp", fill="#dcdcaa")
        img.save(icon_path, format="ICO", sizes=[(16, 16), (20, 20), (24, 24), (32, 32), (40, 40), (48, 48), (64, 64), (128, 128), (256, 256)])
    return icon_path


def _set_dpi_awareness():
    try:
        ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
    except Exception:
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:
            try:
                ctypes.windll.user32.SetProcessDPIAware()
            except Exception:
                pass


def _add_tray_icon(hwnd):
    cx = ctypes.windll.user32.GetSystemMetrics(49) or 32
    cy = ctypes.windll.user32.GetSystemMetrics(50) or 32
    hicon = win32gui.LoadImage(
        0, os.path.join(tempfile.gettempdir(), "snapaste_icon.ico"),
        1, cx, cy, 0x00000010
    )
    nid = NOTIFYICONDATAW()
    nid.cbSize = ctypes.sizeof(NOTIFYICONDATAW)
    nid.hWnd = hwnd
    nid.uID = ID_TRAYICON
    nid.uFlags = NIF_MESSAGE | NIF_ICON | NIF_TIP
    nid.uCallbackMessage = WM_TRAYICON
    nid.hIcon = hicon
    nid.szTip = f"{APP_NAME} v{__version__}"
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
    status_text = "\u72b6\u6001[\u5f00\u542f]" if _enabled else "\u72b6\u6001[\u5173\u95ed]"
    win32gui.AppendMenu(hmenu, MF_POPUP, hsub, status_text)

    win32gui.AppendMenu(hmenu, MF_SEPARATOR, 0, "")
    win32gui.AppendMenu(hmenu, MF_STRING, ID_QUIT, "\u9000\u51fa")

    pt = win32gui.GetCursorPos()
    win32gui.SetForegroundWindow(hwnd)
    win32gui.TrackPopupMenu(hmenu, TPM_RIGHTBUTTON | TPM_BOTTOMALIGN, pt[0], pt[1], 0, hwnd, None)
    win32gui.PostMessage(hwnd, 0, 0, 0)


def _on_exit():
    global _clip_hwnd, _watchdog_running
    
    # Stop watchdog thread
    _watchdog_running = False
    
    if _tray_hwnd:
        _remove_tray_icon(_tray_hwnd)
        win32gui.DestroyWindow(_tray_hwnd)
    if _clip_hwnd:
        try:
            ctypes.windll.user32.RemoveClipboardFormatListener(_clip_hwnd)
        except Exception:
            pass
        win32gui.DestroyWindow(_clip_hwnd)
        _clip_hwnd = None
    _release_single_instance()
    win32gui.PostQuitMessage(0)


def _acquire_single_instance():
    global _mutex_handle
    # Create mutex with initial ownership
    _mutex_handle = ctypes.windll.kernel32.CreateMutexW(None, True, MUTEX_NAME)
    if not _mutex_handle:
        # Failed to create mutex, proceed anyway
        return True
    
    # Check if mutex already exists (ERROR_ALREADY_EXISTS = 183)
    if ctypes.windll.kernel32.GetLastError() == 183:
        # Another instance is already running
        ctypes.windll.user32.MessageBoxW(
            0,
            "WSL Snapaste 已经在运行中。",
            APP_NAME,
            0x40 | 0x00000000  # MB_ICONINFORMATION | MB_OK
        )
        return False
    return True


def _release_single_instance():
    global _mutex_handle
    if _mutex_handle:
        ctypes.windll.kernel32.ReleaseMutex(_mutex_handle)
        ctypes.windll.kernel32.CloseHandle(_mutex_handle)
        _mutex_handle = None


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
    global _processing, _last_clipboard_time
    
    if _processing:
        log.info("Toggle ignored, already processing")
        return
    
    _processing = True
    try:
        time.sleep(0.1)
        if to_enabled:
            # Re-register clipboard listener when enabling
            if _clip_hwnd:
                try:
                    ctypes.windll.user32.RemoveClipboardFormatListener(_clip_hwnd)
                    time.sleep(0.05)
                    if ctypes.windll.user32.AddClipboardFormatListener(_clip_hwnd):
                        log.info("Clipboard listener re-registered on enable")
                        _last_clipboard_time = time.time()
                    else:
                        log.error("Failed to re-register clipboard listener on enable")
                except Exception as e:
                    log.error("Error re-registering listener: %s", e)
            
            filepath = snapaste()
            if filepath:
                log.info("Toggle ON -> Path: %s", filepath)
            else:
                log.info("Toggle ON -> No clipboard image")
        else:
            if restore_clipboard_image():
                log.info("Toggle OFF -> Restored image")
            else:
                log.info("Toggle OFF -> No image to restore")
    except Exception as e:
        log.error("Toggle error: %s", e)
    finally:
        _processing = False


def _process_clipboard():
    global _processing, _last_clipboard_time
    
    if _processing or not _enabled:
        return
    
    _processing = True
    try:
        time.sleep(0.1)
        if not has_clipboard_image():
            return
        
        # Update last clipboard time
        _last_clipboard_time = time.time()
        
        filepath = snapaste()
        if filepath:
            log.info("Clipboard converted: %s", filepath)
        else:
            log.info("Clipboard image detected but conversion failed")
    except Exception as e:
        log.error("Clipboard processing error: %s", e)
    finally:
        _processing = False


def _clip_proc(hwnd, msg, wparam, lparam):
    global _last_clipboard_time
    if msg == WM_CLIPBOARDUPDATE:
        _last_clipboard_time = time.time()
        threading.Thread(target=_process_clipboard, daemon=True).start()
    return win32gui.DefWindowProc(hwnd, msg, wparam, lparam)


def _watchdog():
    """Watchdog thread to monitor clipboard listener health."""
    global _clip_hwnd, _watchdog_running, _last_clipboard_time
    
    while _watchdog_running:
        time.sleep(WATCHDOG_INTERVAL)
        
        if not _enabled:
            continue
            
        # Check if we haven't received clipboard updates for a while
        if _last_clipboard_time > 0 and time.time() - _last_clipboard_time > 30:
            log.warning("Clipboard listener may be stale, attempting to re-register")
            try:
                # Try to re-register the clipboard listener
                if _clip_hwnd:
                    ctypes.windll.user32.RemoveClipboardFormatListener(_clip_hwnd)
                    time.sleep(0.1)
                    if ctypes.windll.user32.AddClipboardFormatListener(_clip_hwnd):
                        log.info("Clipboard listener re-registered successfully")
                        _last_clipboard_time = time.time()
                    else:
                        log.error("Failed to re-register clipboard listener")
            except Exception as e:
                log.error("Watchdog re-register error: %s", e)


def run():
    global _clip_hwnd, _tray_hwnd, _watchdog_running, _last_clipboard_time

    # Check for single instance before initializing
    if not _acquire_single_instance():
        log.info("Another instance is already running, exiting.")
        return

    _set_dpi_awareness()
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
    if ctypes.windll.user32.AddClipboardFormatListener(_clip_hwnd):
        log.info("Clipboard listener registered successfully")
        _last_clipboard_time = time.time()
    else:
        log.error("AddClipboardFormatListener failed")

    # Start watchdog thread
    _watchdog_running = True
    _watchdog_thread = threading.Thread(target=_watchdog, daemon=True)
    _watchdog_thread.start()

    log.info("Started")
    win32gui.PumpMessages()
    log.info("Exited")


if __name__ == "__main__":
    run()

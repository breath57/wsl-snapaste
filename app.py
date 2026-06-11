import sys
import ctypes
import ctypes.wintypes
import logging
import os
import tempfile
import threading
import time

import win32gui
import win32con
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

def _close_existing_instance():
    """Find and close existing instance by locating its tray window."""
    result = [None]

    def enum_callback(hwnd, _):
        if win32gui.GetClassName(hwnd) == "SnapasteTray":
            result[0] = hwnd
            return False
        return True

    win32gui.EnumWindows(enum_callback, None)
    hwnd = result[0]
    if not hwnd:
        return True  # No existing instance found

    # Get process ID of the old instance
    pid = ctypes.wintypes.DWORD()
    ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    if not pid.value:
        return True

    # Try graceful close first
    win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)
    # Wait up to 3 seconds for it to exit
    for _ in range(30):
        time.sleep(0.1)
        # Check if process still exists
        handle = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid.value)  # PROCESS_QUERY_LIMITED_INFORMATION
        if not handle:
            return True  # Process exited
        ctypes.windll.kernel32.CloseHandle(handle)

    # Still running — force kill
    handle = ctypes.windll.kernel32.OpenProcess(0x0001, False, pid.value)  # PROCESS_TERMINATE
    if handle:
        ctypes.windll.kernel32.TerminateProcess(handle, 0)
        ctypes.windll.kernel32.CloseHandle(handle)
        time.sleep(0.5)
    return True

WM_CLIPBOARDUPDATE = 0x031D
WM_COMMAND = 0x0111
WM_TRAYICON = 0x0401
ID_ON = 1
ID_OFF = 2
ID_QUIT = 3
ID_TRAYICON = 1

# Watchdog settings
WATCHDOG_INTERVAL = 5  # seconds
WATCHDOG_REREGISTER_INTERVAL = 120  # re-register every 2 minutes
_last_clipboard_time = 0
_last_re_register_time = 0
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
    global _clip_hwnd, _watchdog_running, _last_clipboard_time, _last_re_register_time
    
    _last_re_register_time = time.time()
    
    while _watchdog_running:
        time.sleep(WATCHDOG_INTERVAL)
        
        if not _enabled or not _clip_hwnd:
            continue
        
        now = time.time()
        should_reregister = False
        reason = ""
        
        # Reason 1: periodic re-register (always, every 2 min)
        if now - _last_re_register_time >= WATCHDOG_REREGISTER_INTERVAL:
            should_reregister = True
            reason = "periodic"
        
        # Reason 2: stale listener (no clipboard activity for 30s)
        if _last_clipboard_time > 0 and now - _last_clipboard_time > 30:
            should_reregister = True
            reason = "stale"
        
        if not should_reregister:
            continue
        
        try:
            ctypes.windll.user32.RemoveClipboardFormatListener(_clip_hwnd)
            time.sleep(0.1)
            if ctypes.windll.user32.AddClipboardFormatListener(_clip_hwnd):
                log.info("Clipboard listener re-registered (%s)", reason)
                _last_clipboard_time = now
                _last_re_register_time = now
            else:
                log.error("Failed to re-register clipboard listener (%s)", reason)
        except Exception as e:
            log.error("Watchdog re-register error (%s): %s", reason, e)


def run():
    global _clip_hwnd, _tray_hwnd, _watchdog_running, _last_clipboard_time

    # Close existing instance before initializing
    _close_existing_instance()

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

import ctypes
import ctypes.wintypes
import io
import os
import struct
import tempfile
import time
from pathlib import Path

import win32clipboard
from PIL import Image

CF_UNICODETEXT = 13
CF_DIB = 8


def win_to_wsl_path(win_path: str) -> str:
    p = Path(win_path)
    drive = p.drive.rstrip(":").lower()
    return f"/mnt/{drive}{p.as_posix()[2:]}"


def has_clipboard_image() -> bool:
    return win32clipboard.IsClipboardFormatAvailable(CF_DIB)


def get_clipboard_image() -> Image.Image | None:
    win32clipboard.OpenClipboard(0)
    try:
        if not win32clipboard.IsClipboardFormatAvailable(CF_DIB):
            return None
        data = win32clipboard.GetClipboardData(CF_DIB)
        if not data:
            return None
        return _dib_to_image(data)
    finally:
        win32clipboard.CloseClipboard()


def _dib_to_image(dib_data: bytes) -> Image.Image:
    bmp_header = struct.pack("<2sIHHI", b"BM", 14 + len(dib_data), 0, 0, 14)
    bmp_data = bmp_header + dib_data
    return Image.open(io.BytesIO(bmp_data))


MAX_SAVED = 50


def save_clipboard_image(subdir: str = "snapaste") -> str | None:
    img = get_clipboard_image()
    if img is None:
        return None

    save_dir = Path(tempfile.gettempdir()) / subdir
    save_dir.mkdir(parents=True, exist_ok=True)

    filename = f"snap_{int(time.time() * 1000)}.png"
    filepath = save_dir / filename
    img.save(str(filepath), "PNG")

    _cleanup_old_files(save_dir)

    return str(filepath)


def _cleanup_old_files(save_dir: Path) -> None:
    files = sorted(save_dir.glob("snap_*.png"), key=lambda f: f.stat().st_mtime)
    while len(files) > MAX_SAVED:
        try:
            files.pop(0).unlink()
        except OSError:
            break


def is_snapaste_clipboard() -> bool:
    win32clipboard.OpenClipboard(0)
    try:
        if not win32clipboard.IsClipboardFormatAvailable(CF_UNICODETEXT):
            return False
        try:
            text = win32clipboard.GetClipboardData(CF_UNICODETEXT)
        except Exception:
            return False
        return isinstance(text, str) and text.startswith("/mnt/") and text.endswith(".png")
    finally:
        win32clipboard.CloseClipboard()


def get_clipboard_dib() -> bytes | None:
    win32clipboard.OpenClipboard(0)
    try:
        if not win32clipboard.IsClipboardFormatAvailable(CF_DIB):
            return None
        return win32clipboard.GetClipboardData(CF_DIB)
    finally:
        win32clipboard.CloseClipboard()


def set_clipboard_to_path(win_path: str) -> None:
    wsl_path = win_to_wsl_path(win_path)
    win_path_native = str(Path(win_path).resolve())

    dib_data = get_clipboard_dib()

    win32clipboard.OpenClipboard(0)
    try:
        win32clipboard.EmptyClipboard()

        if dib_data:
            win32clipboard.SetClipboardData(CF_DIB, dib_data)

        win32clipboard.SetClipboardData(CF_UNICODETEXT, wsl_path)

        _set_clipboard_filedrop([win_path_native])
    finally:
        win32clipboard.CloseClipboard()


def _set_clipboard_filedrop(files: list[str]) -> None:
    CF_HDROP = 15

    chars = "".join(f + "\0" for f in files) + "\0"
    encoded = chars.encode("utf-16-le")
    DROPFILES_size = 20
    total = DROPFILES_size + len(encoded)

    kernel32 = ctypes.windll.kernel32
    kernel32.GlobalAlloc.restype = ctypes.wintypes.HGLOBAL
    kernel32.GlobalLock.restype = ctypes.c_void_p
    kernel32.GlobalAlloc.argtypes = [ctypes.c_uint, ctypes.c_size_t]
    kernel32.GlobalLock.argtypes = [ctypes.wintypes.HGLOBAL]
    kernel32.GlobalUnlock.argtypes = [ctypes.wintypes.HGLOBAL]

    hmem = kernel32.GlobalAlloc(0x0042, total)
    ptr = kernel32.GlobalLock(hmem)

    DROPFILES_struct = struct.pack("<IiiIII", DROPFILES_size, 0, 0, 0, 0, 1)
    ctypes.memmove(ptr, DROPFILES_struct, DROPFILES_size)
    ctypes.memmove(ptr + DROPFILES_size, encoded, len(encoded))
    kernel32.GlobalUnlock(hmem)

    user32 = ctypes.windll.user32
    user32.SetClipboardData.restype = ctypes.wintypes.HANDLE
    user32.SetClipboardData.argtypes = [ctypes.c_uint, ctypes.wintypes.HANDLE]
    user32.SetClipboardData(CF_HDROP, hmem)


_saved_paths: list[str] = []


def restore_clipboard_image() -> bool:
    "Restore clipboard to raw DIB only, removing path/text formats."
    if not _saved_paths:
        return False
    dib_data = get_clipboard_dib()
    if not dib_data:
        return False
    win32clipboard.OpenClipboard(0)
    try:
        win32clipboard.EmptyClipboard()
        win32clipboard.SetClipboardData(CF_DIB, dib_data)
    finally:
        win32clipboard.CloseClipboard()
    return True


def snapaste() -> str | None:
    if not has_clipboard_image():
        return None
    if is_snapaste_clipboard():
        return None
    filepath = save_clipboard_image()
    if not filepath:
        return None
    _saved_paths.append(filepath)
    set_clipboard_to_path(filepath)
    return filepath

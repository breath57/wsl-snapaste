import win32clipboard
import io
import time
import struct
import ctypes
import ctypes.wintypes
from PIL import Image

time.sleep(0.3)
img = Image.open("tests/test_image.png")
output = io.BytesIO()
img.convert("RGBA").save(output, "BMP")
dib_data = output.getvalue()[14:]

win_path = r"C:\Users\ws\AppData\Local\Temp\snapaste\test_all3.png"
img.save(win_path, "PNG")

wsl_path = "/mnt/c/Users/ws/AppData/Local/Temp/snapaste/test_all3.png"

win32clipboard.OpenClipboard(0)
win32clipboard.EmptyClipboard()

win32clipboard.SetClipboardData(8, dib_data)
win32clipboard.SetClipboardData(13, wsl_path)

chars = win_path + "\0\0"
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
user32.SetClipboardData(15, hmem)

win32clipboard.CloseClipboard()
print("Written: DIB + UnicodeText + CF_HDROP (all three)")

import win32clipboard
import io
from PIL import Image

img = Image.open('tests/test_image.png')
out = io.BytesIO()
img.convert('RGBA').save(out, 'BMP')
dib = out.getvalue()[14:]

win32clipboard.OpenClipboard(0)
win32clipboard.EmptyClipboard()
win32clipboard.SetClipboardData(8, dib)
win32clipboard.CloseClipboard()
print('copied')

import ctypes
import sys

from app import run

ERROR_ALREADY_EXISTS = 183
_mutex_handle = None


def _acquire_single_instance() -> bool:
    global _mutex_handle
    kernel32 = ctypes.windll.kernel32
    _mutex_handle = kernel32.CreateMutexW(
        None,
        False,
        "Global\\WSL-Snapaste-SingleInstance",
    )
    return kernel32.GetLastError() != ERROR_ALREADY_EXISTS


if __name__ == "__main__":
    if not _acquire_single_instance():
        sys.exit(0)
    run()

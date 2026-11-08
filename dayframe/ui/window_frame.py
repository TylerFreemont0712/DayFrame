"""Theme native Windows frames while retaining OS resize, snap and caption controls."""

import ctypes
import sys
import weakref
from PySide6.QtCore import QObject, QEvent, QTimer, Qt
from PySide6.QtWidgets import QApplication, QWidget
from shiboken6 import isValid


def colorref(color):
    color = color.lstrip("#")
    return int(color[0:2], 16) | (int(color[2:4], 16) << 8) | (int(color[4:6], 16) << 16)


def _dwm():
    api = ctypes.WinDLL("dwmapi")
    for name in ("DwmSetWindowAttribute", "DwmGetWindowAttribute"):
        fn = getattr(api, name)
        fn.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_void_p, ctypes.c_uint32]
        fn.restype = ctypes.c_long
    return api


def apply_native_frame(widget):
    app = QApplication.instance()
    if (
        sys.platform != "win32"
        or not app
        or app.platformName() != "windows"
        or not isValid(widget)
        or not widget.isWindow()
    ):
        return {}
    if widget.windowType() not in (Qt.Window, Qt.Dialog, Qt.Tool):
        return {}
    from .theme import CURRENT

    values = {
        20: 1 if CURRENT.get("dark", True) else 0,
        34: colorref(CURRENT["line"]),
        35: colorref(CURRENT["bg"]),
        36: colorref(CURRENT["text"]),
    }
    try:
        hwnd = int(widget.winId())
        if getattr(widget, "_native_frame_cache", None) == (hwnd, values):
            return widget._native_frame_result
        api = _dwm()
        result = {}
        for attribute, value in values.items():
            number = ctypes.c_uint32(value)
            result[str(attribute)] = int(
                api.DwmSetWindowAttribute(hwnd, attribute, ctypes.byref(number), ctypes.sizeof(number))
            )
        widget._native_frame_cache = (hwnd, values)
        widget._native_frame_result = result
        return result
    except (OSError, AttributeError, RuntimeError):
        # Older Windows/compositors may decline individual attributes.
        return {}


def read_native_frame(widget):
    if sys.platform != "win32" or QApplication.platformName() != "windows":
        return {}
    try:
        api = _dwm()
        hwnd = int(widget.winId())
        result = {}
        for attribute in (20, 34, 35, 36):
            number = ctypes.c_uint32()
            status = api.DwmGetWindowAttribute(hwnd, attribute, ctypes.byref(number), ctypes.sizeof(number))
            result[str(attribute)] = {"status": int(status), "value": number.value}
        return result
    except (OSError, AttributeError, RuntimeError):
        return {}


class FrameThemeFilter(QObject):
    def __init__(self, parent):
        super().__init__(parent)
        self.pending = weakref.WeakSet()

    def eventFilter(self, widget, event):
        if (
            isinstance(widget, QWidget)
            and widget.isWindow()
            and event.type() in (QEvent.Show, QEvent.WinIdChange)
        ):
            if widget not in self.pending:
                self.pending.add(widget)
                reference = weakref.ref(widget)

                def update():
                    window = reference()
                    if window is not None:
                        self.pending.discard(window)
                        if isValid(window):
                            apply_native_frame(window)

                QTimer.singleShot(0, update)
        return False


def install_frame_theming():
    app = QApplication.instance()
    if sys.platform != "win32" or app.platformName() != "windows":
        return
    if not hasattr(app, "_frame_theme_filter"):
        app._frame_theme_filter = FrameThemeFilter(app)
        app.installEventFilter(app._frame_theme_filter)
    for widget in app.topLevelWidgets():
        if widget.testAttribute(Qt.WA_WState_Created):
            apply_native_frame(widget)

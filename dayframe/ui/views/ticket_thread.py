"""Widgets for the ticket discussion: Markdown text, screenshots, avatars and the composer."""

import base64
from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPixmap
from PySide6.QtWidgets import (
    QDialogButtonBox,
    QFileDialog,
    QFrame,
    QLabel,
    QPlainTextEdit,
    QScrollArea,
    QSizePolicy,
    QTextBrowser,
)
from ...core import domain as D
from ..theme import CURRENT as C
from ..widgets import FormDialog, button, error

MAX_SIDE = 1600
THUMB = QSize(220, 140)


def prepare_image(image, name="screenshot.png"):
    """Shrink and recompress an image until it fits the stored attachment limit.

    PNG is kept when it already fits (crisp UI screenshots); otherwise JPEG at falling
    quality, then smaller sizes. Raises ValueError when nothing usable fits.
    """
    if image.isNull():
        raise ValueError("That is not an image DayFrame can read.")
    if max(image.width(), image.height()) > MAX_SIDE:
        image = image.scaled(MAX_SIDE, MAX_SIDE, Qt.KeepAspectRatio, Qt.SmoothTransformation)
    attempts = [("PNG", "image/png", -1)] + [("JPG", "image/jpeg", q) for q in (88, 78, 66, 52)]
    for _ in range(4):
        for fmt, media, quality in attempts:
            data = QByteArray()
            buffer = QBuffer(data)
            buffer.open(QIODevice.WriteOnly)
            source = image if fmt == "PNG" else image.convertToFormat(QImage.Format_RGB888)
            source.save(buffer, fmt, quality)
            raw = bytes(data)
            encoded = base64.b64encode(raw).decode()
            if len(encoded) <= D.MAX_ATTACHMENT_CHARS:
                stem = name.rsplit(".", 1)[0] or "screenshot"
                return {
                    "name": stem + (".png" if fmt == "PNG" else ".jpg"),
                    "media_type": media,
                    "data": encoded,
                    "size": len(raw),
                    "width": image.width(),
                    "height": image.height(),
                }
        image = image.scaled(
            int(image.width() * 0.75), int(image.height() * 0.75), Qt.KeepAspectRatio, Qt.SmoothTransformation
        )
    raise ValueError("This image is too large to attach, even after shrinking it.")


def pixmap_for(window, attachment_id):
    """The decoded image for an attachment, cached on the window."""
    cache = window.__dict__.setdefault("_image_cache", {})
    if attachment_id not in cache:
        record = window.store.read("attachment", attachment_id)
        pixmap = QPixmap()
        if record:
            pixmap.loadFromData(base64.b64decode(record["data"]))
        cache[attachment_id] = pixmap
    return cache[attachment_id]


class Thumb(QLabel):
    """A clickable screenshot thumbnail that opens the full image."""

    def __init__(self, window, attachment, pixmap=None):
        super().__init__()
        self.window = window
        self.attachment = attachment
        self.full = pixmap if pixmap is not None else pixmap_for(window, attachment["id"])
        self.setObjectName("thumb")
        self.setCursor(Qt.PointingHandCursor)
        self.setFrameShape(QFrame.Box)
        self.setAlignment(Qt.AlignCenter)
        self.setFixedSize(THUMB)
        if not self.full.isNull():
            self.setPixmap(self.full.scaled(THUMB - QSize(4, 4), Qt.KeepAspectRatio, Qt.SmoothTransformation))
        else:
            self.setText("Image unavailable")
        size = attachment.get("size") or attachment.get("data_size", 0)
        self.setToolTip(
            "%s · %d×%d · %d KB · click to enlarge"
            % (
                attachment["name"],
                attachment.get("width", 0),
                attachment.get("height", 0),
                round(size / 1024),
            )
        )
        self.setAccessibleName("Screenshot " + attachment["name"])

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and not self.full.isNull():
            ImageViewer(self.window, self.attachment["name"], self.full).exec()


class ImageViewer(FormDialog):
    def __init__(self, parent, title, pixmap):
        super().__init__(parent, title)
        self.pixmap = pixmap
        available = self.available_rect()
        self.resize(
            min(pixmap.width() + 60, available.width()), min(pixmap.height() + 120, available.height())
        )
        view = QLabel()
        view.setPixmap(pixmap)
        view.setAlignment(Qt.AlignCenter)
        area = QScrollArea()
        area.setWidget(view)
        area.setWidgetResizable(True)
        self.layout.addWidget(area, 1)
        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        save = buttons.addButton("Save image…", QDialogButtonBox.ActionRole)
        save.clicked.connect(self.save)
        buttons.rejected.connect(self.reject)
        self.set_footer(buttons)

    def fit_to_contents(self):
        pass

    def save(self):
        path, _ = QFileDialog.getSaveFileName(self, "Save image", self.windowTitle(), "Images (*.png *.jpg)")
        if path and not self.pixmap.save(path):
            error(self, "The image could not be saved.")


class MarkdownView(QTextBrowser):
    """Read-only Markdown that grows to fit its text instead of scrolling."""

    def __init__(self, text, placeholder=""):
        super().__init__()
        self.setObjectName("markdown")
        self.setOpenExternalLinks(True)
        self.setFrameShape(QFrame.NoFrame)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.viewport().setAutoFillBackground(False)
        self.setStyleSheet("QTextBrowser#markdown { background:transparent; border:0; }")
        if text.strip():
            self.setMarkdown(text)
        else:
            self.setPlainText(placeholder)
            self.setStyleSheet(self.styleSheet() + " QTextBrowser#markdown { color:" + C["muted"] + "; }")
        self.document().documentLayout().documentSizeChanged.connect(self.fit)
        self.fit()

    def fit(self, *args):
        self.setFixedHeight(int(self.document().size().height()) + 6)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.document().setTextWidth(self.viewport().width())
        self.fit()


def avatar(name, size=28):
    """A round initial in the accent colour; team members get real avatars later."""
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    p = QPainter(pixmap)
    p.setRenderHint(QPainter.Antialiasing)
    fill = QColor(C["accent"])
    fill.setAlpha(60)
    p.setBrush(fill)
    p.setPen(QColor(C["accent"]))
    p.drawEllipse(1, 1, size - 2, size - 2)
    font = QFont(p.font())
    font.setBold(True)
    font.setPixelSize(int(size * 0.45))
    p.setFont(font)
    p.drawText(pixmap.rect(), Qt.AlignCenter, (name or "?")[:1].upper())
    p.end()
    picture = QLabel()
    picture.setPixmap(pixmap)
    picture.setFixedSize(size, size)
    return picture


class PasteEdit(QPlainTextEdit):
    """Comment box that turns pasted or dropped images into attachments."""

    imagePasted = Signal(QImage, str)

    def canInsertFromMimeData(self, source):
        return source.hasImage() or self._image_urls(source) or super().canInsertFromMimeData(source)

    def insertFromMimeData(self, source):
        if source.hasImage():
            self.imagePasted.emit(QImage(source.imageData()), "pasted-screenshot.png")
            return
        urls = self._image_urls(source)
        if urls:
            for url in urls:
                self.imagePasted.emit(QImage(url.toLocalFile()), url.fileName())
            return
        super().insertFromMimeData(source)

    @staticmethod
    def _image_urls(source):
        if not source.hasUrls():
            return []
        return [
            u
            for u in source.urls()
            if u.isLocalFile() and u.fileName().lower().endswith((".png", ".jpg", ".jpeg", ".bmp", ".gif"))
        ]


def pending_thumb(window, attachment, pixmap, on_remove):
    """A thumbnail in the composer with a small remove button."""
    holder = QFrame()
    holder.setFixedSize(THUMB + QSize(0, 26))
    thumb = Thumb(window, attachment, pixmap)
    thumb.setParent(holder)
    thumb.move(0, 0)
    remove = button("Remove", on_remove, "times")
    remove.setParent(holder)
    remove.move(0, THUMB.height() + 2)
    return holder

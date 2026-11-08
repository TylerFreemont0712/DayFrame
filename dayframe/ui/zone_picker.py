"""Searchable time zone drop-down that shows each zone's UTC offset and current local time."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QComboBox, QCompleter

from ..core import timezones as TZ

NONE_LABEL = "None"


class ZonePicker(QComboBox):
    """Editable combo box of IANA zones.

    The full list (about 500 zones) is built when the popup first opens, and the
    times are refreshed each time it opens, so building Settings stays fast. Typing
    filters by any part of the label, for example "tokyo" or "UTC+05:30". zone()
    returns the chosen zone name, or the typed text when it matches no entry, so the
    caller's validation can report an unknown zone.
    """

    def __init__(self, zone="", allow_none=False, parent=None):
        super().__init__(parent)
        self.allow_none = allow_none
        self.loaded = False
        self.setEditable(True)
        self.setInsertPolicy(QComboBox.NoInsert)
        self.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.setMinimumContentsLength(18)
        self.setMaxVisibleItems(16)
        completer = QCompleter(self.model(), self)
        completer.setFilterMode(Qt.MatchContains)
        completer.setCaseSensitivity(Qt.CaseInsensitive)
        completer.setCompletionMode(QCompleter.PopupCompletion)
        completer.activated[str].connect(self._completed)
        self.setCompleter(completer)
        self.set_zone(zone)

    def _label(self, zone):
        if not zone:
            return NONE_LABEL
        try:
            return "%s  %s  ·  %s" % (
                TZ.format_offset(TZ.offset_minutes(zone)),
                zone if "/" in zone and not zone.startswith("Etc/") else TZ.place(zone),
                TZ.local_time(zone),
            )
        except (ValueError, KeyError, OSError):
            return zone

    def load(self):
        """Fill (or refresh) every zone with its current time, keeping the selection."""
        current = self.zone()
        self.blockSignals(True)
        self.clear()
        if self.allow_none:
            self.addItem(NONE_LABEL, "")
        for zone, text in TZ.choices():
            self.addItem(text, zone)
        self.loaded = True
        self.set_zone(current)
        self.blockSignals(False)

    def showPopup(self):
        self.load()
        super().showPopup()
        view = self.view()
        view.setMinimumWidth(max(self.width(), view.sizeHintForColumn(0) + 28))

    def focusInEvent(self, event):
        # Typing should be able to match any zone, not only the one shown.
        if not self.loaded:
            self.load()
        super().focusInEvent(event)

    def _completed(self, text):
        index = self.findText(text)
        if index >= 0:
            self.setCurrentIndex(index)

    def zone(self):
        text = self.currentText().strip()
        if text == NONE_LABEL and self.allow_none:
            return ""
        index = self.findText(text)
        if index >= 0:
            return self.itemData(index) or ""
        return text

    def set_zone(self, zone):
        zone = zone or ""
        index = self.findData(zone)
        if index < 0 and (zone or self.allow_none):
            # Before the full list loads, show just the current zone.
            self.addItem(self._label(zone), zone)
            index = self.count() - 1
        if index >= 0:
            self.setCurrentIndex(index)
        else:
            self.setEditText(zone)

"""Read-only unified diff viewer with theme-aware line coloring."""

from PySide6.QtGui import QColor, QFont, QSyntaxHighlighter, QTextCharFormat
from PySide6.QtWidgets import QPlainTextEdit
from ..theme import CURRENT as C

# Very large patches are still stored whole; the viewer shows the start of them.
MAX_SHOWN = 400_000


class DiffHighlighter(QSyntaxHighlighter):
    def __init__(self, document):
        super().__init__(document)
        added = "#3fa96b" if not C.get("dark", True) else "#7fd49b"
        removed = C["danger"]
        self.formats = {}
        for key, color, bold in (
            ("+", added, False),
            ("-", removed, False),
            ("@", C["accent"], False),
            ("header", C["muted"], True),
        ):
            fmt = QTextCharFormat()
            fmt.setForeground(QColor(color))
            if bold:
                fmt.setFontWeight(QFont.DemiBold)
            self.formats[key] = fmt

    def highlightBlock(self, text):
        if text.startswith(
            ("diff --git", "index ", "--- ", "+++ ", "new file", "deleted file", "similarity")
        ):
            self.setFormat(0, len(text), self.formats["header"])
        elif text.startswith("@@"):
            self.setFormat(0, len(text), self.formats["@"])
        elif text.startswith("+"):
            self.setFormat(0, len(text), self.formats["+"])
        elif text.startswith("-"):
            self.setFormat(0, len(text), self.formats["-"])


class DiffView(QPlainTextEdit):
    def __init__(self, text="", placeholder="Select changes to see their diff."):
        super().__init__()
        self.setObjectName("diffView")
        self.setReadOnly(True)
        self.setLineWrapMode(QPlainTextEdit.NoWrap)
        self.setAccessibleName("Diff")
        self.setPlaceholderText(placeholder)
        font = QFont(C.get("mono", "Consolas"))
        font.setStyleHint(QFont.Monospace)
        self.setFont(font)
        self.highlighter = DiffHighlighter(self.document())
        self.show_diff(text)

    def show_diff(self, text):
        if len(text) > MAX_SHOWN:
            text = text[:MAX_SHOWN] + "\n… (diff truncated for display)"
        self.setPlainText(text)

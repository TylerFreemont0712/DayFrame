"""QThreadPool worker that reports results back on the GUI thread."""
from __future__ import annotations
from PySide6.QtCore import QObject, QRunnable, Signal


class WorkerSignals(QObject):
    done=Signal(object); failed=Signal(str)


class Worker(QRunnable):
    def __init__(self,fn):
        super().__init__(); self.fn=fn; self.signals=WorkerSignals()
    def run(self):
        try: self.signals.done.emit(self.fn())
        except Exception as exc: self.signals.failed.emit(str(exc))

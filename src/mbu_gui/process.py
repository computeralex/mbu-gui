from __future__ import annotations

from PySide6.QtCore import QObject, QProcess, Signal


class LineProcess(QObject):
    line = Signal(str)
    finished = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._proc = QProcess(self)
        self._buf = ""
        self._finished_emitted = False
        self._proc.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self._proc.readyReadStandardOutput.connect(self._on_ready)
        self._proc.finished.connect(self._on_finished)
        self._proc.errorOccurred.connect(self._on_error)

    def start(self, argv: list[str]) -> None:
        self._buf = ""
        self._finished_emitted = False
        if not argv:
            self._emit_finished(-1)
            return
        self._proc.start(argv[0], argv[1:])

    def _on_ready(self) -> None:
        data = bytes(self._proc.readAllStandardOutput()).decode("utf-8", errors="replace")
        if not data:
            return
        self._buf += data
        while "\n" in self._buf:
            line, self._buf = self._buf.split("\n", 1)
            if line.endswith("\r"):
                line = line[:-1]
            self.line.emit(line)

    def _on_finished(self, exit_code: int, exit_status: QProcess.ExitStatus) -> None:
        self._flush()
        code = -1 if exit_status == QProcess.ExitStatus.CrashExit else exit_code
        self._emit_finished(code)

    def _on_error(self, error: QProcess.ProcessError) -> None:
        if error == QProcess.ProcessError.FailedToStart:
            self._flush()
            self._emit_finished(-1)

    def _flush(self) -> None:
        if self._proc.bytesAvailable():
            self._on_ready()
        if self._buf:
            leftover = self._buf
            self._buf = ""
            if leftover.endswith("\r"):
                leftover = leftover[:-1]
            self.line.emit(leftover)

    def _emit_finished(self, code: int) -> None:
        if self._finished_emitted:
            return
        self._finished_emitted = True
        self.finished.emit(code)

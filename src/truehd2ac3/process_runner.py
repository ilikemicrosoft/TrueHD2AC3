from __future__ import annotations

import subprocess

from truehd2ac3.models import CommandResult


class ProcessRunner:
    def __init__(self) -> None:
        self._process: subprocess.Popen[str] | None = None

    def run(self, command: list[str], on_output) -> CommandResult:
        popen_kwargs = {
            "stdout": subprocess.PIPE,
            "stderr": subprocess.PIPE,
            "text": True,
            "encoding": "utf-8",
            "errors": "replace",
        }
        if subprocess._mswindows:
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE
            popen_kwargs["startupinfo"] = startupinfo
            popen_kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW

        self._process = subprocess.Popen(
            command,
            **popen_kwargs,
        )
        stdout_lines: list[str] = []
        stderr_lines: list[str] = []

        assert self._process.stdout is not None
        for line in self._process.stdout:
            clean = line.rstrip("\r\n")
            stdout_lines.append(clean)
            on_output(clean)

        assert self._process.stderr is not None
        for line in self._process.stderr:
            clean = line.rstrip("\r\n")
            stderr_lines.append(clean)
            on_output(clean)

        return_code = self._process.wait()
        cancelled = return_code == 130
        self._process = None
        return CommandResult(
            return_code=return_code,
            stdout_lines=stdout_lines,
            stderr_lines=stderr_lines,
            cancelled=cancelled,
        )

    def cancel(self) -> None:
        if self._process is not None and self._process.poll() is None:
            self._process.terminate()

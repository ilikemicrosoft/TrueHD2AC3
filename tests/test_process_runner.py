from __future__ import annotations

import subprocess

from truehd2ac3.process_runner import ProcessRunner


class FakeStream:
    def __iter__(self):
        return iter(())


class FakeProcess:
    def __init__(self):
        self.stdout = FakeStream()
        self.stderr = FakeStream()

    def wait(self) -> int:
        return 0

    def poll(self):
        return 0


def test_process_runner_hides_console_window_on_windows(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_popen(*args, **kwargs):
        captured.update(kwargs)
        return FakeProcess()

    monkeypatch.setattr(subprocess, "Popen", fake_popen)

    runner = ProcessRunner()
    result = runner.run(["cmd"], lambda line: None)

    assert result.return_code == 0
    assert captured["creationflags"] == subprocess.CREATE_NO_WINDOW
    startupinfo = captured["startupinfo"]
    assert startupinfo.dwFlags & subprocess.STARTF_USESHOWWINDOW
    assert startupinfo.wShowWindow == subprocess.SW_HIDE

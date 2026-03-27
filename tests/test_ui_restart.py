from __future__ import annotations

from unittest.mock import patch

import pytest

pytest.importorskip("PyQt6")


def test_restart_command_filters_macos_psn_arg():
    from talky import ui

    with (
        patch.object(ui.sys, "executable", "/Applications/Talky.app/Contents/MacOS/Talky"),
        patch.object(
            ui.sys,
            "argv",
            [
                "/Applications/Talky.app/Contents/MacOS/Talky",
                "-psn_0_12345",
                "--flag",
            ],
        ),
    ):
        cmd = ui._restart_command()
    assert cmd == ["/Applications/Talky.app/Contents/MacOS/Talky", "--flag"]


def test_restart_current_process_falls_back_to_subprocess():
    from talky import ui

    with (
        patch.object(ui.sys, "executable", "/usr/local/bin/python3"),
        patch.object(ui.sys, "argv", ["main.py", "--debug"]),
        patch.object(ui.os, "execv", side_effect=OSError("exec failed")),
        patch.object(ui.subprocess, "Popen") as mock_popen,
    ):
        ok = ui._restart_current_process("unit-test")
    assert ok is True
    mock_popen.assert_called_once_with(["/usr/local/bin/python3", "--debug"], close_fds=True)


def test_restart_current_process_returns_false_when_all_paths_fail():
    from talky import ui

    with (
        patch.object(ui.sys, "executable", "/usr/local/bin/python3"),
        patch.object(ui.sys, "argv", ["main.py"]),
        patch.object(ui.os, "execv", side_effect=OSError("exec failed")),
        patch.object(ui.subprocess, "Popen", side_effect=OSError("spawn failed")),
    ):
        ok = ui._restart_current_process("unit-test")
    assert ok is False


def test_bundled_app_restart_uses_open_via_launchservices():
    """In frozen .app mode, restart should use `open /path/to/App.app` not execv."""
    from talky import ui

    with (
        patch.object(ui.sys, "frozen", True, create=True),
        patch.object(
            ui.sys,
            "executable",
            "/Applications/Talky.app/Contents/MacOS/Talky",
        ),
        patch.object(ui.sys, "argv", ["/Applications/Talky.app/Contents/MacOS/Talky"]),
        patch.object(ui.subprocess, "Popen") as mock_popen,
        patch.object(ui.os, "execv") as mock_execv,
    ):
        ok = ui._restart_current_process("unit-test-bundled")
    assert ok is True
    mock_execv.assert_not_called()
    popen_args = mock_popen.call_args
    shell_cmd = popen_args[0][0]
    assert shell_cmd[0] == "/bin/sh"
    script = shell_cmd[2]
    assert "open" in script
    assert "Talky.app" in script


def test_find_app_bundle_path():
    from talky import ui

    with patch.object(
        ui.sys,
        "executable",
        "/Applications/Talky.app/Contents/MacOS/Talky",
    ):
        result = ui._find_app_bundle_path()
    assert result is not None
    assert result.name == "Talky.app"

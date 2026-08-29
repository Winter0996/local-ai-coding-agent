
import pytest

from app.validation import security, service


def _write_passing_pytest_repo(tmp_path):
    (tmp_path / "pyproject.toml").write_text("[tool.pytest.ini_options]\n", encoding="utf-8")
    (tmp_path / "test_sample.py").write_text(
        "def test_ok():\n    assert 1 + 1 == 2\n", encoding="utf-8"
    )
    return tmp_path


def _write_failing_pytest_repo(tmp_path):
    (tmp_path / "pyproject.toml").write_text("[tool.pytest.ini_options]\n", encoding="utf-8")
    (tmp_path / "test_sample.py").write_text(
        "def test_fails():\n    assert 1 + 1 == 3\n", encoding="utf-8"
    )
    return tmp_path


def test_detect_available_commands_python_repo(tmp_path):
    _write_passing_pytest_repo(tmp_path)
    available = security.detect_available_commands(tmp_path)
    assert "pytest" in available
    assert "npm-test" not in available


def test_detect_available_commands_node_repo(tmp_path):
    (tmp_path / "package.json").write_text("{}", encoding="utf-8")
    available = security.detect_available_commands(tmp_path)
    assert "npm-test" in available
    assert "pytest" not in available


def test_detect_available_commands_empty_repo(tmp_path):
    assert security.detect_available_commands(tmp_path) == []


def test_run_command_rejects_unknown_key(tmp_path):
    with pytest.raises(service.UnknownCommandError):
        service.run_command(tmp_path, "rm -rf /")  # not a real key, must be rejected outright


def test_run_pytest_passes_on_passing_repo(tmp_path):
    _write_passing_pytest_repo(tmp_path)

    result = service.run_command(tmp_path, "pytest")

    assert result.exit_code == 0
    assert result.timed_out is False
    assert "1 passed" in result.stdout or "1 passed" in result.stderr


def test_run_pytest_fails_on_failing_repo(tmp_path):
    _write_failing_pytest_repo(tmp_path)

    result = service.run_command(tmp_path, "pytest")

    assert result.exit_code != 0
    assert result.timed_out is False


def test_run_command_strips_app_secrets_from_subprocess_env(tmp_path, monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "should-never-leak-to-subprocess")
    (tmp_path / "pyproject.toml").write_text("[tool.pytest.ini_options]\n", encoding="utf-8")
    # A test that would FAIL if JWT_SECRET leaked through — proves the
    # stripping is real, not just asserted in isolation from run_command().
    (tmp_path / "test_env_leak.py").write_text(
        "import os\n\n"
        "def test_secret_not_present():\n"
        "    assert 'JWT_SECRET' not in os.environ\n",
        encoding="utf-8",
    )

    result = service.run_command(tmp_path, "pytest")

    assert result.exit_code == 0, result.stdout + result.stderr


def test_run_command_never_executes_shell_string(tmp_path):
    """SECURITY INVARIANT: run_command only ever accepts a key into
    ALLOWED_COMMANDS, never an argv/string built from caller input. This
    test documents and locks in that contract — if someone ever changes
    run_command's signature to accept a raw command, this test (and the
    reasoning behind it) should be revisited."""
    import inspect

    sig = inspect.signature(service.run_command)
    assert list(sig.parameters.keys()) == ["root", "command_key"]
    # command_key is validated against a fixed dict inside run_command;
    # confirm the dict itself contains no shell metacharacters anywhere.
    for argv in security.ALLOWED_COMMANDS.values():
        for part in argv:
            assert ";" not in part
            assert "&&" not in part
            assert "|" not in part


def test_max_output_bytes_is_reasonable():
    assert 0 < security.MAX_OUTPUT_BYTES <= 1_000_000


def test_timeout_is_reasonable():
    assert 0 < security.TIMEOUT_SECONDS <= 600
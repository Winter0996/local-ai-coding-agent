import os

import pytest

from app.filesystem import service


def test_browse_defaults_to_home_directory(monkeypatch, tmp_path):
    monkeypatch.setattr(service.Path, "home", classmethod(lambda cls: tmp_path))
    (tmp_path / "Projects").mkdir()
    (tmp_path / "Documents").mkdir()

    result = service.browse(None)

    assert result.path == str(tmp_path)
    names = {e.name for e in result.entries}
    assert "Projects" in names
    assert "Documents" in names


def test_browse_lists_subdirectories_of_given_path(tmp_path):
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    (tmp_path / "a_file.txt").write_text("not a dir", encoding="utf-8")

    result = service.browse(str(tmp_path))

    names = sorted(e.name for e in result.entries)
    assert names == ["a", "b"]  # file excluded, only directories


def test_browse_entries_sorted_case_insensitively(tmp_path):
    (tmp_path / "Zebra").mkdir()
    (tmp_path / "apple").mkdir()

    result = service.browse(str(tmp_path))

    assert [e.name for e in result.entries] == ["apple", "Zebra"]


def test_browse_reports_parent_directory(tmp_path):
    child = tmp_path / "child"
    child.mkdir()

    result = service.browse(str(child))

    assert result.parent == str(tmp_path)


def test_browse_raises_for_nonexistent_path(tmp_path):
    with pytest.raises(service.PathNotFoundError):
        service.browse(str(tmp_path / "does-not-exist"))


def test_browse_raises_for_a_file_not_a_directory(tmp_path):
    file_path = tmp_path / "file.txt"
    file_path.write_text("hi", encoding="utf-8")

    with pytest.raises(service.PathNotFoundError):
        service.browse(str(file_path))


def test_browse_skips_unreadable_entries_without_crashing(tmp_path):
    readable = tmp_path / "readable"
    readable.mkdir()
    unreadable = tmp_path / "unreadable"
    unreadable.mkdir()

    if os.name != "nt":
        unreadable.chmod(0)
        try:
            result = service.browse(str(tmp_path))
            names = {e.name for e in result.entries}
            assert "readable" in names
        finally:
            unreadable.chmod(0o755)  # restore so tmp_path cleanup can remove it
    else:
        # Windows permission bits behave differently; just confirm normal
        # listing doesn't crash on this platform.
        result = service.browse(str(tmp_path))
        assert {"readable", "unreadable"}.issubset({e.name for e in result.entries})


def test_list_roots_posix(monkeypatch):
    monkeypatch.setattr(service.os, "name", "posix")
    roots = service.list_roots()
    assert roots == [service.DirEntry(name="/", path="/")]


def test_list_roots_windows(monkeypatch):
    monkeypatch.setattr(service.os, "name", "nt")
    monkeypatch.setattr(
        service.os.path, "exists", lambda p: p in ("C:\\", "D:\\")
    )
    roots = service.list_roots()
    assert [r.path for r in roots] == ["C:\\", "D:\\"]
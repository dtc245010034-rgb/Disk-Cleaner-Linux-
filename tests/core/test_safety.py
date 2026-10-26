import pytest

from disk_cleaner.core.safety import SafetyError, assert_deletable, is_user_content


@pytest.fixture
def home(tmp_path):
    h = tmp_path / "home"
    for d in ("Documents", ".cache", "proj/node_modules"):
        (h / d).mkdir(parents=True)
    (h / "proj" / ".git").mkdir()
    return h


def test_allows_child_of_allowed_root(home):
    target = home / ".cache" / "x"
    target.mkdir()
    assert assert_deletable(target, [home / ".cache"], home) == target.resolve()


def test_rejects_outside_roots(home, tmp_path):
    other = tmp_path / "other"
    other.mkdir()
    with pytest.raises(SafetyError):
        assert_deletable(other, [home / ".cache"], home)


def test_rejects_home_itself_and_documents(home):
    with pytest.raises(SafetyError):
        assert_deletable(home, [home], home)
    with pytest.raises(SafetyError):
        assert_deletable(home / "Documents", [home], home)


def test_rejects_ancestor_of_blocked_path(home, tmp_path):
    with pytest.raises(SafetyError):
        assert_deletable(tmp_path, [tmp_path], home)


def test_rejects_project_root_but_allows_its_node_modules(home):
    with pytest.raises(SafetyError):
        assert_deletable(home / "proj", [home], home)
    assert assert_deletable(home / "proj" / "node_modules", [home], home)


def test_check_project_false_allows_dir_with_package_json(home):
    d = home / ".cache" / "x"
    d.mkdir()
    (d / "package.json").write_text("{}")
    assert_deletable(d, [home / ".cache"], home, check_project=False)
    with pytest.raises(SafetyError):
        assert_deletable(d, [home / ".cache"], home)


def test_symlink_escape_is_rejected(home):
    link = home / ".cache" / "link"
    link.symlink_to(home / "Documents")
    with pytest.raises(SafetyError):
        assert_deletable(link, [home / ".cache"], home)


def test_is_user_content(home):
    assert is_user_content(home / "proj" / "node_modules", home)
    assert not is_user_content(home / ".config" / "x", home)
    assert not is_user_content(home / "snap" / "code", home)
    assert not is_user_content(home, home)

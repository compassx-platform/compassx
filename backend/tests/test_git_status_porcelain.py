"""Git porcelain paths must survive a leading status space, including deletions."""
import pytest

from app.services.omnigent_dev_service import git_status_from_porcelain, include_git_only_files, safe_repo_path


def test_unstaged_edit_keeps_the_full_path():
    statuses = git_status_from_porcelain(" M src/app.py\n?? new.txt\nA  added.py\nD  gone.py\nR  old.py -> renamed.py\n")
    assert statuses["src/app.py"] == "modified"
    assert statuses["new.txt"] == "untracked"
    assert statuses["added.py"] == "added"
    assert statuses["gone.py"] == "deleted"
    assert statuses["renamed.py"] == "added"
    assert "rc/app.py" not in statuses


def test_deleted_file_is_added_when_it_is_not_on_disk():
    files = include_git_only_files(
        [{"path": "src/app.py", "name": "app.py", "git_status": "modified"}],
        {"src/app.py": "modified", "src/gone.py": "deleted"},
    )
    deleted = next(item for item in files if item["path"] == "src/gone.py")
    assert deleted["git_status"] == "deleted"
    assert deleted["name"] == "gone.py"
    assert len(files) == 2


def test_repo_path_rejects_parent_traversal():
    assert safe_repo_path("src/app.py") == "src/app.py"
    with pytest.raises(ValueError):
        safe_repo_path("../secret")

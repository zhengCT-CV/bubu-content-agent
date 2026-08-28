from __future__ import annotations

from pathlib import Path

import pytest

from mcp_server.app.adapters.wechat_workspace import WorkspaceAdapter
from tests.helpers import build_wechat_fixture


def adapter(tmp_path: Path) -> WorkspaceAdapter:
    root = build_wechat_fixture(tmp_path / "ops")
    return WorkspaceAdapter(root, "secret", tmp_path / "state.sqlite3")


def test_writeback_requires_approval_and_secret(tmp_path: Path) -> None:
    target = adapter(tmp_path)
    with pytest.raises(PermissionError):
        target.approved_markdown_write(
            operation="append_retro",
            relative_path="drafts/demo-article/article_record.md",
            heading="复盘",
            markdown="内容",
            idempotency_key="one",
            approved=False,
            approval_secret="secret",
        )


@pytest.mark.parametrize(
    "path",
    ["../outside.md", "data/raw.md", "README.md", "knowledge/other.md"],
)
def test_writeback_path_allowlist(tmp_path: Path, path: str) -> None:
    target = adapter(tmp_path)
    with pytest.raises(PermissionError):
        target.approved_markdown_write(
            operation="append_retro",
            relative_path=path,
            heading="复盘",
            markdown="内容",
            idempotency_key=f"path:{path}",
            approved=True,
            approval_secret="secret",
            create_if_missing=True,
        )


def test_writeback_is_idempotent(tmp_path: Path) -> None:
    target = adapter(tmp_path)
    kwargs = dict(
        operation="append_retro",
        relative_path="drafts/demo-article/article_record.md",
        heading="复盘",
        markdown="只出现一次",
        idempotency_key="same-key",
        approved=True,
        approval_secret="secret",
    )
    assert target.approved_markdown_write(**kwargs)["applied"] is True
    assert target.approved_markdown_write(**kwargs)["duplicate"] is True
    content = (target.workspace / "drafts/demo-article/article_record.md").read_text(encoding="utf-8")
    assert content.count("只出现一次") == 1

from __future__ import annotations

from mcp_server.app.adapters.wechat_workspace import WorkspaceAdapter


def test_title_normalization_ignores_width_spaces_and_punctuation() -> None:
    assert WorkspaceAdapter.normalize_title(" 你好，世界！ ") == WorkspaceAdapter.normalize_title("你好 世界")

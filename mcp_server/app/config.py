from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class McpEnvironment(BaseSettings):
    """从项目 .env 读取 MCP 配置，显式系统环境变量仍拥有最高优先级。"""

    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    wechat_workspace_path: Path = Path(r"C:\Users\10534\Documents\New project 2")
    writeback_approval_secret: str = Field(default="development-only-change-me", repr=False)
    mcp_host: str = "127.0.0.1"
    mcp_port: int = 8100
    mcp_state_path: Path | None = None


@dataclass(frozen=True, slots=True)
class McpSettings:
    workspace: Path
    approval_secret: str
    host: str = "127.0.0.1"
    port: int = 8100
    state_path: Path = Path(__file__).resolve().parents[1] / ".runtime" / "idempotency.sqlite3"


def get_mcp_settings() -> McpSettings:
    environment = McpEnvironment()
    return McpSettings(
        workspace=environment.wechat_workspace_path,
        approval_secret=environment.writeback_approval_secret,
        host=environment.mcp_host,
        port=environment.mcp_port,
        state_path=(
            environment.mcp_state_path
            or Path(__file__).resolve().parents[1] / ".runtime" / "idempotency.sqlite3"
        ),
    )

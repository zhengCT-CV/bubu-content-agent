from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """集中读取配置；密钥永远只从环境变量进入进程。"""

    model_config = SettingsConfigDict(env_file=(".env", "../.env"), env_file_encoding="utf-8", extra="ignore")

    app_mode: Literal["demo", "local"] = "demo"
    app_host: str = "127.0.0.1"
    app_port: int = 8000
    frontend_origin: str = "http://localhost:5173"
    log_level: str = "INFO"

    database_url: str = "postgresql+psycopg://bubu:bubu@127.0.0.1:5432/bubu_content"
    checkpoint_database_url: str = "postgresql://bubu:bubu@127.0.0.1:5432/bubu_checkpoints"
    redis_url: str = "redis://127.0.0.1:6379/0"
    mcp_server_url: str = "http://127.0.0.1:8100/mcp"

    text_model_provider: Literal["deepseek", "demo"] = "deepseek"
    deepseek_api_key: str | None = Field(default=None, repr=False)
    deepseek_model: str = "deepseek-chat"
    deepseek_base_url: str = "https://api.deepseek.com"
    dashscope_api_key: str | None = Field(default=None, repr=False)
    dashscope_embedding_model: str = "text-embedding-v4"
    dashscope_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"

    wechat_workspace_path: Path = Path(r"C:\Users\10534\Documents\New project 2")
    writeback_approval_secret: str = Field(default="development-only-change-me", repr=False)
    reviewer_max_reworks: int = 2
    retrieval_limit: int = 8

    @property
    def uses_external_services(self) -> bool:
        return self.app_mode == "local"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()

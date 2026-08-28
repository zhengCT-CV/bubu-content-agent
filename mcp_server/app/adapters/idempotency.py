from __future__ import annotations

import sqlite3
import threading
from pathlib import Path


class IdempotencyStore:
    """MCP 独立运行，使用本地 SQLite 防止重复 Markdown 写回。"""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        with sqlite3.connect(self.path) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS applied_operations (
                    idempotency_key TEXT PRIMARY KEY,
                    operation TEXT NOT NULL,
                    target_path TEXT NOT NULL,
                    applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

    def claim(self, key: str, operation: str, target_path: str) -> bool:
        with self._lock, sqlite3.connect(self.path) as connection:
            try:
                connection.execute(
                    "INSERT INTO applied_operations"
                    "(idempotency_key, operation, target_path) VALUES (?, ?, ?)",
                    (key, operation, target_path),
                )
            except sqlite3.IntegrityError:
                return False
        return True

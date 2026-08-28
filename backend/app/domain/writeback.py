from __future__ import annotations

import json
from typing import Any

from app.config import Settings
from app.domain.models import KnowledgeProposal, PublicationInfo
from app.integrations.mcp_client import OperationsGateway


class ApprovedWritebackService:
    """这是唯一能把 Agent 结论传给 MCP 写工具的后端服务。"""

    def __init__(self, operations: OperationsGateway, settings: Settings) -> None:
        self.operations = operations
        self.approval_secret = settings.writeback_approval_secret

    async def apply(
        self,
        *,
        project_id: str,
        thread_id: str,
        publication: PublicationInfo,
        proposals: list[KnowledgeProposal],
        approval_patch: dict[str, Any],
    ) -> list[dict[str, Any]]:
        selected = set(approval_patch.get("proposal_indexes", range(len(proposals))))
        targets = approval_patch.get("knowledge_targets", {})
        recent_records = json.loads(await self.operations.read_resource("wechat://articles/recent") or "[]")
        known_paths = {item.get("article_id"): item.get("path") for item in recent_records}
        results: list[dict[str, Any]] = []
        for index, proposal in enumerate(proposals):
            if index not in selected:
                continue
            idempotency_key = f"{project_id}:{thread_id}:{proposal.target}:{index}"
            if proposal.target == "article_record":
                article_id = publication.article_id or project_id
                relative_path = known_paths.get(article_id) or f"drafts/{article_id}/article_record.md"
                tool = "append_retro" if article_id in known_paths else "create_article_record"
                arguments = {
                    "relative_path": relative_path,
                    "markdown": proposal.markdown,
                    "idempotency_key": idempotency_key,
                    "approved": True,
                    "approval_secret": self.approval_secret,
                }
            elif proposal.target == "weekly_review":
                relative_path = targets.get("weekly_review")
                if not relative_path:
                    results.append(
                        {
                            "applied": False,
                            "reason": "missing_weekly_review_target",
                            "proposal_index": index,
                        }
                    )
                    continue
                tool = "apply_approved_knowledge_update"
                arguments = {
                    "relative_path": relative_path,
                    "heading": proposal.heading,
                    "markdown": proposal.markdown,
                    "idempotency_key": idempotency_key,
                    "approved": True,
                    "approval_secret": self.approval_secret,
                }
            else:
                tool = "apply_approved_knowledge_update"
                arguments = {
                    "relative_path": "knowledge/content_playbook.md",
                    "heading": proposal.heading,
                    "markdown": proposal.markdown,
                    "idempotency_key": idempotency_key,
                    "approved": True,
                    "approval_secret": self.approval_secret,
                }
            results.append(await self.operations.call_tool(tool, arguments))
        return results

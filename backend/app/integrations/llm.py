from __future__ import annotations

import json
import time
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, TypeVar

from langchain_deepseek import ChatDeepSeek
from pydantic import BaseModel

from app.config import Settings
from app.domain.errors import ExternalServiceError
from app.domain.models import (
    CharacterSpec,
    CoverDescription,
    DialogueItem,
    KnowledgeProposal,
    LlmTraceContext,
    LlmTraceRecord,
    PanelPrompt,
    Prediction,
    RetroReport,
    ReviewIssue,
    ReviewResult,
    Storyboard,
    StoryboardPanel,
    TimelineCheck,
    TimelineItem,
    TopicCandidate,
    VisualGlobalSpace,
    VisualHandoffCard,
    VisualPromptPackage,
    utc_now,
)
from app.integrations.retry import external_retry

if TYPE_CHECKING:
    from app.repositories.base import ProjectRepository

T = TypeVar("T", bound=BaseModel)
SCHEMA_REPAIR_ATTEMPTS = 3
SENSITIVE_KEY_PARTS = ("api_key", "apikey", "secret", "password", "authorization", "cookie", "token")


def _schema_error_summary(error: BaseException | None, limit: int = 2000) -> str:
    """保留校验错误末尾的字段定位，避免把整段失败 JSON 再重复进提示词。"""

    if error is None:
        return "解析器没有返回具体校验错误。"
    message = str(error).strip()
    if len(message) <= limit:
        return message
    return "…" + message[-limit:]


def _sensitive_values(value: Any, key: str = "") -> set[str]:
    normalized_key = key.lower().replace("-", "_")
    if key and any(part in normalized_key for part in SENSITIVE_KEY_PARTS):
        return {str(value)} if value not in (None, "") else set()
    if isinstance(value, dict):
        return {
            secret
            for item_key, item_value in value.items()
            for secret in _sensitive_values(item_value, str(item_key))
        }
    if isinstance(value, (list, tuple)):
        return {secret for item in value for secret in _sensitive_values(item)}
    return set()


def _redact_text(value: str, secrets: set[str]) -> str:
    for secret in sorted(secrets, key=len, reverse=True):
        value = value.replace(secret, "***REDACTED***")
    return value


def _redact(value: Any, key: str = "", secrets: set[str] | None = None) -> Any:
    """复制可序列化数据，并按字段名隐藏密钥类信息。"""

    normalized_key = key.lower().replace("-", "_")
    if key and any(part in normalized_key for part in SENSITIVE_KEY_PARTS):
        return "***REDACTED***"
    if isinstance(value, BaseModel):
        return _redact(value.model_dump(mode="json"), secrets=secrets)
    if isinstance(value, dict):
        return {
            str(item_key): _redact(item_value, str(item_key), secrets)
            for item_key, item_value in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [_redact(item, secrets=secrets) for item in value]
    if isinstance(value, str):
        return _redact_text(value, secrets or set())
    if value is None or isinstance(value, (int, float, bool)):
        return value
    return str(value)


def _raw_content(result: dict[str, Any], secrets: set[str]) -> str | None:
    raw = result.get("raw")
    if raw is None:
        return None
    content = getattr(raw, "content", raw)
    if isinstance(content, str):
        return _redact_text(content, secrets)
    return json.dumps(_redact(content, secrets=secrets), ensure_ascii=False, default=str)


def _parsed_output(result: dict[str, Any], secrets: set[str]) -> dict[str, Any] | None:
    parsed = result.get("parsed")
    if isinstance(parsed, BaseModel):
        return _redact(parsed.model_dump(mode="json"), secrets=secrets)
    if isinstance(parsed, dict):
        return _redact(parsed, secrets=secrets)
    return None


def _usage(result: dict[str, Any]) -> tuple[int | None, int | None, int | None]:
    raw = result.get("raw")
    usage = getattr(raw, "usage_metadata", None) or {}
    metadata = getattr(raw, "response_metadata", None) or {}
    token_usage = metadata.get("token_usage", {}) if isinstance(metadata, dict) else {}
    prompt = usage.get("input_tokens") or token_usage.get("prompt_tokens")
    completion = usage.get("output_tokens") or token_usage.get("completion_tokens")
    total = usage.get("total_tokens") or token_usage.get("total_tokens")
    return prompt, completion, total


async def _persist_trace(
    repository: ProjectRepository | None,
    context: LlmTraceContext | None,
    *,
    provider: str,
    model_name: str,
    schema_name: str,
    attempt: int,
    schema_attempt: int,
    status: str,
    messages: list[tuple[str, str]],
    payload: dict[str, Any],
    latency_ms: int,
    created_at: Any,
    result: dict[str, Any] | None = None,
    error: BaseException | None = None,
) -> None:
    """Trace 写入失败不能反向打断内容生成，因此这里采用 best-effort。"""

    if repository is None or context is None:
        return
    result = result or {}
    secrets = _sensitive_values(payload)
    prompt_tokens, completion_tokens, total_tokens = _usage(result)
    parsing_error = result.get("parsing_error")
    trace_error = error or parsing_error
    try:
        await repository.record_llm_trace(
            LlmTraceRecord(
                **context.model_dump(),
                model_provider=provider,
                model_name=model_name,
                schema_name=schema_name,
                attempt=attempt,
                schema_attempt=schema_attempt,
                status=status,
                messages=[
                    {"role": role, "content": str(_redact(content, secrets=secrets))}
                    for role, content in messages
                ],
                input_payload=_redact(payload, secrets=secrets),
                raw_output=_raw_content(result, secrets),
                parsed_output=_parsed_output(result, secrets),
                error_type=type(trace_error).__name__ if trace_error else None,
                error_message=str(trace_error)[:4000] if trace_error else None,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
                latency_ms=latency_ms,
                created_at=created_at,
            )
        )
    except Exception:
        # 可观测性不能成为业务链路的单点故障；服务日志仍会记录数据库异常。
        return


class TopicCandidateList(BaseModel):
    candidates: list[TopicCandidate]


class ModelGateway(ABC):
    provider: str
    model_name: str

    @abstractmethod
    async def generate_structured(
        self,
        schema: type[T],
        system_prompt: str,
        payload: dict[str, Any],
        *,
        trace_context: LlmTraceContext | None = None,
    ) -> T: ...


class DeepSeekGateway(ModelGateway):
    provider = "deepseek"

    def __init__(self, settings: Settings, trace_repository: ProjectRepository | None = None) -> None:
        if not settings.deepseek_api_key:
            raise ExternalServiceError("local 模式缺少 DEEPSEEK_API_KEY")
        self.model_name = settings.deepseek_model
        self._trace_repository = trace_repository
        self._client = ChatDeepSeek(
            model=settings.deepseek_model,
            api_key=settings.deepseek_api_key,
            api_base=settings.deepseek_base_url,
            temperature=0.6,
            max_retries=0,  # 重试在统一边界处理，避免嵌套重试。
        )

    @external_retry
    async def _invoke_structured(
        self,
        runnable: Any,
        messages: list[tuple[str, str]],
        payload: dict[str, Any],
        trace_context: LlmTraceContext | None,
        schema_name: str,
        schema_attempt: int,
        attempt_counter: dict[str, int],
    ) -> dict[str, Any]:
        """只对网络/服务调用重试；解析修复由 generate_structured 单独控制。"""

        attempt_counter["value"] += 1
        attempt = attempt_counter["value"]
        created_at = utc_now()
        started = time.perf_counter()
        try:
            result = await runnable.ainvoke(messages)
        except Exception as exc:  # SDK 异常类型会随版本变化，在边界统一包装并重试。
            await _persist_trace(
                getattr(self, "_trace_repository", None),
                trace_context,
                provider=self.provider,
                model_name=self.model_name,
                schema_name=schema_name,
                attempt=attempt,
                schema_attempt=schema_attempt,
                status="error",
                messages=messages,
                payload=payload,
                latency_ms=int((time.perf_counter() - started) * 1000),
                created_at=created_at,
                error=exc,
            )
            raise ExternalServiceError(
                "DeepSeek 请求失败", detail={"type": type(exc).__name__}
            ) from exc
        status = "success" if result.get("parsed") is not None else "schema_error"
        await _persist_trace(
            getattr(self, "_trace_repository", None),
            trace_context,
            provider=self.provider,
            model_name=self.model_name,
            schema_name=schema_name,
            attempt=attempt,
            schema_attempt=schema_attempt,
            status=status,
            messages=messages,
            payload=payload,
            latency_ms=int((time.perf_counter() - started) * 1000),
            created_at=created_at,
            result=result,
        )
        return result

    async def generate_structured(
        self,
        schema: type[T],
        system_prompt: str,
        payload: dict[str, Any],
        *,
        trace_context: LlmTraceContext | None = None,
    ) -> T:
        schema_json = json.dumps(schema.model_json_schema(), ensure_ascii=False)
        messages: list[tuple[str, str]] = [
            (
                "system",
                system_prompt
                + "\n\n# 强制输出格式\n"
                + "只输出一个 JSON 对象，不要输出 Markdown、解释或 Schema 之外的字段。"
                + "字段名、嵌套结构和类型必须严格符合下面的 JSON Schema：\n"
                + schema_json,
            ),
            (
                "human",
                "以下是本节点唯一可信的输入 JSON：\n"
                + json.dumps(payload, ensure_ascii=False, default=str),
            ),
        ]
        runnable = self._client.with_structured_output(
            schema,
            method="json_mode",
            include_raw=True,
        )
        last_error: BaseException | None = None
        attempt_counter = {"value": 0}
        for attempt in range(1, SCHEMA_REPAIR_ATTEMPTS + 1):
            result = await self._invoke_structured(
                runnable,
                messages,
                payload,
                trace_context,
                schema.__name__,
                attempt,
                attempt_counter,
            )
            parsed = result.get("parsed")
            if parsed is not None:
                try:
                    return parsed if isinstance(parsed, schema) else schema.model_validate(parsed)
                except Exception as exc:
                    last_error = exc
            else:
                last_error = result.get("parsing_error")

            if attempt < SCHEMA_REPAIR_ATTEMPTS:
                raw = result.get("raw")
                raw_content = getattr(raw, "content", "")
                if not isinstance(raw_content, str):
                    raw_content = json.dumps(raw_content, ensure_ascii=False, default=str)
                messages.extend(
                    [
                        ("assistant", raw_content),
                        (
                            "human",
                            "上一次输出未通过 JSON Schema 校验。请保留合理内容，但严格改用 Schema "
                            "规定的字段名，补齐所有必填字段，删除所有额外字段；仍然只输出 JSON 对象。"
                            "\n\n具体校验错误如下，请只修复这些错误：\n"
                            + _schema_error_summary(last_error),
                        ),
                    ]
                )

        raise ExternalServiceError(
            "DeepSeek 结构化输出失败",
            detail={
                "type": type(last_error).__name__ if last_error else "UnknownParseError",
                "attempts": SCHEMA_REPAIR_ATTEMPTS,
                "schema": schema.__name__,
            },
        )


class DemoModelGateway(ModelGateway):
    """无密钥演示模型：返回稳定结构，方便完整走通审批和回溯。"""

    provider = "demo"
    model_name = "deterministic-demo-v1"

    def __init__(self, trace_repository: ProjectRepository | None = None) -> None:
        self._trace_repository = trace_repository

    async def generate_structured(
        self,
        schema: type[T],
        system_prompt: str,
        payload: dict[str, Any],
        *,
        trace_context: LlmTraceContext | None = None,
    ) -> T:
        schema_json = json.dumps(schema.model_json_schema(), ensure_ascii=False)
        messages = [
            ("system", system_prompt + "\n\n# 输出 JSON Schema\n" + schema_json),
            (
                "human",
                "以下是本节点唯一可信的输入 JSON：\n"
                + json.dumps(payload, ensure_ascii=False, default=str),
            ),
        ]
        created_at = utc_now()
        started = time.perf_counter()
        try:
            output = await self._generate_structured(schema, system_prompt, payload)
        except Exception as exc:
            await _persist_trace(
                self._trace_repository,
                trace_context,
                provider=self.provider,
                model_name=self.model_name,
                schema_name=schema.__name__,
                attempt=1,
                schema_attempt=1,
                status="error",
                messages=messages,
                payload=payload,
                latency_ms=int((time.perf_counter() - started) * 1000),
                created_at=created_at,
                error=exc,
            )
            raise
        await _persist_trace(
            self._trace_repository,
            trace_context,
            provider=self.provider,
            model_name=self.model_name,
            schema_name=schema.__name__,
            attempt=1,
            schema_attempt=1,
            status="success",
            messages=messages,
            payload=payload,
            latency_ms=int((time.perf_counter() - started) * 1000),
            created_at=created_at,
            result={"raw": output.model_dump(mode="json"), "parsed": output},
        )
        return output

    async def _generate_structured(
        self, schema: type[T], system_prompt: str, payload: dict[str, Any]
    ) -> T:
        inspiration = str(
            payload.get("inspiration") or payload.get("selected_topic", {}).get("title") or "日常困境"
        )
        short = inspiration.strip().replace("\n", " ")[:20]

        if schema is TopicCandidateList:
            evidence_ids = [item.get("id") for item in payload.get("evidence", []) if item.get("id")]
            candidates = [
                TopicCandidate(
                    title=f"原来，{short}最难的不是选择",
                    core_conflict="表面上在权衡得失，真正冲突是害怕承担主动选择的代价。",
                    narrative_mechanism="认知反转：把‘没得选’翻转为‘不敢选’。",
                    audience_value="帮助读者识别拖延决定背后的隐性成本。",
                    hook="他把辞职信删了第七次，领导却先叫住了他。",
                    predicted_strength=82,
                    duplicate_risk=28,
                    evidence_ids=evidence_ids[:2],
                ),
                TopicCandidate(
                    title=f"当{short}发生在饭桌上",
                    core_conflict="外部期待与个人真实感受在亲密关系场景中正面碰撞。",
                    narrative_mechanism="身份错位：关心的话被听成了审判。",
                    audience_value="让读者看见关系冲突中双方各自合理的部分。",
                    hook="妈妈只问了一句‘最近还好吗’，他突然放下了筷子。",
                    predicted_strength=78,
                    duplicate_risk=34,
                    evidence_ids=evidence_ids[1:3],
                ),
                TopicCandidate(
                    title=f"关于{short}，先做一个很小的动作",
                    core_conflict="想一次解决人生问题，却被巨大目标压得无法行动。",
                    narrative_mechanism="微行动共鸣：用一个可执行动作替代宏大答案。",
                    audience_value="给出低门槛的情绪出口和行动起点。",
                    hook="她没有辞职，只是在下班前关掉了一个聊天框。",
                    predicted_strength=74,
                    duplicate_risk=22,
                    evidence_ids=evidence_ids[:1],
                ),
            ]
            return schema(candidates=candidates)

        if schema is Storyboard:
            topic = payload.get("selected_topic", {})
            title = topic.get("title", f"关于{short}的一次选择")
            use_v11 = "handoff_card" in system_prompt or "品牌角色不可更改" in system_prompt
            if use_v11:
                characters = [
                    CharacterSpec(
                        name="一二",
                        identity="敏感、略焦虑的一二布布品牌角色",
                        visual_anchor=(
                            "a small white panda-like bear with black ears and black eye patches, "
                            "sensitive, gloomy, expressive and slightly anxious vibe"
                        ),
                    ),
                    CharacterSpec(
                        name="布布",
                        identity="温柔、温暖的一二布布品牌角色",
                        visual_anchor=(
                            "a small round brown bear, gentle, warm and slightly dazed vibe"
                        ),
                    ),
                ]
            else:
                characters = [
                    CharacterSpec(
                        name="布布",
                        identity="普通职场人，正在学习为自己的选择负责",
                        visual_anchor="short dark hair, round glasses, teal cardigan, canvas shoulder bag",
                    )
                ]
            panel_specs = [
                (
                    "钩子",
                    "深夜办公室",
                    "反复删除手机里的草稿",
                    "迟疑",
                    "第七次了。",
                    "手机屏幕特写",
                    "night",
                    ["phone", "desk lamp"],
                ),
                (
                    "建立处境",
                    "空荡工位",
                    "看向仍亮着的同事电脑",
                    "疲惫",
                    "再帮一次就好。",
                    "中景",
                    "night",
                    ["laptop", "coffee cup"],
                ),
                (
                    "冲突出现",
                    "公司电梯",
                    "收到家人的语音消息",
                    "紧绷",
                    "你最近，还好吗？",
                    "肩后镜头",
                    "night",
                    ["phone", "canvas bag"],
                ),
                (
                    "冲突升级",
                    "家中餐桌",
                    "把准备好的解释咽回去",
                    "防御",
                    "我没事，别问了。",
                    "双人侧面中景",
                    "evening",
                    ["rice bowl", "phone"],
                ),
                (
                    "转折",
                    "卧室窗边",
                    "重新打开草稿，只写下一件小事",
                    "平静",
                    "明天，我先拒绝一件不属于我的事。",
                    "俯拍近景",
                    "late night",
                    ["notebook", "pen"],
                ),
                (
                    "收束互动",
                    "次日办公室",
                    "礼貌把文件推回同事桌前",
                    "坚定",
                    "这部分需要你自己完成。",
                    "平视中景",
                    "morning",
                    ["document folder", "canvas bag"],
                ),
            ]
            panels = []
            for index, (
                purpose,
                scene,
                action,
                emotion,
                dialogue,
                camera,
                time_of_day,
                props,
            ) in enumerate(panel_specs, 1):
                dialogue_items = []
                if use_v11 and dialogue:
                    dialogue_items = [
                        DialogueItem(
                            kind="speech",
                            speaker="一二" if index % 2 else "布布",
                            exact_text=dialogue,
                        )
                    ]
                panels.append(
                    StoryboardPanel(
                        index=index,
                        purpose=purpose,
                        scene=scene,
                        action=action,
                        emotion=emotion,
                        dialogue=dialogue,
                        dialogue_items=dialogue_items,
                        camera=camera,
                        time_of_day=time_of_day,
                        props=props,
                    )
                )
            handoff = None
            if use_v11:
                handoff = VisualHandoffCard(
                    time_anchor="从深夜到次日上午，顺序递进",
                    environment_baseline="简化的办公室、家中与窗边生活空间",
                    fixed_props=["phone", "canvas bag"],
                    time_object_strategy="只通过光照表达时间，不显示可读钟表数字",
                    timeline=[
                        TimelineItem(
                            panel_index=panel.index,
                            time_of_day=panel.time_of_day,
                            lighting=f"{panel.time_of_day} ambient lighting",
                        )
                        for panel in panels
                    ],
                    emotional_peak_panel=4,
                    comedy_peak_panel=None,
                    narrative_mechanism=topic.get("narrative_mechanism", "生活观察与微行动反转"),
                    cover_brief="一二握着手机，布布把文件温柔推回；双角色在中央形成紧凑角色团。",
                )
            return schema(
                title=title,
                summary="一个总在等待完美答案的人，先用一次小小的拒绝拿回主动权。",
                interaction_question="你最近最想先拒绝哪一件不属于你的事？",
                characters=characters,
                cover_brief=(
                    "一二握着手机，布布把文件温柔推回；双角色在中央形成紧凑角色团。"
                    if use_v11
                    else "布布一手握着手机、一手推回文件，表情从迟疑转向坚定；主体居中。"
                ),
                panels=panels,
                ending="真正的改变，不一定从离开开始，也可以从不再替别人承担开始。",
                handoff_card=handoff,
            )

        if schema is ReviewResult:
            artifact = payload.get("artifact", {})
            forced = artifact.get("force_review_failure") if isinstance(artifact, dict) else False
            if forced:
                return schema(
                    passed=False,
                    score=62,
                    issues=[
                        ReviewIssue(
                            code="continuity-broken",
                            severity="blocking",
                            message="测试输入要求触发连续性阻断。",
                            suggestion="恢复角色与关键道具的连续定义后重审。",
                        )
                    ],
                    rewrite_instruction="保留核心冲突，修复连续性后重新提交。",
                )
            return schema(passed=True, score=92, issues=[], rewrite_instruction="")

        if schema is VisualPromptPackage:
            storyboard = Storyboard.model_validate(payload["storyboard"])
            use_v11 = "Masterpiece webcomic illustration" in system_prompt
            if use_v11:
                style = (
                    "Masterpiece webcomic illustration, 8k, cute healing chibi comic style, "
                    "thick uniform clean dark outlines, flat pastel colors, minimal soft cel shading, "
                    "large round heads, simple expressive facial features, tiny mouths and oval blush "
                    "cheeks, short stubby limbs, characters as the dominant focal point, extremely "
                    "simplified background made of flat pastel shapes, no fine detail, no realistic "
                    "texture, no photographic depth of field"
                )
                full_bleed = (
                    "full-bleed single illustration filling the entire canvas to all four edges, no "
                    "panel border, no frame line, no white margin, no rounded corner card, no drop "
                    "shadow around the artwork, no multi-panel grid, one single continuous scene only"
                )
                time_clause = (
                    "no clocks, no wall clocks, no alarm clocks, no digital clocks, no watches, no "
                    "visible readable time displays anywhere in the scene"
                )
                background_clause = (
                    "background contains no more than two recognizable scene objects, rendered as "
                    "extremely simple flat silhouettes, everything else reduced to clean pastel "
                    "negative space"
                )
                crop_clause = (
                    "This is a 16:9 master cover composition designed to survive both a centered 1:1 "
                    "crop and a centered 2.35:1 crop. Keep all essential character faces, facial "
                    "expressions, the main interaction, key hand gestures and the key prop inside the "
                    "central approximately 56 percent of the canvas width and central 75 percent of "
                    "the canvas height. Keep the characters as one compact central visual cluster, "
                    "not spread toward opposite sides. Treat the outer approximately 22 percent on "
                    "the left and right and the outer approximately 12 percent on the top and bottom "
                    "as expendable crop zones containing background only. The composition must remain "
                    "complete and readable after either crop, with no cropped face, missing key prop, "
                    "severed key gesture or loss of the main joke or emotional interaction. Do not draw "
                    "crop guides, safe-zone boxes, grids, borders or crop marks."
                )
                no_text = (
                    "no rendered text anywhere, no letters, no Chinese characters, no speech bubbles, "
                    "no logos"
                )
                anchors = {
                    "Yier": (
                        "a small white panda-like bear with black ears and black eye patches, sensitive, "
                        "gloomy, expressive and slightly anxious vibe"
                    ),
                    "Bubu": "a small round brown bear, gentle, warm and slightly dazed vibe",
                }
                bible = "; ".join(f"{name}: {anchor}" for name, anchor in anchors.items())
                panels = []
                for panel in storyboard.panels:
                    dialogue_clauses = []
                    for item in panel.dialogue_items:
                        dialogue_clauses.append(f'exact Chinese text: "{item.exact_text}"')
                        if item.kind == "speech":
                            speaker = "Yier" if item.speaker in {"一二", "Yier"} else "Bubu"
                            dialogue_clauses.append(
                                "include a readable speech bubble in simplified Chinese, "
                                f"the speech bubble tail clearly points to {speaker}"
                            )
                            dialogue_clauses.append(
                                "simple oval speech bubble with a thin dark outline and plain white "
                                "fill, clean readable typography, no rectangular caption box, no "
                                "drop shadow"
                            )
                        else:
                            dialogue_clauses.append(
                                "borderless floating simplified Chinese text integrated naturally "
                                "into clean background negative space"
                            )
                    if not dialogue_clauses:
                        dialogue_clauses.append("no rendered text and no speech bubble in this panel")
                    camera_lower = panel.camera.lower()
                    if "close" in camera_lower or "特写" in panel.camera or "近景" in panel.camera:
                        subject_ratio = "65-75%"
                    elif "medium-wide" in camera_lower or "中远景" in panel.camera:
                        subject_ratio = "45-55%"
                    else:
                        subject_ratio = "55-65%"
                    prompt = ". ".join(
                        [
                            style,
                            bible,
                            background_clause,
                            f"{storyboard.panel_aspect_ratio} single scene",
                            f"{panel.time_of_day} lighting",
                            f"The characters perform one core action: {panel.action}",
                            f"{panel.camera}, the characters occupy {subject_ratio} of the canvas, "
                            f"showing {panel.emotion}",
                            *dialogue_clauses,
                            full_bleed,
                            time_clause,
                        ]
                    )
                    panels.append(
                        PanelPrompt(
                            panel_index=panel.index,
                            description_zh=f"{panel.scene}；{panel.action}；情绪：{panel.emotion}",
                            time_lighting=f"{panel.time_of_day} lighting",
                            camera=panel.camera,
                            subject_ratio=subject_ratio,
                            core_action=panel.action,
                            comic_symbols=[],
                            dialogue_items=panel.dialogue_items,
                            background_objects=panel.props[:2],
                            aspect_ratio=storyboard.panel_aspect_ratio,
                            prompt_en=prompt,
                            negative_prompt_en=(
                                "extra character, inconsistent outfit, duplicate character, extra "
                                "fingers, realistic texture, photographic depth of field, watermark, logo"
                            ),
                            continuity_notes=f"Keep {bible}; preserve props: {', '.join(panel.props)}.",
                        )
                    )
                handoff = storyboard.handoff_card or VisualHandoffCard()
                cover_prompt = ". ".join(
                    [
                        style,
                        bible,
                        storyboard.cover_brief,
                        "one single flat warm apricot brand-color background filling the entire canvas",
                        "compact central character cluster",
                        crop_clause,
                        no_text,
                        full_bleed,
                        time_clause,
                    ]
                )
                return schema(
                    style_prefix=style,
                    character_bible=bible,
                    core_props=handoff.fixed_props,
                    allowed_background_objects=["desk", "window"],
                    global_space=VisualGlobalSpace(
                        environment_en=handoff.environment_baseline,
                        main_palette="warm apricot and flat pastel colors",
                        costumes="Keep the approved outfit unchanged throughout the story",
                        prop_consistency="Keep every fixed prop color, shape, count and size consistent",
                    ),
                    reference_reminders=["角色定妆表", "分镜交接卡", "画风参考图", "首格", "上一格"],
                    timeline_check=TimelineCheck(
                        items=handoff.timeline,
                        monotonic=True,
                        time_object_strategy=handoff.time_object_strategy,
                        notes=handoff.inferred_notes,
                    ),
                    cover_type="双角色互动",
                    cover_background_mode="品牌纯色型",
                    cover_description_zh=CoverDescription(
                        composition_focus="一二和布布组成中央紧凑角色团",
                        character_action="一二握手机，布布把文件温柔推回",
                        emotional_hook="迟疑与温柔坚定形成反差",
                        key_prop="手机与文件",
                        storyboard_relation="重构分镜中的核心选择动作",
                        crop_safety="核心信息位于中央 56% × 75%，外围只有背景",
                    ),
                    cover_crop_safety="通过中心 1:1 与 2.35:1 裁切检查",
                    cover_prompt_en=cover_prompt,
                    cover_negative_prompt_en=(
                        "rendered text, letters, Chinese characters, speech bubbles, logos, cropped face, "
                        "edge-clipped prop, watermark"
                    ),
                    panels=panels,
                )
            style = (
                "editorial Chinese webcomic, clean expressive line art, "
                "warm muted palette, subtle paper texture"
            )
            bible = "; ".join(
                f"{character.name}: {character.visual_anchor}" for character in storyboard.characters
            )
            panels = [
                PanelPrompt(
                    panel_index=panel.index,
                    prompt_en=(
                        f"{style}. {bible}. Scene: {panel.scene}. The character is {panel.action}, "
                        f"showing {panel.emotion}. {panel.camera}, {panel.time_of_day} lighting. "
                        f"Visible props: {', '.join(panel.props)}. Leave clean negative "
                        "space for a later Chinese speech bubble; no rendered text."
                    ),
                    negative_prompt_en=(
                        "readable text, watermark, logo, duplicate character, "
                        "inconsistent outfit, extra fingers"
                    ),
                    continuity_notes=f"Keep {bible}; preserve props: {', '.join(panel.props)}.",
                )
                for panel in storyboard.panels
            ]
            return schema(
                style_prefix=style,
                character_bible=bible,
                cover_prompt_en=(
                    f"{style}. {bible}. {storyboard.cover_brief}. Keep all faces and essential props "
                    "inside the central 70 percent safe area, clean edge space, no rendered text."
                ),
                cover_negative_prompt_en="cropped face, edge-clipped prop, readable text, watermark, logo",
                panels=panels,
            )

        if schema is Prediction:
            return schema(
                expected_reads_24h=900,
                expected_reads_48h=1250,
                expected_share_rate=0.035,
                rationale=["具体场景钩子有利于早期打开", "身份表达型结尾可能带来转发"],
            )

        if schema is RetroReport:
            prediction = payload.get("prediction", {})
            metrics = payload.get("metrics", [])
            latest = metrics[-1] if metrics else {}
            actual = int(latest.get("reads", 0))
            expected = int(prediction.get("expected_reads_24h", 0))
            delta = actual - expected
            return schema(
                verdict=(
                    f"最新阅读量比 24h 预测{'高' if delta >= 0 else '低'} {abs(delta)}；"
                    "当前结论需结合采样时点理解。"
                ),
                prediction_comparison={
                    "expected_reads_24h": expected,
                    "latest_reads": actual,
                    "delta": delta,
                    "latest_hours": latest.get("hours_since_publish"),
                },
                strengths=["开头由具体动作进入，降低了理解成本。"],
                weaknesses=["需要继续验证结尾是否真正贡献分享，而不是只贡献阅读。"],
                next_actions=["下一篇保留具体动作钩子，只改变互动结尾，做单变量比较。"],
                knowledge_proposals=[
                    KnowledgeProposal(
                        target="article_record",
                        heading="Agent 复盘",
                        markdown="本篇最新数据与发布前预测的对比见上；下一篇做结尾单变量验证。",
                        evidence=[str(latest.get("article_id", "demo"))],
                    )
                ],
            )

        raise ExternalServiceError(f"DemoGateway 未实现 Schema：{schema.__name__}")


def build_model_gateway(
    settings: Settings, trace_repository: ProjectRepository | None = None
) -> ModelGateway:
    if settings.app_mode == "demo" or settings.text_model_provider == "demo":
        return DemoModelGateway(trace_repository)
    return DeepSeekGateway(settings, trace_repository)

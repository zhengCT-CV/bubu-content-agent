import { useEffect, useState } from "react";
import { CheckCircle2, Plus, RefreshCw, Trash2 } from "lucide-react";
import type {
  DialogueItem,
  ReviewSummary,
  Storyboard,
  StoryboardPanel,
  VisualHandoffCard,
} from "../../api/types";
import { Badge, Button, Card } from "../../components/ui";

const YIER_ANCHOR = "a small white panda-like bear with black ears and black eye patches, sensitive, gloomy, expressive and slightly anxious vibe";
const BUBU_ANCHOR = "a small round brown bear, gentle, warm and slightly dazed vibe";

function defaultSpeaker(storyboard: Storyboard): DialogueItem["speaker"] {
  const name = storyboard.characters[0]?.name;
  return name === "一二" || name === "Yier" ? "一二" : "布布";
}

function prepareDraft(storyboard: Storyboard): Storyboard {
  const panels = storyboard.panels.map((panel) => ({
    ...panel,
    dialogue_items:
      panel.dialogue_items?.length || !panel.dialogue
        ? panel.dialogue_items ?? []
        : [{ kind: "speech" as const, speaker: defaultSpeaker(storyboard), exact_text: panel.dialogue }],
  }));
  const defaults: VisualHandoffCard = {
    time_anchor: panels[0]?.time_of_day ?? "",
    environment_baseline: panels[0]?.scene ?? "",
    fixed_props: [...new Set(panels.flatMap((panel) => panel.props))],
    time_object_strategy: "禁止未在脚本指定的可读时间",
    timeline: panels.map((panel) => ({ panel_index: panel.index, time_of_day: panel.time_of_day })),
    emotional_peak_panel: panels[Math.floor(panels.length / 2)]?.index ?? null,
    comedy_peak_panel: null,
    narrative_mechanism: "",
    cover_brief: storyboard.cover_brief,
    inferred_notes: ["【推断，请核对】由旧版分镜生成交接卡"],
    conflicts: [],
  };
  const existing = storyboard.handoff_card;
  const handoff: VisualHandoffCard = {
    ...defaults,
    ...existing,
    fixed_props: existing?.fixed_props ?? defaults.fixed_props,
    timeline: panels.map((panel) => ({
      ...(existing?.timeline.find((item) => item.panel_index === panel.index) ?? {}),
      panel_index: panel.index,
      time_of_day: panel.time_of_day,
    })),
    inferred_notes: existing?.inferred_notes ?? defaults.inferred_notes,
    conflicts: existing?.conflicts ?? [],
  };
  return {
    ...storyboard,
    panel_aspect_ratio: storyboard.panel_aspect_ratio ?? "4:3",
    panels,
    handoff_card: handoff,
  };
}

export function StoryboardApproval({
  storyboard,
  review,
  pending,
  onResume,
}: {
  storyboard: Storyboard;
  review?: ReviewSummary;
  pending: boolean;
  onResume: (payload: Record<string, unknown>) => void;
}) {
  const [draft, setDraft] = useState(() => prepareDraft(storyboard));
  useEffect(() => setDraft(prepareDraft(storyboard)), [storyboard]);

  const patchHandoff = <K extends keyof VisualHandoffCard>(key: K, value: VisualHandoffCard[K]) => {
    setDraft((current) => ({
      ...current,
      handoff_card: { ...prepareDraft(current).handoff_card!, [key]: value },
    }));
  };

  const patchPanel = (index: number, patch: Partial<StoryboardPanel>) => {
    setDraft((current) => {
      const panels = current.panels.map((panel) =>
        panel.index === index ? { ...panel, ...patch } : panel,
      );
      const handoff = prepareDraft(current).handoff_card!;
      const timeline = handoff.timeline.map((item) =>
        item.panel_index === index && patch.time_of_day
          ? { ...item, time_of_day: patch.time_of_day }
          : item,
      );
      return { ...current, panels, handoff_card: { ...handoff, timeline } };
    });
  };

  const patchDialogue = (
    panel: StoryboardPanel,
    itemIndex: number,
    patch: Partial<DialogueItem>,
  ) => {
    const items = [...(panel.dialogue_items ?? [])];
    items[itemIndex] = { ...items[itemIndex], ...patch };
    patchPanel(panel.index, {
      dialogue_items: items,
      dialogue: items.map((item) => item.exact_text).join("\n"),
    });
  };

  const addDialogue = (panel: StoryboardPanel, kind: DialogueItem["kind"]) => {
    const item: DialogueItem = {
      kind,
      speaker: kind === "speech" ? defaultSpeaker(draft) : null,
      exact_text: "",
    };
    patchPanel(panel.index, { dialogue_items: [...(panel.dialogue_items ?? []), item] });
  };

  const removeDialogue = (panel: StoryboardPanel, itemIndex: number) => {
    const items = (panel.dialogue_items ?? []).filter((_, index) => index !== itemIndex);
    patchPanel(panel.index, {
      dialogue_items: items,
      dialogue: items.map((item) => item.exact_text).join("\n"),
    });
  };

  const repairBrandCharacters = () => {
    setDraft((current) => {
      const characters = current.characters.map((character) => {
        if (character.name === "一二" || character.name === "Yier") {
          return { ...character, name: "一二", visual_anchor: YIER_ANCHOR };
        }
        if (character.name === "布布" || character.name === "Bubu") {
          return { ...character, name: "布布", visual_anchor: BUBU_ANCHOR };
        }
        return character;
      });
      const hasBrand = characters.some((character) => ["一二", "Yier", "布布", "Bubu"].includes(character.name));
      return {
        ...current,
        characters: hasBrand
          ? characters
          : [
              ...characters,
              { name: "一二", identity: "敏感、略焦虑的一二布布品牌角色", visual_anchor: YIER_ANCHOR },
              { name: "布布", identity: "温柔、温暖的一二布布品牌角色", visual_anchor: BUBU_ANCHOR },
            ],
      };
    });
  };

  const handoff = prepareDraft(draft).handoff_card!;
  const hasEmptyDialogue = draft.panels.some((panel) =>
    panel.dialogue_items?.some((item) => !item.exact_text.trim()),
  );
  return (
    <section>
      <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="label">Human gate 02</p>
          <h2 className="mt-1 text-2xl font-bold">逐格编辑分镜与交接卡</h2>
          <p className="mt-2 text-sm text-slate-500">
            保存后先进行品牌、时间轴和对白确定性校验，再进入 Visual Agent。
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Badge className={review?.passed ? "bg-emerald-100 text-emerald-800" : "bg-amber-100 text-amber-800"}>
            Reviewer {review?.score ?? "—"}
          </Badge>
          <Button variant="secondary" disabled={pending} onClick={() => onResume({ decision: "regenerate" })}>
            <RefreshCw className="h-4 w-4" />按审核意见重做
          </Button>
        </div>
      </div>

      {review?.issues?.length ? (
        <div className="mb-4 space-y-2 rounded-2xl bg-amber-50 p-4 text-sm text-amber-950">
          {review.issues.map((issue, index) => (
            <div key={`${issue.code ?? "issue"}-${index}`}>
              <span className="font-bold">{issue.severity === "blocking" ? "阻断" : "提醒"}</span> · {issue.message}
              {issue.suggestion && <p className="mt-1 text-xs text-amber-800">建议：{issue.suggestion}</p>}
            </div>
          ))}
        </div>
      ) : null}

      <Card className="mb-4">
        <input className="field text-lg font-bold" value={draft.title} onChange={(event) => setDraft({ ...draft, title: event.target.value })} />
        <textarea className="field mt-3 min-h-20" value={draft.summary} onChange={(event) => setDraft({ ...draft, summary: event.target.value })} />
        <div className="mt-4 flex items-center justify-between gap-3"><p className="label">本篇角色锚点</p><Button variant="secondary" onClick={repairBrandCharacters}>应用固定品牌锚点</Button></div>
        <div className="mt-3 grid gap-3 sm:grid-cols-2">
          {draft.characters.map((character) => <div key={character.name} className="rounded-2xl bg-slate-50 p-3 text-xs leading-5"><b>{character.name}</b><br />{character.visual_anchor}</div>)}
        </div>
      </Card>

      <Card className="mb-5 border-sage-300 bg-sage-50/60">
        <div className="flex items-center justify-between">
          <div><p className="label">Visual handoff</p><h3 className="mt-1 text-lg font-bold">分镜交接卡</h3></div>
          <select className="field w-28" value={draft.panel_aspect_ratio ?? "4:3"} onChange={(event) => setDraft({ ...draft, panel_aspect_ratio: event.target.value as "4:3" | "1:1" })}>
            <option value="4:3">正文 4:3</option><option value="1:1">正文 1:1</option>
          </select>
        </div>
        <div className="mt-4 grid gap-4 md:grid-cols-2">
          <label className="text-sm"><span className="label">时间锚点</span><input className="field mt-1" value={handoff.time_anchor} onChange={(event) => patchHandoff("time_anchor", event.target.value)} /></label>
          <label className="text-sm"><span className="label">环境基准</span><input className="field mt-1" value={handoff.environment_baseline} onChange={(event) => patchHandoff("environment_baseline", event.target.value)} /></label>
          <label className="text-sm"><span className="label">叙事机制</span><input className="field mt-1" value={handoff.narrative_mechanism} onChange={(event) => patchHandoff("narrative_mechanism", event.target.value)} /></label>
          <label className="text-sm"><span className="label">固定道具（逗号分隔）</span><input className="field mt-1" value={handoff.fixed_props.join(", ")} onChange={(event) => patchHandoff("fixed_props", event.target.value.split(/[,，]/).map((item) => item.trim()).filter(Boolean))} /></label>
          <label className="text-sm md:col-span-2"><span className="label">时间物件策略</span><input className="field mt-1" value={handoff.time_object_strategy} onChange={(event) => patchHandoff("time_object_strategy", event.target.value)} /></label>
          <label className="text-sm md:col-span-2"><span className="label">封面简报</span><textarea className="field mt-1 min-h-20" value={handoff.cover_brief} onChange={(event) => setDraft((current) => ({ ...current, cover_brief: event.target.value, handoff_card: { ...prepareDraft(current).handoff_card!, cover_brief: event.target.value } }))} /></label>
          <label className="text-sm"><span className="label">情绪最高点</span><input className="field mt-1" type="number" min={1} max={draft.panels.length} value={handoff.emotional_peak_panel ?? ""} onChange={(event) => patchHandoff("emotional_peak_panel", event.target.value ? Number(event.target.value) : null)} /></label>
          <label className="text-sm"><span className="label">喜剧最高点（可空）</span><input className="field mt-1" type="number" min={1} max={draft.panels.length} value={handoff.comedy_peak_panel ?? ""} onChange={(event) => patchHandoff("comedy_peak_panel", event.target.value ? Number(event.target.value) : null)} /></label>
        </div>
        {handoff.inferred_notes.length > 0 && <div className="mt-4 rounded-xl bg-white/70 p-3 text-xs leading-5 text-amber-800">{handoff.inferred_notes.join("；")}</div>}
        {handoff.conflicts.length > 0 && <div className="mt-3 flex items-center justify-between gap-3 rounded-xl bg-red-50 p-3 text-xs text-red-800"><span>{handoff.conflicts.join("；")}</span><Button variant="secondary" onClick={() => patchHandoff("conflicts", [])}>已修复，清除冲突</Button></div>}
      </Card>

      <div className="space-y-4">
        {draft.panels.map((panel) => (
          <Card key={panel.index} className="grid gap-4 lg:grid-cols-[5rem_1fr_1fr]">
            <div><div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-sage-700 text-lg font-bold text-white">{String(panel.index).padStart(2, "0")}</div><p className="mt-2 text-xs font-semibold text-sage-700">{panel.purpose}</p></div>
            <div className="space-y-3">
              <label><span className="label">场景</span><input className="field mt-1" value={panel.scene} onChange={(event) => patchPanel(panel.index, { scene: event.target.value })} /></label>
              <label><span className="label">核心动作</span><textarea className="field mt-1 min-h-20" value={panel.action} onChange={(event) => patchPanel(panel.index, { action: event.target.value })} /></label>
              <div className="flex gap-2"><Button variant="secondary" onClick={() => addDialogue(panel, "speech")}><Plus className="h-3 w-3" />对白</Button><Button variant="secondary" onClick={() => addDialogue(panel, "narration")}><Plus className="h-3 w-3" />旁白</Button></div>
              {(panel.dialogue_items ?? []).map((item, itemIndex) => (
                <div key={itemIndex} className="rounded-2xl bg-slate-50 p-3">
                  <div className="grid gap-2 sm:grid-cols-[8rem_7rem_1fr_auto]">
                    <select className="field" value={item.kind} onChange={(event) => patchDialogue(panel, itemIndex, { kind: event.target.value as DialogueItem["kind"], speaker: event.target.value === "speech" ? item.speaker ?? "一二" : null })}><option value="speech">对白气泡</option><option value="narration">旁白</option><option value="inner_thought">内心</option></select>
                    <select className="field" disabled={item.kind !== "speech"} value={item.speaker ?? ""} onChange={(event) => patchDialogue(panel, itemIndex, { speaker: event.target.value as DialogueItem["speaker"] })}><option value="一二">一二</option><option value="布布">布布</option></select>
                    <input className="field" value={item.exact_text} onChange={(event) => patchDialogue(panel, itemIndex, { exact_text: event.target.value })} placeholder="精确中文原文" />
                    <Button variant="ghost" onClick={() => removeDialogue(panel, itemIndex)}><Trash2 className="h-4 w-4" /></Button>
                  </div>
                  <p className={`mt-2 text-xs ${item.exact_text.length > 12 ? "text-amber-700" : "text-slate-400"}`}>{item.exact_text.length} 字{item.exact_text.length > 12 ? " · 超过 12 字，Reviewer 将提醒但不阻断" : ""}</p>
                </div>
              ))}
            </div>
            <div className="space-y-3">
              <label><span className="label">情绪</span><input className="field mt-1" value={panel.emotion} onChange={(event) => patchPanel(panel.index, { emotion: event.target.value })} /></label>
              <label><span className="label">镜头</span><input className="field mt-1" value={panel.camera} onChange={(event) => patchPanel(panel.index, { camera: event.target.value })} /></label>
              <label><span className="label">时间</span><input className="field mt-1" value={panel.time_of_day} onChange={(event) => patchPanel(panel.index, { time_of_day: event.target.value })} /></label>
              <label><span className="label">道具（逗号分隔）</span><input className="field mt-1" value={panel.props.join(", ")} onChange={(event) => patchPanel(panel.index, { props: event.target.value.split(/[,，]/).map((item) => item.trim()).filter(Boolean) })} /></label>
            </div>
          </Card>
        ))}
      </div>
      <div className="sticky bottom-4 mt-5 flex items-center justify-end gap-3 rounded-full bg-white/90 p-2 shadow-soft backdrop-blur">{hasEmptyDialogue && <span className="text-xs text-red-600">请填写或删除空对白</span>}<Button disabled={pending || hasEmptyDialogue} onClick={() => onResume({ decision: "edit", state_patch: { storyboard: draft } })}><CheckCircle2 className="h-4 w-4" />保存修改并生成 Prompt</Button></div>
    </section>
  );
}

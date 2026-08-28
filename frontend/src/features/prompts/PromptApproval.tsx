import { CheckCircle2, Copy, RefreshCw } from "lucide-react";
import type { VisualPrompts } from "../../api/types";
import { Badge, Button, Card } from "../../components/ui";

export function PromptApproval({
  prompts,
  pending,
  onResume,
}: {
  prompts: VisualPrompts;
  pending: boolean;
  onResume: (payload: Record<string, unknown>) => void;
}) {
  const copy = (value: string) => void navigator.clipboard.writeText(value);
  const cover = prompts.cover_description_zh;
  return (
    <section>
      <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="label">Human gate 03</p>
          <h2 className="mt-1 text-2xl font-bold">逐格 Nano Banana 2 Prompt</h2>
          <p className="mt-2 text-sm text-slate-500">正文直接生成精确中文；封面无字。单格重做不会覆盖其他格或封面。</p>
        </div>
        <Badge className="bg-emerald-100 text-emerald-800">等待你的确认</Badge>
      </div>

      <div className="mb-4 grid gap-4 xl:grid-cols-2">
        <Card>
          <div className="flex items-start justify-between">
            <div><p className="label">画风基准</p><p className="mt-3 text-xs leading-6 text-slate-600">{prompts.style_prefix}</p></div>
            <Button variant="ghost" onClick={() => copy(prompts.style_prefix)}><Copy className="h-4 w-4" /></Button>
          </div>
          <p className="mt-3 rounded-xl bg-slate-50 p-3 text-xs leading-5">{prompts.character_bible}</p>
        </Card>
        <Card>
          <p className="label">参考图准备顺序</p>
          {prompts.reference_reminders?.length ? (
            <ol className="mt-3 space-y-2 text-sm text-slate-600">
              {prompts.reference_reminders.map((item, index) => <li key={item}>{index + 1}. {item}</li>)}
            </ol>
          ) : <p className="mt-3 text-sm text-slate-400">旧版产物没有参考图提醒</p>}
          <p className="mt-3 text-xs text-slate-400">请按顺序在 Nano Banana 2 手动上传；系统不保存附件。</p>
        </Card>
      </div>

      {prompts.global_space && (
        <Card className="mb-4">
          <p className="label">全局空间</p>
          <div className="mt-3 grid gap-3 text-sm md:grid-cols-2">
            <p><b>环境：</b>{prompts.global_space.environment_en}</p><p><b>主色：</b>{prompts.global_space.main_palette}</p>
            <p><b>服装：</b>{prompts.global_space.costumes}</p><p><b>道具：</b>{prompts.global_space.prop_consistency}</p>
          </div>
        </Card>
      )}

      {prompts.timeline_check && (
        <Card className="mb-4">
          <div className="flex items-center justify-between">
            <div><p className="label">时间轴自检</p><h3 className="mt-1 font-bold">{prompts.timeline_check.monotonic ? "时间顺序已确认" : "时间轴需要核对"}</h3></div>
            <Badge>{prompts.timeline_check.monotonic ? "通过" : "冲突"}</Badge>
          </div>
          <div className="mt-3 flex flex-wrap gap-2">{prompts.timeline_check.items.map((item) => <Badge key={item.panel_index}>格 {item.panel_index} · {item.time_of_day}</Badge>)}</div>
          <p className="mt-3 text-xs text-slate-500">{prompts.timeline_check.time_object_strategy}</p>
          {prompts.timeline_check.notes.length > 0 && <p className="mt-2 text-xs text-amber-700">{prompts.timeline_check.notes.join("；")}</p>}
        </Card>
      )}

      <Card className="mb-4 border-coral/20 bg-orange-50/60">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="flex flex-wrap gap-2"><Badge>{prompts.cover_type || "封面"}</Badge><Badge>{prompts.cover_background_mode || "背景模式未记录"}</Badge></div>
            {cover && <div className="mt-3 grid gap-2 text-xs leading-5 text-slate-600 sm:grid-cols-2"><p><b>构图：</b>{cover.composition_focus}</p><p><b>动作：</b>{cover.character_action}</p><p><b>情绪：</b>{cover.emotional_hook}</p><p><b>道具：</b>{cover.key_prop}</p><p><b>正文关系：</b>{cover.storyboard_relation}</p><p><b>裁切：</b>{cover.crop_safety}</p></div>}
            <p className="mt-4 text-sm leading-7 text-slate-700">{prompts.cover_prompt_en}</p>
            <p className="mt-3 text-xs text-slate-500">Negative: {prompts.cover_negative_prompt_en}</p>
          </div>
          <Button variant="ghost" onClick={() => copy(prompts.cover_prompt_en)}><Copy className="h-4 w-4" /></Button>
        </div>
      </Card>

      <div className="space-y-4">
        {prompts.panels.map((panel) => (
          <Card key={panel.panel_index}>
            <div className="flex items-start gap-4">
              <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-ink font-bold text-white">{panel.panel_index}</div>
              <div className="min-w-0 flex-1">
                {panel.description_zh && <p className="text-sm font-medium text-slate-800">{panel.description_zh}</p>}
                <div className="mt-2 flex flex-wrap gap-2 text-xs">{panel.aspect_ratio && <Badge>{panel.aspect_ratio}</Badge>}{panel.camera && <Badge>{panel.camera}</Badge>}{panel.subject_ratio && <Badge>主体 {panel.subject_ratio}</Badge>}{panel.time_lighting && <Badge>{panel.time_lighting}</Badge>}</div>
                {panel.dialogue_items?.length ? <div className="mt-3 space-y-1 rounded-xl bg-orange-50 p-3 text-sm">{panel.dialogue_items.map((item, index) => <p key={index}><b>{item.kind === "speech" ? item.speaker : item.kind === "narration" ? "旁白" : "内心"}：</b>{item.exact_text}</p>)}</div> : null}
                <p className="mt-4 whitespace-pre-wrap text-sm leading-7 text-slate-700">{panel.prompt_en}</p>
                <p className="mt-3 rounded-xl bg-slate-50 p-3 text-xs leading-5 text-slate-500"><b>Negative：</b>{panel.negative_prompt_en}<br /><b>Continuity：</b>{panel.continuity_notes}</p>
              </div>
              <div className="flex shrink-0 flex-col gap-2">
                <Button variant="ghost" onClick={() => copy(panel.prompt_en)}><Copy className="h-4 w-4" /></Button>
                <Button variant="secondary" disabled={pending} onClick={() => onResume({ decision: "regenerate", state_patch: { panel_index: panel.panel_index } })}><RefreshCw className="h-4 w-4" /></Button>
              </div>
            </div>
          </Card>
        ))}
      </div>
      <div className="mt-5 flex justify-end"><Button disabled={pending} onClick={() => onResume({ decision: "approve" })}><CheckCircle2 className="h-4 w-4" />批准全部 Prompt</Button></div>
    </section>
  );
}

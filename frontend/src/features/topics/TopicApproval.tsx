import { useState } from "react";
import { Check, RefreshCw, ShieldAlert, Sparkles } from "lucide-react";
import type { TopicCandidate } from "../../api/types";
import { Badge, Button, Card } from "../../components/ui";

export function TopicApproval({ candidates, pending, onResume }: { candidates: TopicCandidate[]; pending: boolean; onResume: (payload: Record<string, unknown>) => void }) {
  const [selected, setSelected] = useState(candidates[0]?.id ?? "");
  const [customTitle, setCustomTitle] = useState("");

  const submitCustom = () => {
    if (!customTitle.trim()) return;
    onResume({
      decision: "custom",
      custom_topic: {
        title: customTitle.trim(),
        core_conflict: "由用户自定义，下一步分镜中继续具体化。",
        narrative_mechanism: "用户自定义方向",
        audience_value: "由用户判断的目标读者价值",
        hook: "在分镜阶段补充具体动作钩子。",
        predicted_strength: 70,
        duplicate_risk: 0,
        evidence_ids: [],
      },
    });
  };

  return (
    <section>
      <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="label">Human gate 01</p>
          <h2 className="mt-1 text-2xl font-bold">选一个真正想做的方向</h2>
          <p className="mt-2 text-sm text-slate-500">三个候选的叙事机制不同；选中后才会进入分镜。</p>
        </div>
        <Button variant="secondary" disabled={pending} onClick={() => onResume({ decision: "regenerate" })}><RefreshCw className="h-4 w-4" />重做三个方向</Button>
      </div>
      <div className="grid gap-4 lg:grid-cols-3">
        {candidates.map((candidate, index) => (
          <button key={candidate.id} onClick={() => setSelected(candidate.id)} className="text-left">
            <Card className={`h-full transition ${selected === candidate.id ? "border-sage-500 ring-4 ring-sage-100" : "hover:-translate-y-1"}`}>
              <div className="flex items-center justify-between">
                <Badge>方向 {index + 1}</Badge>
                {selected === candidate.id && <Check className="h-5 w-5 text-sage-700" />}
              </div>
              <h3 className="mt-4 text-lg font-bold leading-7">{candidate.title}</h3>
              <p className="mt-3 text-sm leading-6 text-slate-600">{candidate.hook}</p>
              <div className="mt-4 space-y-3 border-t border-sage-100 pt-4 text-xs leading-5 text-slate-500">
                <p><span className="font-semibold text-ink">冲突：</span>{candidate.core_conflict}</p>
                <p><span className="font-semibold text-ink">机制：</span>{candidate.narrative_mechanism}</p>
                <p><span className="font-semibold text-ink">价值：</span>{candidate.audience_value}</p>
              </div>
              <div className="mt-4 flex gap-2">
                <Badge className="bg-sage-50"><Sparkles className="mr-1 inline h-3 w-3" />潜力 {candidate.predicted_strength}</Badge>
                <Badge className="bg-orange-50 text-orange-700"><ShieldAlert className="mr-1 inline h-3 w-3" />重复 {candidate.duplicate_risk}</Badge>
              </div>
            </Card>
          </button>
        ))}
      </div>
      <div className="mt-5 flex flex-col gap-3 rounded-3xl bg-white/55 p-4 sm:flex-row">
        <Button className="sm:w-44" disabled={!selected || pending} onClick={() => onResume({ decision: "approve", selected_candidate_id: selected })}>确认并生成分镜</Button>
        <input className="field" value={customTitle} onChange={(event) => setCustomTitle(event.target.value)} placeholder="或者直接输入你的自定义选题" />
        <Button variant="ghost" disabled={!customTitle.trim() || pending} onClick={submitCustom}>使用自定义</Button>
      </div>
    </section>
  );
}


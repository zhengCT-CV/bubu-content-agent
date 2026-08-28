import { CircleCheck, CircleDot, CircleX } from "lucide-react";
import type { RunEvent } from "../../api/types";
import { formatDate } from "../../lib";

export function RunTimeline({ events }: { events: RunEvent[] }) {
  return <div className="space-y-3">{events.length === 0 && <p className="text-sm text-slate-400">节点事件会实时出现在这里。</p>}{events.slice().reverse().map((event) => <div key={event.id} className="flex gap-3 text-sm"><div className="mt-0.5">{event.event === "run.failed" ? <CircleX className="h-4 w-4 text-red-500" /> : event.event === "run.completed" ? <CircleCheck className="h-4 w-4 text-emerald-600" /> : <CircleDot className="h-4 w-4 text-sage-500" />}</div><div className="min-w-0"><p className="font-medium">{event.event}</p><p className="truncate text-xs text-slate-400">{String(event.data.node_name ?? event.data.stage ?? "workflow")} · {formatDate(event.created_at)}</p></div></div>)}</div>;
}


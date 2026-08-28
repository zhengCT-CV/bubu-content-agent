import { AlertTriangle, BookOpen, Database, FileText } from "lucide-react";
import type { Evidence } from "../../api/types";
import { Badge, EmptyState } from "../../components/ui";

export function EvidenceSidebar({ evidence, degraded }: { evidence: Evidence[]; degraded?: boolean }) {
  return (
    <aside className="surface h-fit p-5 xl:sticky xl:top-6">
      <div className="flex items-center justify-between">
        <div>
          <p className="label">Grounding</p>
          <h2 className="mt-1 text-lg font-bold">证据侧栏</h2>
        </div>
        <BookOpen className="h-5 w-5 text-sage-500" />
      </div>
      {degraded && (
        <div className="mt-4 flex gap-2 rounded-2xl bg-amber-50 p-3 text-xs leading-5 text-amber-800">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
          Embedding 不可用，本次已降级为全文检索。
        </div>
      )}
      <div className="mt-4 space-y-3">
        {!evidence.length && <EmptyState title="尚无证据" body="运行到上下文加载节点后，这里会出现长期、近期、案例与精确指标证据。" />}
        {evidence.map((item) => (
          <details key={item.id} className="rounded-2xl border border-sage-100 bg-white/70 p-4">
            <summary className="cursor-pointer list-none">
              <div className="flex items-start gap-3">
                {item.source_type === "metrics" ? <Database className="mt-0.5 h-4 w-4 text-coral" /> : <FileText className="mt-0.5 h-4 w-4 text-sage-500" />}
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-semibold leading-5">{item.title}</p>
                  <p className="mt-1 truncate text-xs text-slate-400">{item.source_path}</p>
                </div>
                <Badge>{Math.round(item.score * 100)}</Badge>
              </div>
            </summary>
            <p className="mt-3 whitespace-pre-wrap text-xs leading-5 text-slate-600">{item.excerpt}</p>
          </details>
        ))}
      </div>
    </aside>
  );
}


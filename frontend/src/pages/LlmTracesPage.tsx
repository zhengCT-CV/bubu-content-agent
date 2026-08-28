import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  AlertTriangle,
  Check,
  CheckCircle2,
  Clipboard,
  Clock3,
  Code2,
  Cpu,
  FileJson2,
  LoaderCircle,
  RefreshCw,
  ScanSearch,
} from "lucide-react";
import { useParams } from "react-router-dom";
import { api } from "../api/client";
import type { LlmTraceRecord, LlmTraceStatus, LlmTraceSummary } from "../api/types";
import { BackButton } from "../components/BackButton";
import { Badge, Button, Card, EmptyState } from "../components/ui";
import { cn, formatDate } from "../lib";

type DetailTab = "messages" | "input" | "raw" | "parsed" | "error";

const statusLabels: Record<LlmTraceStatus, string> = {
  success: "成功",
  schema_error: "Schema 修复",
  error: "失败",
  legacy: "历史记录",
};

const statusClasses: Record<LlmTraceStatus, string> = {
  success: "bg-emerald-100 text-emerald-800",
  schema_error: "bg-amber-100 text-amber-800",
  error: "bg-red-100 text-red-800",
  legacy: "bg-slate-100 text-slate-700",
};

function formatLatency(value: number) {
  return value >= 1_000 ? `${(value / 1_000).toFixed(1)}s` : `${value}ms`;
}

function jsonText(value: unknown) {
  return JSON.stringify(value, null, 2);
}

function CopyButton({ value }: { value: string }) {
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    await navigator.clipboard.writeText(value);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1_500);
  };
  return <Button variant="ghost" className="px-3 py-2" onClick={() => void copy()}>
    {copied ? <Check className="h-4 w-4" /> : <Clipboard className="h-4 w-4" />}
    {copied ? "已复制" : "复制"}
  </Button>;
}

function CodePanel({ title, value, empty }: { title: string; value: string; empty: string }) {
  return <div className="overflow-hidden rounded-2xl border border-sage-100 bg-slate-950 text-slate-100">
    <div className="flex items-center justify-between border-b border-white/10 px-4 py-2.5">
      <span className="text-xs font-semibold text-slate-300">{title}</span>
      {value && <CopyButton value={value} />}
    </div>
    {value
      ? <pre className="max-h-[62vh] overflow-auto whitespace-pre-wrap break-words p-4 text-xs leading-6">{value}</pre>
      : <p className="p-5 text-sm text-slate-400">{empty}</p>}
  </div>;
}

function TraceDetail({ trace }: { trace: LlmTraceRecord }) {
  const [tab, setTab] = useState<DetailTab>("messages");
  const tabs: Array<{ id: DetailTab; label: string }> = [
    { id: "messages", label: "完整消息" },
    { id: "input", label: "输入 JSON" },
    { id: "raw", label: "原始输出" },
    { id: "parsed", label: "解析输出" },
    { id: "error", label: "错误" },
  ];
  const messagesText = trace.messages.map((message) => `[${message.role.toUpperCase()}]\n${message.content}`).join("\n\n");
  const errorText = trace.error_type || trace.error_message
    ? `${trace.error_type ?? "Error"}\n${trace.error_message ?? ""}`
    : "";

  return <Card className="min-w-0">
    <div className="flex flex-wrap items-start justify-between gap-3">
      <div>
        <div className="flex flex-wrap items-center gap-2">
          <Badge className={statusClasses[trace.status]}>{statusLabels[trace.status]}</Badge>
          <Badge>{trace.model_provider} / {trace.model_name}</Badge>
          <Badge>第 {trace.attempt} 次请求</Badge>
        </div>
        <h2 className="mt-3 text-2xl font-black">{trace.node_name}</h2>
        <p className="mt-1 text-sm text-slate-500">{trace.skill_name} v{trace.skill_version} · {trace.schema_name}</p>
      </div>
      <div className="text-right text-xs leading-6 text-slate-500">
        <div>{formatDate(trace.created_at)}</div>
        <div>{formatLatency(trace.latency_ms)} · {trace.total_tokens ?? "—"} tokens</div>
      </div>
    </div>

    {trace.status === "legacy" && <div className="mt-5 rounded-2xl bg-amber-50 p-4 text-sm leading-6 text-amber-900">
      这是升级 Trace 功能前产生的调用，只保留了解析输出和运行元数据；后续调用会记录完整消息、输入与原始输出。
    </div>}

    <div className="mt-5 grid gap-3 text-xs sm:grid-cols-2 xl:grid-cols-4">
      <div className="rounded-2xl bg-sage-50 p-3"><span className="text-slate-500">Prompt tokens</span><b className="mt-1 block text-base">{trace.prompt_tokens ?? "—"}</b></div>
      <div className="rounded-2xl bg-sage-50 p-3"><span className="text-slate-500">Completion tokens</span><b className="mt-1 block text-base">{trace.completion_tokens ?? "—"}</b></div>
      <div className="rounded-2xl bg-sage-50 p-3"><span className="text-slate-500">Prompt hash</span><b className="mt-1 block truncate font-mono" title={trace.prompt_hash}>{trace.prompt_hash.slice(0, 14)}…</b></div>
      <div className="rounded-2xl bg-sage-50 p-3"><span className="text-slate-500">Schema attempt</span><b className="mt-1 block text-base">{trace.schema_attempt}</b></div>
    </div>

    <div className="mt-5 flex gap-2 overflow-x-auto border-b border-sage-100 pb-3">
      {tabs.map((item) => <button
        key={item.id}
        type="button"
        onClick={() => setTab(item.id)}
        className={cn(
          "shrink-0 rounded-full px-4 py-2 text-xs font-semibold transition",
          tab === item.id ? "bg-sage-800 text-white" : "bg-sage-50 text-sage-800 hover:bg-sage-100",
        )}
      >{item.label}</button>)}
    </div>

    <div className="mt-4">
      {tab === "messages" && <CodePanel title="发送给模型的消息（敏感字段已脱敏）" value={messagesText} empty="历史记录没有保存完整消息。" />}
      {tab === "input" && <CodePanel title="本节点输入 JSON" value={Object.keys(trace.input_payload).length ? jsonText(trace.input_payload) : ""} empty="历史记录只有输入 hash，没有完整输入。" />}
      {tab === "raw" && <CodePanel title="模型原始返回文本" value={trace.raw_output ?? ""} empty="本次调用没有可用的原始输出。" />}
      {tab === "parsed" && <CodePanel title="Schema 解析后的结构化输出" value={trace.parsed_output ? jsonText(trace.parsed_output) : ""} empty="本次调用没有成功解析出结构化结果。" />}
      {tab === "error" && <CodePanel title="调用或 Schema 错误" value={errorText} empty="本次调用没有错误。" />}
    </div>
  </Card>;
}

function TraceListItem({ trace, selected, onSelect }: { trace: LlmTraceSummary; selected: boolean; onSelect: () => void }) {
  return <button
    type="button"
    onClick={onSelect}
    className={cn(
      "w-full rounded-2xl border p-4 text-left transition",
      selected ? "border-sage-600 bg-sage-50 shadow-sm" : "border-white bg-white/65 hover:border-sage-200 hover:bg-white",
    )}
  >
    <div className="flex items-center justify-between gap-2">
      <Badge className={statusClasses[trace.status]}>{statusLabels[trace.status]}</Badge>
      <span className="text-xs text-slate-400">{formatLatency(trace.latency_ms)}</span>
    </div>
    <h3 className="mt-3 truncate font-bold">{trace.node_name}</h3>
    <p className="mt-1 truncate text-xs text-slate-500">{trace.skill_name} v{trace.skill_version}</p>
    <p className="mt-1 truncate font-mono text-[10px] text-slate-400">run {trace.thread_id.slice(0, 8)}</p>
    <div className="mt-3 flex items-center justify-between text-[11px] text-slate-400">
      <span>attempt {trace.attempt}</span><span>{formatDate(trace.created_at)}</span>
    </div>
  </button>;
}

export function LlmTracesPage() {
  const { projectId = "" } = useParams();
  const [selectedTraceId, setSelectedTraceId] = useState<string | null>(null);
  const traces = useQuery({
    queryKey: ["project-llm-traces", projectId],
    queryFn: () => api.getProjectLlmTraces(projectId),
    enabled: Boolean(projectId),
    refetchInterval: 4_000,
  });
  const activeTraceId = selectedTraceId ?? traces.data?.[0]?.id ?? null;
  const detail = useQuery({
    queryKey: ["project-llm-trace", projectId, activeTraceId],
    queryFn: () => api.getProjectLlmTrace(projectId, activeTraceId!),
    enabled: Boolean(projectId && activeTraceId),
  });
  const totalTokens = traces.data?.reduce((sum, trace) => sum + (trace.total_tokens ?? 0), 0) ?? 0;
  const errorCount = traces.data?.filter((trace) => trace.status === "error" || trace.status === "schema_error").length ?? 0;

  return <div className="mx-auto max-w-[1600px] px-5 py-8 lg:px-10">
    <header className="flex flex-wrap items-start justify-between gap-4">
      <div>
        <p className="label">LLM observability</p>
        <h1 className="mt-2 text-4xl font-black">LLM 调用记录</h1>
        <p className="mt-3 max-w-3xl text-sm leading-7 text-slate-500">
          查看每个 Agent 节点实际发送的消息、输入、原始输出、Schema 解析结果、重试和 Token 用量。密钥类字段会在入库前脱敏。
        </p>
      </div>
      <BackButton fallbackTo={`/projects/${projectId}`} label="返回工作台" />
    </header>

    <div className="mt-7 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
      <Card className="flex items-center gap-3"><ScanSearch className="h-5 w-5 text-sage-700" /><div><p className="text-xs text-slate-500">调用记录</p><b className="text-xl">{traces.data?.length ?? 0}</b></div></Card>
      <Card className="flex items-center gap-3"><Code2 className="h-5 w-5 text-sage-700" /><div><p className="text-xs text-slate-500">累计 Tokens</p><b className="text-xl">{totalTokens || "—"}</b></div></Card>
      <Card className="flex items-center gap-3"><AlertTriangle className="h-5 w-5 text-amber-600" /><div><p className="text-xs text-slate-500">修复 / 失败</p><b className="text-xl">{errorCount}</b></div></Card>
      <Card className="flex items-center gap-3"><Cpu className="h-5 w-5 text-sage-700" /><div><p className="text-xs text-slate-500">当前模型</p><b className="text-sm">{traces.data?.[0]?.model_name ?? "—"}</b></div></Card>
    </div>

    {traces.isLoading && <Card className="mt-8 flex items-center justify-center py-16"><LoaderCircle className="h-6 w-6 animate-spin text-sage-700" /></Card>}
    {traces.isError && <Card className="mt-8 border-red-200 bg-red-50 text-red-800"><AlertTriangle className="h-5 w-5" /><p className="mt-2 font-bold">暂时无法读取调用记录</p><Button variant="danger" className="mt-4" onClick={() => void traces.refetch()}><RefreshCw className="h-4 w-4" />重新加载</Button></Card>}
    {traces.data?.length === 0 && <div className="mt-8"><EmptyState title="暂无 LLM 调用" body="当前项目还没有调用模型；页面每 4 秒自动刷新，并汇总所有运行与 Fork。" /></div>}

    {traces.data && traces.data.length > 0 && <div className="mt-8 grid items-start gap-5 xl:grid-cols-[20rem_minmax(0,1fr)]">
      <Card className="max-h-[78vh] overflow-y-auto p-3">
        <div className="mb-3 flex items-center justify-between px-2 py-1">
          <div><p className="label">Trace list</p><p className="mt-1 text-xs text-slate-500">最新调用在前</p></div>
          {traces.isFetching ? <LoaderCircle className="h-4 w-4 animate-spin text-sage-600" /> : <CheckCircle2 className="h-4 w-4 text-emerald-600" />}
        </div>
        <div className="space-y-2">{traces.data.map((trace) => <TraceListItem key={trace.id} trace={trace} selected={trace.id === activeTraceId} onSelect={() => setSelectedTraceId(trace.id)} />)}</div>
      </Card>
      {detail.isLoading && <Card className="flex min-h-96 items-center justify-center"><LoaderCircle className="h-7 w-7 animate-spin text-sage-700" /></Card>}
      {detail.data && <TraceDetail key={detail.data.id} trace={detail.data} />}
      {detail.isError && <Card className="border-red-200 bg-red-50 text-red-800"><AlertTriangle className="h-5 w-5" /><p className="mt-2">调用详情读取失败。</p></Card>}
    </div>}

    <p className="mt-6 flex items-center gap-2 text-xs text-slate-400"><Clock3 className="h-3.5 w-3.5" /><FileJson2 className="h-3.5 w-3.5" />记录保存在本地 PostgreSQL，不会上传到额外的观测平台。</p>
  </div>;
}

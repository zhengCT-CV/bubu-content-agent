import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CircleAlert, CircleX, Clock3, GitFork, History, LoaderCircle, Play, RefreshCw, ScanSearch, Wifi, WifiOff, X } from "lucide-react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api/client";
import { useRunEvents } from "../api/use-run-events";
import { BackButton } from "../components/BackButton";
import { Badge, Button, Card, EmptyState } from "../components/ui";
import { KnowledgeGate } from "../features/approval/KnowledgeGate";
import { PublicationGate } from "../features/approval/PublicationGate";
import { EvidenceSidebar } from "../features/evidence/EvidenceSidebar";
import { PromptApproval } from "../features/prompts/PromptApproval";
import { StoryboardApproval } from "../features/storyboard/StoryboardApproval";
import { RunTimeline } from "../features/timeline/RunTimeline";
import { TopicApproval } from "../features/topics/TopicApproval";
import { useRunStore } from "../stores/run-store";

function Running({ stage }: { stage?: string }) { return <Card className="flex min-h-72 flex-col items-center justify-center text-center"><LoaderCircle className="h-8 w-8 animate-spin text-sage-600" /><h2 className="mt-5 text-xl font-bold">Agent 正在推进工作流</h2><p className="mt-2 text-sm text-slate-500">当前阶段：{stage ?? "初始化"}。结束后会在这里出现人工审批卡片。</p></Card>; }

interface StageTransitionState {
  startedAt: number;
  minVisibleUntil: number;
  sourceCheckpointId?: string;
  sourceInterruptKind?: string;
  title: string;
  detail: string;
  expectedReturnToSameGate: boolean;
}

interface GateReturnNoticeState {
  kind: string;
}

const MIN_TRANSITION_MS = 1_200;

function eventInterruptKind(event: { data: Record<string, unknown> } | undefined) {
  const interrupts = event?.data.interrupts;
  if (!Array.isArray(interrupts)) return undefined;
  const first = interrupts[0];
  if (!first || typeof first !== "object" || !("kind" in first)) return undefined;
  return typeof first.kind === "string" ? first.kind : undefined;
}

function StageTransition({ transition }: { transition: StageTransitionState }) {
  return <Card role="status" aria-live="polite" className="flex min-h-80 flex-col items-center justify-center overflow-hidden text-center">
    <div className="relative flex h-16 w-16 items-center justify-center rounded-full bg-sage-50">
      <div className="absolute inset-0 animate-ping rounded-full bg-sage-200/60" />
      <LoaderCircle className="relative h-8 w-8 animate-spin text-sage-700" />
    </div>
    <p className="label mt-6">Next stage</p>
    <h2 className="mt-2 text-2xl font-black">{transition.title}</h2>
    <p className="mt-3 max-w-xl text-sm leading-7 text-slate-500">{transition.detail}</p>
    <div className="mt-6 flex flex-wrap justify-center gap-2 text-xs">
      <Badge className="bg-emerald-100 text-emerald-800">操作已提交</Badge>
      <Badge>工作流处理中</Badge>
      <Badge>完成后自动出现</Badge>
    </div>
  </Card>;
}

function GateReturnNotice({ kind, blockingMessages, onDismiss }: { kind: string; blockingMessages: string[]; onDismiss: () => void }) {
  const label = kind === "storyboard" ? "分镜" : kind === "visual_prompt" ? "绘图 Prompt" : "当前内容";
  return <Card role="alert" className="mb-5 border-amber-300 bg-amber-50/90">
    <div className="flex items-start gap-3">
      <CircleAlert className="mt-0.5 h-5 w-5 shrink-0 text-amber-700" />
      <div className="min-w-0 flex-1">
        <h2 className="font-bold text-amber-950">校验未通过，已返回{label}修改</h2>
        <p className="mt-1 text-sm leading-6 text-amber-900">
          工作流没有卡住。请先处理下方 Reviewer 标出的阻断问题，再重新保存并继续生成。
        </p>
        {blockingMessages.length > 0 && <div className="mt-3 rounded-xl bg-white/70 p-3 text-xs leading-5 text-amber-950">
          <b>当前有 {blockingMessages.length} 个阻断项：</b>
          <ul className="mt-1 list-disc space-y-1 pl-5">{blockingMessages.slice(0, 4).map((message, index) => <li key={`${message}-${index}`}>{message}</li>)}</ul>
        </div>}
      </div>
      <button type="button" aria-label="关闭提示" className="rounded-lg p-1 text-amber-700 hover:bg-amber-100" onClick={onDismiss}><X className="h-4 w-4" /></button>
    </div>
  </Card>;
}

function FailedRun({ message, pending, onRetry }: { message: string; pending: boolean; onRetry: () => void }) {
  return <Card className="border-red-200 bg-red-50/80 py-10 text-center"><CircleX className="mx-auto h-10 w-10 text-red-600" /><h2 className="mt-4 text-2xl font-black text-red-900">本次工作流已停止</h2><p className="mx-auto mt-3 max-w-2xl text-sm leading-6 text-red-800">{message}</p><p className="mt-2 text-xs text-slate-500">已有 checkpoint 和历史产物不会丢失，可从历史创建分支，或从头重新运行。</p><div className="mt-6 flex flex-wrap justify-center gap-3"><Button variant="danger" disabled={pending} onClick={onRetry}>{pending ? <LoaderCircle className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}从头重试</Button></div></Card>;
}

export function WorkbenchPage() {
  const { projectId = "" } = useParams();
  const queryClient = useQueryClient();
  const project = useQuery({ queryKey: ["project", projectId], queryFn: () => api.getProject(projectId), enabled: Boolean(projectId) });
  const [threadOverride, setThreadOverride] = useState<string | null>(null);
  const [stageTransition, setStageTransition] = useState<StageTransitionState | null>(null);
  const [gateReturnNotice, setGateReturnNotice] = useState<GateReturnNoticeState | null>(null);
  const threadId = threadOverride ?? project.data?.active_thread_id;
  useRunEvents(threadId);
  const connected = useRunStore((state) => state.connected);
  const events = useRunStore((state) => state.events);
  const resetEvents = useRunStore((state) => state.reset);
  useEffect(() => { resetEvents(); }, [threadId, resetEvents]);
  const run = useQuery({ queryKey: ["run", threadId], queryFn: () => api.getRunState(threadId!), enabled: Boolean(threadId), refetchInterval: 4000, retry: false });
  const start = useMutation({ mutationFn: () => api.startRun(projectId), onSuccess: ({ thread_id }) => { setThreadOverride(thread_id); void queryClient.invalidateQueries({ queryKey: ["project", projectId] }); } });
  const resume = useMutation({ mutationFn: (payload: Record<string, unknown>) => api.resume(threadId!, payload), onSuccess: () => setTimeout(() => void queryClient.invalidateQueries({ queryKey: ["run", threadId] }), 400) });
  const publish = useMutation({ mutationFn: (payload: { title: string; published_at: string; article_id?: string; article_url?: string }) => api.publish(projectId, payload), onSuccess: () => { void queryClient.invalidateQueries({ queryKey: ["project", projectId] }); setTimeout(() => void queryClient.invalidateQueries({ queryKey: ["run", threadId] }), 500); } });
  const sync = useMutation({ mutationFn: () => api.syncMetrics(projectId), onSuccess: () => { void queryClient.invalidateQueries({ queryKey: ["metrics", projectId] }); setTimeout(() => void queryClient.invalidateQueries({ queryKey: ["run", threadId] }), 500); } });
  const state = run.data?.values;
  const interrupt = run.data?.interrupts?.[0];
  const failureEvent = [...events].reverse().find((event) => event.event === "run.failed");
  const rawFailureMessage = String(failureEvent?.data.message ?? "工作流执行失败，请查看实时事件或后端日志。");
  const failureMessage = rawFailureMessage.split("\n", 1)[0];
  useEffect(() => {
    if (!stageTransition) return;
    const terminalEvent = [...events].reverse().find((event) =>
      ["interrupt.waiting", "run.completed", "run.failed"].includes(event.event)
      && Date.parse(event.created_at) >= stageTransition.startedAt,
    );
    const reachedCheckpoint = !resume.isPending
      && Boolean(interrupt)
      && Boolean(run.data?.checkpoint_id)
      && run.data?.checkpoint_id !== stageTransition.sourceCheckpointId;
    if (!terminalEvent && !reachedCheckpoint && !run.isError) return;

    const resolvedKind = eventInterruptKind(terminalEvent) ?? interrupt?.kind;
    const returnedToSameGate = (terminalEvent?.event === "interrupt.waiting" || reachedCheckpoint)
      && Boolean(resolvedKind)
      && resolvedKind === stageTransition.sourceInterruptKind;
    const waitMs = run.isError ? 0 : Math.max(0, stageTransition.minVisibleUntil - Date.now());
    const timer = window.setTimeout(() => {
      setStageTransition((current) => current?.startedAt === stageTransition.startedAt ? null : current);
      if (returnedToSameGate && resolvedKind && !stageTransition.expectedReturnToSameGate) {
        setGateReturnNotice({ kind: resolvedKind });
        window.requestAnimationFrame(() => window.scrollTo({ top: 0, behavior: "smooth" }));
      } else {
        setGateReturnNotice(null);
      }
    }, waitMs);
    return () => window.clearTimeout(timer);
  }, [events, interrupt, resume.isPending, run.data?.checkpoint_id, run.isError, stageTransition]);

  useEffect(() => { setStageTransition(null); setGateReturnNotice(null); }, [threadId]);

  const submitResume = (payload: Record<string, unknown>) => {
    const decision = String(payload.decision ?? "");
    const next = interrupt?.kind === "topic" && decision === "regenerate"
      ? {
          title: "正在重新生成选题",
          detail: "Strategy Agent 正在结合你的灵感、运营数据和检索证据，重新生成三个不同叙事方向的候选选题。",
        }
      : interrupt?.kind === "storyboard" && ["regenerate", "reject"].includes(decision)
        ? {
            title: "正在重新生成分镜",
            detail: "Storyboard Agent 正在根据 Reviewer 意见重新设计逐格剧情、对白和视觉交接卡。",
          }
      : interrupt?.kind === "storyboard"
      ? {
          title: "正在生成绘图 Prompt",
          detail: "分镜已提交，Visual Agent 正在直接生成封面与逐格 Prompt；生成完成后会进入人工确认页面。",
        }
      : interrupt?.kind === "topic"
        ? { title: "正在生成分镜", detail: "选题已提交，Storyboard Agent 正在设计逐格剧情、对白和视觉交接卡。" }
        : interrupt?.kind === "visual_prompt"
          ? { title: "正在重新生成绘图 Prompt", detail: "Visual Agent 正按你的选择返工，未指定的分镜和封面不会被覆盖。" }
          : { title: "Agent 正在进入下一阶段", detail: "本次人工操作已提交，工作流正在校验并继续运行。" };
    resume.reset();
    const startedAt = Date.now();
    setGateReturnNotice(null);
    setStageTransition({
      startedAt,
      minVisibleUntil: startedAt + MIN_TRANSITION_MS,
      sourceCheckpointId: run.data?.checkpoint_id,
      sourceInterruptKind: interrupt?.kind,
      expectedReturnToSameGate: ["regenerate", "reject"].includes(decision),
      ...next,
    });
    resume.mutate(payload, { onError: () => setStageTransition(null) });
  };
  const reviewForNotice = gateReturnNotice?.kind === "storyboard"
    ? state?.storyboard_review
    : undefined;
  const blockingMessages = reviewForNotice?.issues
    ?.filter((issue) => issue.severity === "blocking")
    .map((issue) => issue.message) ?? [];
  let content = <Running stage={state?.stage} />;
  if (!threadId) content = <EmptyState title="还没有运行" body="启动后会并行加载最近指标、长期打法、周复盘和相似案例，然后停在第一个选题审批点。" />;
  else if (run.isError) content = <Card><p className="font-semibold text-red-700">运行状态暂时不可用</p><p className="mt-2 text-sm text-slate-500">服务可能仍在初始化，请稍后刷新。</p></Card>;
  else if (project.data?.status === "failed" || failureEvent) content = <FailedRun message={failureMessage} pending={start.isPending} onRetry={() => start.mutate()} />;
  else if (stageTransition) content = <StageTransition transition={stageTransition} />;
  else if (interrupt?.kind === "topic" && state?.topic_candidates) content = <TopicApproval candidates={state.topic_candidates} pending={resume.isPending} onResume={submitResume} />;
  else if (interrupt?.kind === "storyboard" && state?.storyboard) content = <StoryboardApproval storyboard={state.storyboard} review={state.storyboard_review} pending={resume.isPending} onResume={submitResume} />;
  else if (interrupt?.kind === "visual_prompt" && state?.visual_prompts) content = <PromptApproval prompts={state.visual_prompts} pending={resume.isPending} onResume={submitResume} />;
  else if (interrupt?.kind === "publication" && state?.storyboard) content = <PublicationGate defaultTitle={state.storyboard.title} pending={publish.isPending} onPublish={(payload) => publish.mutate(payload)} />;
  else if (interrupt?.kind === "metrics") content = <Card className="mx-auto max-w-2xl text-center"><Clock3 className="mx-auto h-8 w-8 text-sage-600" /><h2 className="mt-4 text-2xl font-bold">等待发布后 {interrupt.target_hours}h 数据</h2><p className="mt-3 text-sm leading-6 text-slate-500">Worker 每小时自动检查。你也可以立即同步；标题匹配不唯一时，系统会停下来而不是猜。</p><Button className="mt-6" disabled={sync.isPending} onClick={() => sync.mutate()}><RefreshCw className={`h-4 w-4 ${sync.isPending ? "animate-spin" : ""}`} />立即同步</Button>{sync.data && <p className="mt-3 text-xs text-slate-500">{sync.data.status} · 新增 {sync.data.synced} 个快照</p>}</Card>;
  else if (interrupt?.kind === "knowledge" && state?.retro) content = <KnowledgeGate retro={state.retro} pending={resume.isPending} onResume={submitResume} />;
  else if (state?.stage === "completed") content = <Card className="py-14 text-center"><h2 className="text-3xl font-black">完整闭环已完成</h2><p className="mt-3 text-sm text-slate-500">选题、分镜、Prompt、预测、24h/48h 复盘和批准写回都保留在 checkpoint 历史中。</p></Card>;
  return (
    <div className="mx-auto max-w-[1600px] px-5 py-7 lg:px-8 lg:py-9">
      <BackButton fallbackTo="/" label="返回作品列表" className="mb-5 -ml-3" />
      <header className="mb-7 flex flex-wrap items-start justify-between gap-4"><div><div className="flex items-center gap-2"><Badge>{project.data?.status ?? "loading"}</Badge>{threadId && <span className="flex items-center gap-1 text-xs text-slate-400">{connected ? <Wifi className="h-3 w-3 text-emerald-600" /> : <WifiOff className="h-3 w-3" />}SSE {connected ? "已连接" : "重连中"}</span>}</div><h1 className="mt-3 text-3xl font-black">{project.data?.name ?? "作品工作台"}</h1><p className="mt-2 max-w-3xl text-sm leading-6 text-slate-500">{project.data?.inspiration}</p></div><div className="flex flex-wrap gap-2">{threadId && <><Link to={`/projects/${projectId}/traces`}><Button variant="secondary"><ScanSearch className="h-4 w-4" />LLM 调用记录</Button></Link><Link to={`/projects/${projectId}/history`}><Button variant="secondary"><History className="h-4 w-4" />历史 / Fork</Button></Link><Badge className="hidden max-w-44 truncate py-2 sm:inline">{threadId}</Badge></>}{!threadId && <Button disabled={start.isPending} onClick={() => start.mutate()}>{start.isPending ? <LoaderCircle className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}启动 Agent</Button>}</div></header>
      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_22rem]">
        <main className="min-w-0">{gateReturnNotice && !stageTransition && <GateReturnNotice kind={gateReturnNotice.kind} blockingMessages={blockingMessages} onDismiss={() => setGateReturnNotice(null)} />}{content}<Card className="mt-6"><div className="mb-4 flex items-center justify-between"><div><p className="label">Live timeline</p><h2 className="mt-1 font-bold">实时事件</h2></div><GitFork className="h-5 w-5 text-sage-500" /></div><RunTimeline events={events} /></Card></main>
        <EvidenceSidebar evidence={state?.evidence ?? []} degraded={state?.retrieval_degraded} />
      </div>
    </div>
  );
}

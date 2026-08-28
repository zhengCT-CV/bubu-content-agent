import { useMutation, useQuery } from "@tanstack/react-query";
import { GitFork, LoaderCircle, RotateCcw } from "lucide-react";
import { useNavigate, useParams } from "react-router-dom";
import { api } from "../api/client";
import { BackButton } from "../components/BackButton";
import { Badge, Button, Card, EmptyState } from "../components/ui";
import { formatDate } from "../lib";

export function HistoryPage() {
  const { projectId = "" } = useParams();
  const navigate = useNavigate();
  const project = useQuery({ queryKey: ["project", projectId], queryFn: () => api.getProject(projectId) });
  const threadId = project.data?.active_thread_id;
  const history = useQuery({ queryKey: ["history", threadId], queryFn: () => api.getRunHistory(threadId!), enabled: Boolean(threadId) });
  const fork = useMutation({ mutationFn: (checkpointId: string) => api.fork(threadId!, { checkpoint_id: checkpointId, state_patch: {} }), onSuccess: ({ thread_id }) => { void thread_id; navigate(`/projects/${projectId}`); } });
  return <div className="mx-auto max-w-5xl px-5 py-10 lg:px-10"><BackButton fallbackTo={`/projects/${projectId}`} label="返回工作台" className="mb-5 -ml-3" /><header><p className="label">Time travel</p><h1 className="mt-2 text-4xl font-black">Checkpoint 历史与分支</h1><p className="mt-3 max-w-2xl text-sm leading-7 text-slate-500">Fork 会复制选中 checkpoint 的状态到新 thread，从下一节点继续；旧路线保持只读。</p></header><div className="mt-8 space-y-3">{history.isLoading && <LoaderCircle className="mx-auto h-6 w-6 animate-spin" />}{history.data?.length === 0 && <EmptyState title="没有 checkpoint" body="先启动一次工作流。" />}{history.data?.map((item, index) => <Card key={item.checkpoint_id} className="grid items-center gap-4 sm:grid-cols-[4rem_1fr_auto]"><div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-sage-100 font-bold text-sage-800">{history.data.length - index}</div><div><div className="flex flex-wrap items-center gap-2"><h2 className="font-bold">{item.stage ?? "state update"}</h2><Badge>{item.next.join(" → ") || "END"}</Badge></div><p className="mt-2 text-xs text-slate-400">{formatDate(item.created_at)} · {item.checkpoint_id}</p></div><Button variant="secondary" disabled={fork.isPending} onClick={() => fork.mutate(item.checkpoint_id)}>{fork.isPending ? <RotateCcw className="h-4 w-4 animate-spin" /> : <GitFork className="h-4 w-4" />}从这里 Fork</Button></Card>)}</div></div>;
}

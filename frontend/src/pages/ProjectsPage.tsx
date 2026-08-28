import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowRight, LoaderCircle, Plus, Sparkles } from "lucide-react";
import { Link, useNavigate } from "react-router-dom";
import { z } from "zod";
import { api } from "../api/client";
import { Badge, Button, Card, EmptyState } from "../components/ui";
import { formatDate } from "../lib";

const projectSchema = z.object({ name: z.string().min(2, "项目名至少 2 个字"), inspiration: z.string().min(2, "请写下一个灵感"), target_audience: z.string().min(2) });

export function ProjectsPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const projects = useQuery({ queryKey: ["projects"], queryFn: api.listProjects });
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ name: "", inspiration: "", target_audience: "关注个人成长与职场表达的微信公众号读者" });
  const [error, setError] = useState("");
  const create = useMutation({ mutationFn: api.createProject, onSuccess: (project) => { void queryClient.invalidateQueries({ queryKey: ["projects"] }); navigate(`/projects/${project.id}`); } });
  const submit = () => { const parsed = projectSchema.safeParse(form); if (!parsed.success) { setError(parsed.error.issues[0]?.message ?? "输入不完整"); return; } setError(""); create.mutate(parsed.data); };
  return (
    <div className="mx-auto max-w-7xl px-5 py-8 lg:px-10 lg:py-12">
      <header className="flex flex-wrap items-end justify-between gap-5"><div><p className="label">Content projects</p><h1 className="mt-2 text-4xl font-black tracking-tight">把一个灵感，走成一条证据链</h1><p className="mt-3 max-w-2xl text-sm leading-7 text-slate-500">选题、分镜、视觉 Prompt、发布后数据与复盘都留在同一条可回溯工作流里。</p></div><Button onClick={() => setOpen((value) => !value)}><Plus className="h-4 w-4" />新建作品</Button></header>
      {open && <Card className="mt-8 border-sage-300 bg-sage-50/80"><div className="grid gap-4 lg:grid-cols-2"><div><label className="label">作品名</label><input className="field mt-1" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="例如：不替别人承担的一天" /></div><div><label className="label">目标读者</label><input className="field mt-1" value={form.target_audience} onChange={(e) => setForm({ ...form, target_audience: e.target.value })} /></div><div className="lg:col-span-2"><label className="label">你现在的灵感</label><textarea className="field mt-1 min-h-28" value={form.inspiration} onChange={(e) => setForm({ ...form, inspiration: e.target.value })} placeholder="不用写成完整选题，说出你观察到的人、冲突或情绪就行。" /></div></div>{error && <p className="mt-3 text-sm text-red-600">{error}</p>}<div className="mt-4 flex justify-end"><Button disabled={create.isPending} onClick={submit}>{create.isPending ? <LoaderCircle className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}创建并进入工作台</Button></div></Card>}
      <section className="mt-10"><div className="mb-4 flex items-center justify-between"><h2 className="text-xl font-bold">最近作品</h2><span className="text-xs text-slate-400">{projects.data?.length ?? 0} 个项目</span></div>{projects.isLoading && <div className="py-20 text-center text-slate-400"><LoaderCircle className="mx-auto h-6 w-6 animate-spin" /></div>}{projects.data?.length === 0 && <EmptyState title="还没有作品" body="从一个真实灵感开始。Agent 会先读取历史运营证据，再给你三个可选择的方向。" />}<div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">{projects.data?.map((project) => <Link key={project.id} to={`/projects/${project.id}`}><Card className="group h-full transition hover:-translate-y-1 hover:border-sage-300"><div className="flex items-center justify-between"><Badge>{project.status}</Badge><ArrowRight className="h-4 w-4 text-slate-300 transition group-hover:translate-x-1 group-hover:text-sage-700" /></div><h3 className="mt-5 text-xl font-bold">{project.name}</h3><p className="mt-3 line-clamp-3 text-sm leading-6 text-slate-500">{project.inspiration}</p><p className="mt-6 text-xs text-slate-400">更新于 {formatDate(project.updated_at)}</p></Card></Link>)}</div></section>
    </div>
  );
}


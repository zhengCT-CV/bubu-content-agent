import { useQuery } from "@tanstack/react-query";
import { BarChart3 } from "lucide-react";
import { api } from "../api/client";
import { Badge, Card, EmptyState } from "../components/ui";

export function AnalyticsPage() {
  const projects = useQuery({ queryKey: ["projects"], queryFn: api.listProjects });
  const published = projects.data?.filter((item) => item.publication) ?? [];
  return <div className="mx-auto max-w-6xl px-5 py-10 lg:px-10"><header><p className="label">Performance</p><h1 className="mt-2 text-4xl font-black">发布与复盘看板</h1><p className="mt-3 text-sm text-slate-500">结构化指标来自 MCP 精确查询，不参与向量相似度计算。</p></header><div className="mt-8 grid gap-4 sm:grid-cols-3"><Card><p className="label">总作品</p><p className="mt-3 text-4xl font-black">{projects.data?.length ?? 0}</p></Card><Card><p className="label">已发布</p><p className="mt-3 text-4xl font-black">{published.length}</p></Card><Card><p className="label">已闭环</p><p className="mt-3 text-4xl font-black">{projects.data?.filter((item) => item.status === "completed").length ?? 0}</p></Card></div><section className="mt-8"><div className="mb-4 flex items-center gap-2"><BarChart3 className="h-5 w-5 text-sage-600" /><h2 className="text-xl font-bold">已发布作品</h2></div>{published.length === 0 && <EmptyState title="还没有发布记录" body="作品通过 Prompt 审批后，登记一次真实发布，这里就会出现指标入口。" />}<div className="space-y-3">{published.map((item) => <Card key={item.id} className="flex items-center justify-between gap-4"><div><h3 className="font-bold">{item.publication?.title}</h3><p className="mt-1 text-xs text-slate-400">{item.publication?.published_at}</p></div><Badge>{item.status}</Badge></Card>)}</div></section></div>;
}


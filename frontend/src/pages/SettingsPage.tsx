import { useQuery } from "@tanstack/react-query";
import { CheckCircle2, KeyRound, Server } from "lucide-react";
import { api } from "../api/client";
import { Badge, Card } from "../components/ui";

export function SettingsPage() {
  const health = useQuery({ queryKey: ["health"], queryFn: api.health });
  return <div className="mx-auto max-w-4xl px-5 py-10 lg:px-10"><header><p className="label">Environment</p><h1 className="mt-2 text-4xl font-black">运行设置</h1><p className="mt-3 text-sm text-slate-500">密钥只从后端环境变量读取，前端不会接触或展示密钥值。</p></header><div className="mt-8 grid gap-4 md:grid-cols-2"><Card><Server className="h-5 w-5 text-sage-600" /><p className="mt-4 font-bold">后端状态</p><div className="mt-3 flex items-center gap-2"><Badge>{health.data?.mode ?? "checking"}</Badge>{health.data?.status === "ok" && <CheckCircle2 className="h-4 w-4 text-emerald-600" />}</div><p className="mt-4 text-xs leading-5 text-slate-500">demo：内存 checkpoint + 确定性 Agent；local：PostgreSQL/pgvector + Redis + DeepSeek + DashScope + MCP。</p></Card><Card><KeyRound className="h-5 w-5 text-coral" /><p className="mt-4 font-bold">版本化 Skills</p><div className="mt-3 space-y-2">{Object.entries(health.data?.skills ?? {}).map(([name, versions]) => <div key={name} className="flex items-center justify-between text-sm"><span>{name}</span><Badge>{versions[0]}</Badge></div>)}</div></Card></div></div>;
}


import { BarChart3, BookOpenCheck, Database, Home, Settings, Sprout } from "lucide-react";
import { NavLink, Outlet } from "react-router-dom";
import { cn } from "../lib";

const links = [
  { to: "/", label: "作品", icon: Home },
  { to: "/analytics", label: "分析", icon: BarChart3 },
  { to: "/data-center", label: "数据中心", icon: Database },
  { to: "/settings", label: "设置", icon: Settings },
];

export function AppShell() {
  return (
    <div className="min-h-screen lg:grid lg:grid-cols-[15rem_1fr]">
      <aside className="border-b border-white/70 bg-sage-900 px-5 py-4 text-white lg:sticky lg:top-0 lg:h-screen lg:border-b-0 lg:border-r lg:py-7">
        <div className="flex items-center gap-3"><div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-coral"><Sprout className="h-5 w-5" /></div><div><p className="text-sm font-bold">Bubu</p><p className="text-xs text-sage-300">ContentOps Agent</p></div></div>
        <nav className="mt-5 flex gap-2 overflow-x-auto lg:mt-10 lg:flex-col lg:overflow-visible">{links.map(({ to, label, icon: Icon }) => <NavLink key={to} to={to} end={to === "/"} className={({ isActive }) => cn("flex shrink-0 items-center gap-3 rounded-2xl px-4 py-3 text-sm font-medium transition", isActive ? "bg-white text-sage-900" : "text-sage-100 hover:bg-white/10")}><Icon className="h-4 w-4" /><span>{label}</span></NavLink>)}</nav>
        <div className="mt-auto hidden rounded-3xl bg-white/8 p-4 lg:absolute lg:bottom-7 lg:left-5 lg:right-5 lg:block"><BookOpenCheck className="h-5 w-5 text-sage-300" /><p className="mt-3 text-xs leading-5 text-sage-100">每次模型运行都固定 Skill 版本和 Prompt hash，方便展示可追溯性。</p></div>
      </aside>
      <main className="min-w-0"><Outlet /></main>
    </div>
  );
}

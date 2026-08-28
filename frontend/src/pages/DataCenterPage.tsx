import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Activity,
  ArrowUpRight,
  BarChart3,
  CheckCircle2,
  Clock3,
  Database,
  Eye,
  Heart,
  LoaderCircle,
  RefreshCw,
  Search,
  Share2,
  Sparkles,
  TrendingUp,
  Users,
} from "lucide-react";
import { api } from "../api/client";
import type { DataCenterArticle } from "../api/types";
import { Badge, Button, Card, EmptyState } from "../components/ui";
import { cn, formatDate } from "../lib";

const numberFormatter = new Intl.NumberFormat("zh-CN", { maximumFractionDigits: 1 });
const integerFormatter = new Intl.NumberFormat("zh-CN", { maximumFractionDigits: 0 });

function number(value: number) {
  return numberFormatter.format(value);
}

function percent(value: number) {
  return `${(value * 100).toFixed(1)}%`;
}

function LineChart({ points, color = "#31553e", valueLabel }: { points: Array<{ label: string; value: number }>; color?: string; valueLabel: string }) {
  if (points.length < 2) return <div className="flex h-52 items-center justify-center text-sm text-slate-400">数据点不足，暂时无法绘制趋势</div>;
  const width = 720;
  const height = 220;
  const paddingX = 26;
  const paddingY = 22;
  const values = points.map((point) => point.value);
  const maximum = Math.max(...values, 1);
  const minimum = Math.min(...values, 0);
  const span = Math.max(maximum - minimum, 1);
  const coordinates = points.map((point, index) => ({
    x: paddingX + (index / (points.length - 1)) * (width - paddingX * 2),
    y: height - paddingY - ((point.value - minimum) / span) * (height - paddingY * 2),
  }));
  const polyline = coordinates.map((point) => `${point.x},${point.y}`).join(" ");
  const peakIndex = values.indexOf(maximum);
  const peak = coordinates[peakIndex];
  return <div>
    <svg role="img" aria-label={valueLabel} viewBox={`0 0 ${width} ${height}`} className="h-52 w-full overflow-visible">
      {[0.25, 0.5, 0.75].map((ratio) => <line key={ratio} x1={paddingX} x2={width - paddingX} y1={height * ratio} y2={height * ratio} stroke="#dfe8e1" strokeDasharray="5 7" />)}
      <polyline fill="none" stroke={color} strokeWidth="4" strokeLinecap="round" strokeLinejoin="round" points={polyline} />
      <circle cx={peak.x} cy={peak.y} r="6" fill={color} stroke="white" strokeWidth="3" />
      <text x={peak.x} y={Math.max(peak.y - 12, 14)} textAnchor="middle" className="fill-slate-500 text-[11px]">{integerFormatter.format(maximum)}</text>
    </svg>
    <div className="flex justify-between text-[11px] text-slate-400"><span>{points[0]?.label}</span><span>{points.at(-1)?.label}</span></div>
  </div>;
}

function HorizontalBars({ items, valueKind = "number" }: { items: Array<{ label: string; value: number }>; valueKind?: "number" | "percent" }) {
  const maximum = Math.max(...items.map((item) => item.value), 1);
  return <div className="space-y-3">{items.map((item) => <div key={item.label}>
    <div className="mb-1.5 flex items-center justify-between gap-4 text-xs"><span className="truncate text-slate-600" title={item.label}>{item.label}</span><b className="shrink-0 text-sage-900">{valueKind === "percent" ? percent(item.value) : integerFormatter.format(item.value)}</b></div>
    <div className="h-2 overflow-hidden rounded-full bg-sage-50"><div className="h-full rounded-full bg-sage-500" style={{ width: `${Math.max((item.value / maximum) * 100, 2)}%` }} /></div>
  </div>)}</div>;
}

function Kpi({ icon: Icon, label, value, note }: { icon: typeof Eye; label: string; value: string; note: string }) {
  return <Card><div className="flex items-center justify-between"><span className="label">{label}</span><Icon className="h-5 w-5 text-sage-500" /></div><p className="mt-4 text-3xl font-black tracking-tight">{value}</p><p className="mt-2 text-xs text-slate-400">{note}</p></Card>;
}

type CurveMetric = "reads" | "shares" | "likes";

export function DataCenterPage() {
  const queryClient = useQueryClient();
  const [search, setSearch] = useState("");
  const [sortBy, setSortBy] = useState<"reads" | "shares" | "published">("reads");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [curveMetric, setCurveMetric] = useState<CurveMetric>("reads");
  const overview = useQuery({
    queryKey: ["data-center"],
    queryFn: () => api.getDataCenterOverview(),
    refetchInterval: 3 * 60 * 1_000,
  });
  const refresh = useMutation({
    mutationFn: () => api.getDataCenterOverview(true),
    onSuccess: (data) => queryClient.setQueryData(["data-center"], data),
  });
  useEffect(() => {
    if (!selectedId && overview.data?.articles[0]) setSelectedId(overview.data.articles[0].article_id);
  }, [overview.data?.articles, selectedId]);
  const detail = useQuery({
    queryKey: ["data-center-article", selectedId, overview.data?.source.data_version],
    queryFn: () => api.getDataCenterArticle(selectedId!),
    enabled: Boolean(selectedId),
  });
  const visibleArticles = useMemo(() => {
    const normalized = search.trim().toLowerCase();
    const items = overview.data?.articles.filter((article) => article.title.toLowerCase().includes(normalized)) ?? [];
    return [...items].sort((left, right) => sortBy === "published"
      ? (right.published_at ?? "").localeCompare(left.published_at ?? "")
      : right[sortBy] - left[sortBy]);
  }, [overview.data?.articles, search, sortBy]);
  const topArticles = useMemo(() => [...(overview.data?.articles ?? [])].sort((a, b) => b.reads - a.reads).slice(0, 6), [overview.data?.articles]);

  if (overview.isLoading) return <div className="flex min-h-[70vh] items-center justify-center"><LoaderCircle className="h-8 w-8 animate-spin text-sage-600" /></div>;
  if (overview.isError || !overview.data) return <div className="mx-auto max-w-3xl px-5 py-16"><Card className="border-red-200 bg-red-50 text-center"><Database className="mx-auto h-9 w-9 text-red-600" /><h1 className="mt-4 text-2xl font-black text-red-900">暂时无法读取采集数据</h1><p className="mt-2 text-sm text-red-700">自动化可能正在写入 Excel，请稍后重试。</p><Button variant="danger" className="mt-5" onClick={() => void overview.refetch()}><RefreshCw className="h-4 w-4" />重新读取</Button></Card></div>;

  const { source, summary, historical_baseline: historical } = overview.data;
  const sourceState = source.state === "fresh"
    ? { label: "数据正常", className: "bg-emerald-100 text-emerald-800", icon: CheckCircle2 }
    : source.state === "updating"
      ? { label: "正在更新", className: "bg-amber-100 text-amber-800", icon: RefreshCw }
      : { label: "数据可能延迟", className: "bg-amber-100 text-amber-800", icon: Clock3 };
  const SourceIcon = sourceState.icon;
  const curveLabels: Record<CurveMetric, string> = { reads: "阅读量", shares: "分享", likes: "点赞" };
  const curvePoints = detail.data?.curve
    .filter((point) => typeof point[curveMetric] === "number")
    .map((point) => ({ label: `${Math.round(point.hours_since_publish)}h`, value: point[curveMetric] as number })) ?? [];
  const exported = detail.data?.exported_detail;

  return <div className="mx-auto max-w-[1600px] px-5 py-8 lg:px-10 lg:py-11">
    <header className="flex flex-wrap items-start justify-between gap-5"><div><p className="label">Content data center</p><h1 className="mt-2 text-4xl font-black tracking-tight">作品数据中心</h1><p className="mt-3 max-w-3xl text-sm leading-7 text-slate-500">读取自动化每小时更新的 Excel，观察作品增长、互动表现与用户画像。原始文件始终只读。</p></div><Button variant="secondary" disabled={refresh.isPending} onClick={() => refresh.mutate()}>{refresh.isPending ? <LoaderCircle className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}立即刷新</Button></header>

    <Card className={cn("mt-7 flex flex-wrap items-center justify-between gap-4", source.state !== "fresh" && "border-amber-200 bg-amber-50/80")}>
      <div className="flex items-center gap-3"><div className="rounded-2xl bg-sage-50 p-3"><Activity className="h-5 w-5 text-sage-700" /></div><div><div className="flex flex-wrap items-center gap-2"><b>自动化采集状态</b><Badge className={sourceState.className}><SourceIcon className={cn("mr-1 inline h-3 w-3", source.state === "updating" && "animate-spin")} />{sourceState.label}</Badge>{source.cached && <Badge>缓存快照</Badge>}</div><p className="mt-1 text-xs text-slate-500">最后采集 {formatDate(source.last_captured_at)} · 文件更新 {formatDate(source.file_modified_at)} · 每 3 分钟自动检查</p></div></div>
      <div className="flex gap-5 text-right text-xs text-slate-500"><div><b className="block text-base text-ink">{number(summary.sample_count)}</b>采样点</div><div><b className="block text-base text-ink">{percent(summary.collector_success_rate)}</b>采集成功率</div></div>
      {source.warning && <p className="w-full rounded-2xl bg-white/70 px-4 py-3 text-xs text-amber-800">{source.warning}</p>}
    </Card>

    <section className="mt-6 grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
      <Kpi icon={Database} label="追踪作品" value={number(summary.tracked_articles)} note={`${summary.tracking_articles} 篇追踪中 · ${summary.completed_articles} 篇已完成`} />
      <Kpi icon={Eye} label="当前总阅读" value={number(summary.total_reads)} note="每篇作品取最新一次读数" />
      <Kpi icon={BarChart3} label="阅读中位数" value={number(summary.median_reads)} note="比平均数更不容易受爆款影响" />
      <Kpi icon={TrendingUp} label="数据里程碑" value={number(summary.milestone_count)} note="按发布后小时对齐的采样点" />
      <Kpi icon={Sparkles} label="历史基线" value={historical ? number(historical.median_reads) : "—"} note={historical ? `${historical.date_from} 至 ${historical.date_to} 中位阅读` : "暂无历史汇总数据"} />
    </section>

    <section className="mt-6 grid gap-6 xl:grid-cols-[minmax(0,1.35fr)_minmax(20rem,0.65fr)]">
      <Card><div className="mb-5"><p className="label">Publishing trend</p><h2 className="mt-1 text-xl font-bold">按发布日期统计的作品阅读表现</h2></div><LineChart valueLabel="每日发布作品当前阅读量趋势" points={overview.data.daily_performance.map((item) => ({ label: item.date.slice(5), value: item.reads }))} /></Card>
      <Card><div className="mb-5"><p className="label">Top works</p><h2 className="mt-1 text-xl font-bold">阅读表现前六</h2></div><HorizontalBars items={topArticles.map((article) => ({ label: article.title, value: article.reads }))} /></Card>
    </section>

    <section className="mt-8"><div className="flex flex-wrap items-end justify-between gap-4"><div><p className="label">Article explorer</p><h2 className="mt-1 text-2xl font-black">全部作品</h2></div><div className="flex flex-wrap gap-2"><label className="relative"><Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" /><input className="field w-64 py-2 pl-9" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="搜索作品标题" /></label><select className="field w-auto py-2" value={sortBy} onChange={(event) => setSortBy(event.target.value as typeof sortBy)}><option value="reads">按阅读排序</option><option value="shares">按分享排序</option><option value="published">按发布时间排序</option></select></div></div>
      <Card className="mt-4 overflow-hidden p-0"><div className="overflow-x-auto"><table className="w-full min-w-[860px] text-left text-sm"><thead className="bg-sage-50/80 text-xs text-sage-800"><tr><th className="px-5 py-4">作品</th><th className="px-4 py-4 text-right">阅读</th><th className="px-4 py-4 text-right">分享</th><th className="px-4 py-4 text-right">点赞</th><th className="px-4 py-4 text-right">分享率</th><th className="px-4 py-4">状态</th><th className="px-5 py-4"></th></tr></thead><tbody className="divide-y divide-sage-50">{visibleArticles.map((article) => <ArticleRow key={article.article_id} article={article} selected={article.article_id === selectedId} onSelect={() => setSelectedId(article.article_id)} />)}</tbody></table></div>{visibleArticles.length === 0 && <EmptyState title="没有匹配的作品" body="尝试缩短搜索词。" />}</Card>
    </section>

    {selectedId && <section className="mt-8"><div className="mb-4"><p className="label">Article detail</p><h2 className="mt-1 text-2xl font-black">单篇作品详情</h2></div>{detail.isLoading && <Card className="flex min-h-72 items-center justify-center"><LoaderCircle className="h-7 w-7 animate-spin text-sage-600" /></Card>}{detail.data && <div className="space-y-6"><Card><div className="flex flex-wrap items-start justify-between gap-4"><div><div className="flex flex-wrap gap-2"><Badge>{detail.data.article.status}</Badge>{detail.data.article.has_details && <Badge className="bg-emerald-100 text-emerald-800">含用户画像</Badge>}</div><h3 className="mt-3 text-2xl font-black">{detail.data.article.title}</h3><p className="mt-2 text-xs text-slate-400">发布于 {formatDate(detail.data.article.published_at)} · 最新采集 {formatDate(detail.data.article.captured_at)}</p></div>{detail.data.article.url && <a href={detail.data.article.url} target="_blank" rel="noreferrer"><Button variant="ghost">打开原文<ArrowUpRight className="h-4 w-4" /></Button></a>}</div><div className="mt-6 grid gap-3 sm:grid-cols-3"><div className="rounded-2xl bg-sage-50 p-4"><Eye className="h-4 w-4 text-sage-600" /><b className="mt-2 block text-2xl">{number(detail.data.article.reads)}</b><span className="text-xs text-slate-500">阅读</span></div><div className="rounded-2xl bg-sage-50 p-4"><Share2 className="h-4 w-4 text-sage-600" /><b className="mt-2 block text-2xl">{number(detail.data.article.shares)}</b><span className="text-xs text-slate-500">分享 · {percent(detail.data.article.share_rate)}</span></div><div className="rounded-2xl bg-sage-50 p-4"><Heart className="h-4 w-4 text-coral" /><b className="mt-2 block text-2xl">{number(detail.data.article.likes)}</b><span className="text-xs text-slate-500">点赞 · {percent(detail.data.article.like_rate)}</span></div></div></Card>
        <div className="grid gap-6 xl:grid-cols-[minmax(0,1.4fr)_minmax(19rem,0.6fr)]"><Card><div className="flex flex-wrap items-center justify-between gap-3"><div><p className="label">Hourly curve</p><h3 className="mt-1 text-xl font-bold">发布后增长曲线</h3></div><div className="flex gap-1 rounded-full bg-sage-50 p-1">{(Object.keys(curveLabels) as CurveMetric[]).map((metric) => <button key={metric} className={cn("rounded-full px-3 py-1.5 text-xs font-semibold", curveMetric === metric ? "bg-sage-800 text-white" : "text-sage-700")} onClick={() => setCurveMetric(metric)}>{curveLabels[metric]}</button>)}</div></div><div className="mt-4"><LineChart valueLabel={`${detail.data.article.title}${curveLabels[curveMetric]}增长曲线`} points={curvePoints} color={curveMetric === "reads" ? "#31553e" : curveMetric === "shares" ? "#e87558" : "#4f8260"} /><p className="mt-3 text-xs leading-5 text-slate-400">阅读曲线会追加文章汇总中的最新读数；分享与点赞严格展示实际小时采样周期。</p></div></Card>
          <Card><p className="label">Traffic sources</p><h3 className="mt-1 text-xl font-bold">阅读来源</h3><div className="mt-5">{exported?.channels.length ? <HorizontalBars items={exported.channels.slice(0, 7).map((item) => ({ label: item.label, value: item.reads }))} /> : <p className="py-16 text-center text-sm text-slate-400">这篇作品暂无渠道明细</p>}</div></Card></div>
        {exported && <div className="grid gap-6 lg:grid-cols-3"><Card><div className="flex items-center gap-2"><Users className="h-5 w-5 text-sage-600" /><h3 className="font-bold">性别分布</h3></div><div className="mt-5"><HorizontalBars valueKind="percent" items={exported.gender.map((item) => ({ label: item.label, value: item.ratio }))} /></div></Card><Card><div className="flex items-center gap-2"><Users className="h-5 w-5 text-sage-600" /><h3 className="font-bold">年龄分布</h3></div><div className="mt-5"><HorizontalBars valueKind="percent" items={exported.age.map((item) => ({ label: item.label, value: item.ratio }))} /></div></Card><Card><div className="flex items-center gap-2"><Users className="h-5 w-5 text-sage-600" /><h3 className="font-bold">地域分布 Top 8</h3></div><div className="mt-5"><HorizontalBars valueKind="percent" items={exported.regions.slice(0, 8).map((item) => ({ label: item.label, value: item.ratio }))} /></div></Card></div>}
      </div>}{detail.isError && <Card className="border-red-200 bg-red-50 text-red-800">单篇数据读取失败，自动化可能正在更新文件。</Card>}</section>}
  </div>;
}

function ArticleRow({ article, selected, onSelect }: { article: DataCenterArticle; selected: boolean; onSelect: () => void }) {
  return <tr className={cn("transition hover:bg-sage-50/50", selected && "bg-sage-50/70")}><td className="px-5 py-4"><button className="max-w-xl text-left" onClick={onSelect}><b className="line-clamp-1">{article.title}</b><span className="mt-1 block text-xs text-slate-400">{formatDate(article.published_at)} · {article.hours_since_publish.toFixed(0)}h 数据</span></button></td><td className="px-4 py-4 text-right font-bold">{integerFormatter.format(article.reads)}</td><td className="px-4 py-4 text-right">{integerFormatter.format(article.shares)}</td><td className="px-4 py-4 text-right">{integerFormatter.format(article.likes)}</td><td className="px-4 py-4 text-right">{percent(article.share_rate)}</td><td className="px-4 py-4"><Badge className={article.status === "追踪中" ? "bg-amber-100 text-amber-800" : undefined}>{article.status}</Badge></td><td className="px-5 py-4 text-right"><Button variant="ghost" className="px-3 py-2" onClick={onSelect}>详情<ArrowUpRight className="h-4 w-4" /></Button></td></tr>;
}

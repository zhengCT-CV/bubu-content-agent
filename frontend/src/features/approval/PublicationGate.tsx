import { useState } from "react";
import { Send } from "lucide-react";
import { Button, Card } from "../../components/ui";

export function PublicationGate({ defaultTitle, pending, onPublish }: { defaultTitle: string; pending: boolean; onPublish: (payload: { title: string; published_at: string; article_id?: string; article_url?: string }) => void }) {
  const localNow = new Date(Date.now() - new Date().getTimezoneOffset() * 60000).toISOString().slice(0, 16);
  const [title, setTitle] = useState(defaultTitle);
  const [publishedAt, setPublishedAt] = useState(localNow);
  const [articleId, setArticleId] = useState("");
  const [url, setUrl] = useState("");
  return (
    <Card className="mx-auto max-w-2xl">
      <p className="label">Publish registry</p><h2 className="mt-2 text-2xl font-bold">产物已完成，等待你发布</h2><p className="mt-2 text-sm leading-6 text-slate-500">系统不会自动发布公众号。发布后在这里登记，Worker 才会开始匹配 24h/48h 数据。</p>
      <div className="mt-6 space-y-4"><div><label className="label">最终标题</label><input className="field mt-1" value={title} onChange={(e) => setTitle(e.target.value)} /></div><div className="grid gap-4 sm:grid-cols-2"><div><label className="label">发布时间</label><input className="field mt-1" type="datetime-local" value={publishedAt} onChange={(e) => setPublishedAt(e.target.value)} /></div><div><label className="label">文章 ID（可选）</label><input className="field mt-1" value={articleId} onChange={(e) => setArticleId(e.target.value)} /></div></div><div><label className="label">文章链接（可选）</label><input className="field mt-1" value={url} onChange={(e) => setUrl(e.target.value)} /></div></div>
      <Button className="mt-6 w-full" disabled={pending || !title || !publishedAt} onClick={() => onPublish({ title, published_at: new Date(publishedAt).toISOString(), article_id: articleId || undefined, article_url: url || undefined })}><Send className="h-4 w-4" />登记发布</Button>
    </Card>
  );
}


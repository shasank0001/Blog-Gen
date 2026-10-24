import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { getArticles, createArticle } from '@/lib/workspaceApi';
import type { Article } from '@/lib/workspaceApi';
import { Button } from '@/components/ui/button';
import { apiErrorMessage } from '@/lib/apiError';

export function Drafts() {
  const [items, setItems] = useState<Omit<Article, 'content'>[]>([]);
  const [skip, setSkip] = useState(0);
  const [more, setMore] = useState(false);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const navigate = useNavigate();
  useEffect(() => {
    let active = true;
    getArticles(skip).then(page => { if (active) { setItems(page.items); setMore(page.has_more); } })
      .catch(problem => { if (active) setError(apiErrorMessage(problem, 'Could not load drafts')); });
    return () => { active = false; };
  }, [skip]);
  async function create() {
    setBusy(true);
    try { const article = await createArticle('Untitled draft'); navigate(`/drafts/${article.id}`); }
    catch (problem) { setError(apiErrorMessage(problem, 'Could not create draft')); setBusy(false); }
  }
  return <div className="space-y-6"><div className="flex justify-between flex-wrap gap-4"><div><h1 className="text-3xl font-bold">Drafts</h1><p className="mt-2 text-muted-foreground">Your saved writing, with a revision for every successful edit.</p></div><Button disabled={busy} onClick={() => void create()}>New draft</Button></div>
    {error && <p role="alert" className="text-red-700">{error}</p>}
    <div className="divide-y rounded-lg border bg-white dark:bg-zinc-900">{items.map(article => <Link key={article.id} to={`/drafts/${article.id}`} className="block p-5 hover:bg-muted/40 focus-visible:ring-2 focus-visible:ring-primary"><div className="flex justify-between gap-4"><h2 className="font-semibold">{article.title}</h2><span className="text-sm text-muted-foreground">v{article.version}</span></div><p className="mt-2 text-sm text-muted-foreground">Edited {new Date(article.updated_at).toLocaleString()}</p></Link>)}{!items.length && <p className="p-8 text-muted-foreground">Create a draft or finish a generation run to start editing.</p>}</div>
    <div className="flex gap-3"><Button variant="outline" disabled={!skip} onClick={() => setSkip(value => Math.max(0, value - 20))}>Previous</Button><Button variant="outline" disabled={!more} onClick={() => setSkip(value => value + 20)}>Next</Button></div>
  </div>;
}

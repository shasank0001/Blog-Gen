import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { getJobs, getArticles, getUsage, usd } from '@/lib/workspaceApi';
import type { Job, Article, Usage } from '@/lib/workspaceApi';
import { Button } from '@/components/ui/button';
import { apiErrorMessage } from '@/lib/apiError';

export function Dashboard() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [drafts, setDrafts] = useState<Omit<Article, 'content'>[]>([]);
  const [usage, setUsage] = useState<Usage | null>(null);
  const [error, setError] = useState('');
  useEffect(() => {
    let active = true;
    Promise.all([getJobs(), getArticles(), getUsage()]).then(([runs, articles, spending]) => {
      if (active) { setJobs(runs.items); setDrafts(articles.items); setUsage(spending); }
    }).catch(problem => { if (active) setError(apiErrorMessage(problem, 'Could not load the workspace')); });
    return () => { active = false; };
  }, []);
  return <div className="space-y-8"><div className="flex flex-wrap justify-between gap-4"><div><h1 className="text-3xl font-bold">Writing workspace</h1><p className="mt-2 text-muted-foreground">Pick up a draft, review a run, or start your next article.</p></div><Button asChild><Link to="/generate">Generate an article</Link></Button></div>
    {error && <p role="alert">{error}</p>}
    <section className="flex flex-wrap justify-between gap-4 p-5 rounded-lg border bg-white dark:bg-zinc-900"><div><h2 className="text-sm text-muted-foreground">This month’s generation budget</h2><p className="text-2xl font-semibold mt-2">{usage ? `${usd(usage.committed_usd)} / ${usd(usage.monthly_limit_usd)}` : 'Loading…'}</p></div><div className="text-sm"><p>Measured estimates and held reservations.</p><Link className="inline-block mt-2 text-primary underline" to="/costs">Manage spending limits</Link></div></section>
    <div className="grid lg:grid-cols-2 gap-8"><section><div className="flex justify-between gap-3 mb-4"><h2 className="text-xl font-semibold">Recent drafts</h2><Link className="text-primary underline" to="/drafts">All drafts</Link></div><div className="divide-y border rounded-lg">{drafts.slice(0, 5).map(draft => <Link className="block p-4 hover:bg-muted/50" key={draft.id} to={`/drafts/${draft.id}`}><p className="font-medium">{draft.title}</p><p className="mt-2 text-sm text-muted-foreground">Version {draft.version} · {new Date(draft.updated_at).toLocaleString()}</p></Link>)}{!drafts.length && <p className="p-6 text-muted-foreground">Your completed articles and manual drafts will appear here.</p>}</div></section>
    <section><div className="flex justify-between gap-3 mb-4"><h2 className="text-xl font-semibold">Recent runs</h2><Link className="text-primary underline" to="/runs">All runs</Link></div><div className="divide-y border rounded-lg">{jobs.slice(0, 5).map(job => <Link className="block p-4 hover:bg-muted/50" key={job.id} to={`/runs/${job.id}`}><p className="font-medium">{job.topic}</p><p className="mt-2 text-sm text-muted-foreground">{job.status.replaceAll('_', ' ')} · {usd(job.committed_usd)} spent + held</p></Link>)}{!jobs.length && <p className="p-6 text-muted-foreground">Generation progress is saved independently of this browser.</p>}</div></section></div>
  </div>;
}

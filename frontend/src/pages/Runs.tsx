import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { getJobs, usd } from '@/lib/workspaceApi';
import type { Job } from '@/lib/workspaceApi';
import { Button } from '@/components/ui/button';
import { apiErrorMessage } from '@/lib/apiError';

export function Runs() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [skip, setSkip] = useState(0);
  const [more, setMore] = useState(false);
  const [error, setError] = useState('');
  useEffect(() => {
    let active = true;
    async function load() {
      try { const page = await getJobs(skip); if (active) { setJobs(page.items); setMore(page.has_more); setError(''); } }
      catch (problem) { if (active) setError(apiErrorMessage(problem, 'Could not load runs')); }
    }
    void load();
    const timer = setInterval(() => { void load(); }, 4000);
    return () => { active = false; clearInterval(timer); };
  }, [skip]);
  return <div className="space-y-6">
    <div className="flex flex-wrap justify-between gap-4"><div><h1 className="text-3xl font-bold">Generation runs</h1>
      <p className="text-muted-foreground mt-2">Your work continues when you leave this page.</p></div>
      <Button asChild><Link to="/generate">New article</Link></Button></div>
    {error && <p role="alert" className="text-red-700">{error}</p>}
    <div className="overflow-x-auto rounded-lg border bg-white dark:bg-zinc-900"><table className="w-full text-sm text-left">
      <thead className="border-b bg-muted/40"><tr><th className="p-4">Article</th><th className="p-4">Status</th><th className="p-4">Spent + held / limit</th><th className="p-4">Updated</th></tr></thead>
      <tbody>{jobs.map(job => <tr key={job.id} className="border-b last:border-0"><td className="p-4"><Link className="font-medium text-primary underline underline-offset-4" to={`/runs/${job.id}`}>{job.topic}</Link></td>
        <td className="p-4">{job.cancel_requested && job.status === 'running' ? 'Cancelling…' : job.status.replaceAll('_', ' ')}</td>
        <td className="p-4 whitespace-nowrap">{usd(job.committed_usd)} / {usd(job.cost_limit_usd)}</td><td className="p-4 whitespace-nowrap">{new Date(job.updated_at).toLocaleString()}</td></tr>)}</tbody>
    </table>{!jobs.length && <p className="p-8 text-muted-foreground">No runs yet. Create an article to begin researching.</p>}</div>
    <div className="flex gap-3"><Button variant="outline" disabled={!skip} onClick={() => setSkip(value => Math.max(0, value - 20))}>Previous</Button><Button variant="outline" disabled={!more} onClick={() => setSkip(value => value + 20)}>Next</Button></div>
  </div>;
}

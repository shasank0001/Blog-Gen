import { useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { useJob } from '@/hooks/useJob';
import { cancelJob, resumeJob, usd } from '@/lib/workspaceApi';
import type { OutlineSection } from '@/lib/agentStream';
import { apiErrorMessage } from '@/lib/apiError';
import { OutlineEditor } from '@/components/custom/OutlineEditor';
import { AgentConsole } from '@/components/custom/AgentConsole';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';

function RunView({ id }: { id: string }) {
  const { job, events, connected, error, reconnect } = useJob(id);
  const [actionError, setActionError] = useState('');
  const [busy, setBusy] = useState(false);
  const [limit, setLimit] = useState('');
  async function action(kind: 'resume' | 'cancel', outline?: OutlineSection[]) {
    setBusy(true); setActionError('');
    try {
      if (kind === 'cancel') await cancelJob(id);
      else await resumeJob(id, { approved_outline: outline, ...(limit ? { cost_limit_usd: limit } : {}) });
      reconnect();
    } catch (problem) { setActionError(apiErrorMessage(problem, 'Could not update this run')); }
    finally { setBusy(false); }
  }
  if (!job) return <p role="status">{error || 'Loading saved run…'}</p>;
  const canResume = ['failed', 'cancelled', 'budget_exceeded'].includes(job.status);
  return <div className="space-y-6">
    <Link className="text-primary underline" to="/runs">All runs</Link>
    <div><h1 className="text-3xl font-bold break-words">{job.topic}</h1><p className="mt-2 text-muted-foreground">{job.cancel_requested && job.status === 'running' ? 'Cancelling…' : job.status.replaceAll('_', ' ')}{job.active_step ? ` · ${job.active_step.replaceAll('_', ' ')}` : ''}</p></div>
    <div className="flex flex-wrap gap-6 border-y py-4 text-sm"><p>Spent + held <strong>{usd(job.committed_usd)}</strong> / {usd(job.cost_limit_usd)}</p><p>Reported: {job.input_tokens.toLocaleString()} input tokens · {job.output_tokens.toLocaleString()} output tokens</p><Link className="text-primary underline" to="/costs">View spending</Link></div>
    {(job.error || actionError || error) && <p role="alert" className="rounded border border-amber-300 bg-amber-50 p-4 text-amber-950">{actionError || job.error || error}</p>}
    <div className="flex flex-wrap items-end gap-3">
      {(canResume || job.status === 'awaiting_approval') && <div><Label htmlFor="run-limit">Run limit (USD)</Label><Input id="run-limit" type="number" min="0.0001" step="0.01" placeholder={Number(job.cost_limit_usd).toString()} value={limit} onChange={event => setLimit(event.target.value)} /></div>}
      {canResume && <Button disabled={busy} onClick={() => void action('resume')}>Resume saved progress</Button>}
      {['queued', 'running', 'awaiting_approval'].includes(job.status) && <Button variant="outline" disabled={busy || job.cancel_requested} onClick={() => void action('cancel')}>Cancel run</Button>}
      {job.article_id && <Button asChild><Link to={`/drafts/${job.article_id}`}>Edit saved draft</Link></Button>}
    </div>
    {canResume && <p className="text-sm text-muted-foreground">Resumes from the last saved step. An interrupted model request may be repeated; uncertain charges remain held against your limit.</p>}
    {job.status === 'awaiting_approval' && <fieldset disabled={busy}><OutlineEditor key={job.updated_at} initialOutline={job.outline} onApprove={outline => void action('resume', outline)} /></fieldset>}
    <AgentConsole events={events} activeNode={job.active_step || ''} isConnected={connected} />
  </div>;
}
export function RunDetail() { const { id = '' } = useParams(); return <RunView key={id} id={id} />; }

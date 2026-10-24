import { Link } from 'react-router-dom';
import { useEffect, useState } from 'react';
import { getUsage, updateMonthlyLimit, getPrices, getUsageCalls, usd } from '@/lib/workspaceApi';
import type { Usage, ModelPrice, UsageCall } from '@/lib/workspaceApi';
import { apiErrorMessage } from '@/lib/apiError';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';

export function Costs() {
  const [usage, setUsage] = useState<Usage | null>(null);
  const [rates, setRates] = useState<ModelPrice[]>([]);
  const [limit, setLimit] = useState('');
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [busy, setBusy] = useState(false);
  const [calls, setCalls] = useState<UsageCall[]>([]);
  const [skip, setSkip] = useState(0);
  const [more, setMore] = useState(false);
  useEffect(() => {
    let active = true;
    async function refresh() {
      try { const value = await getUsage(); if (active) setUsage(value); }
      catch (problem) { if (active) setError(apiErrorMessage(problem, 'Could not load spending')); }
    }
    void refresh();
    getPrices().then(value => { if (active) setRates(value.models); }).catch(() => { if (active) setError('Model prices are not configured correctly. Contact your administrator.'); });
    const timer = setInterval(() => { void refresh(); }, 5000);
    return () => { active = false; clearInterval(timer); };
  }, []);
  useEffect(() => {
    let active = true;
    async function load() {
      try { const page = await getUsageCalls(skip); if (active) { setCalls(page.items); setMore(page.has_more); } }
      catch { if (active) setError('Could not load the generation call ledger.'); }
    }
    void load();
    const timer = setInterval(() => { void load(); }, 5000);
    return () => { active = false; clearInterval(timer); };
  }, [skip]);
  async function saveLimit() {
    if (limit === '') return;
    setBusy(true); setError(''); setNotice('');
    try { await updateMonthlyLimit(limit); setUsage(await getUsage()); setLimit(''); setNotice('Monthly limit saved.'); }
    catch (problem) { setError(apiErrorMessage(problem, 'Could not update the monthly limit')); }
    finally { setBusy(false); }
  }
  const percentage = usage ? Math.min(100, Number(usage.monthly_limit_usd) > 0 ? Number(usage.committed_usd) / Number(usage.monthly_limit_usd) * 100 : 0) : 0;
  return <div className="space-y-7"><div><h1 className="text-3xl font-bold">Generation spending</h1><p className="mt-2 text-muted-foreground">Estimated LLM charges in USD, using reported tokens and configured model prices.</p><p className="mt-1 text-sm text-muted-foreground">Excludes search, embeddings, standalone style analysis, tax and provider billing adjustments.</p></div>
    {error && <p role="alert" className="text-red-700">{error}</p>}{notice && <p role="status" className="text-green-700">{notice}</p>}
    {usage ? <><section className="rounded-lg border bg-white dark:bg-zinc-900 p-6 space-y-5"><div className="flex flex-wrap gap-8 justify-between"><div><p className="text-sm text-muted-foreground">This month, from {new Date(usage.period_start).toLocaleDateString()}</p><p className="text-3xl font-semibold mt-2">{usd(usage.committed_usd)} <span className="text-lg text-muted-foreground">of {usd(usage.monthly_limit_usd)}</span></p></div><div className="text-sm space-y-2"><p>Measured estimate <strong>{usd(usage.estimated_usd)}</strong></p><p>Held for pending or uncertain calls <strong>{usd(usage.held_usd)}</strong></p><p>Available <strong>{usd(usage.remaining_usd)}</strong></p></div></div><div className="h-3 rounded-full bg-muted overflow-hidden" role="progressbar" aria-label="Monthly generation budget used" aria-valuenow={percentage} aria-valuemin={0} aria-valuemax={100}><div className="h-full bg-primary" style={{ width: `${percentage}%` }} /></div><p className="text-sm text-muted-foreground">Before each model call, the worker reserves a conservative amount. Interrupted calls keep their reservation until usage can be reconciled. Limits reset by calendar month in UTC.</p></section>
      <form className="flex flex-wrap items-end gap-3" onSubmit={event => { event.preventDefault(); void saveLimit(); }}><div><Label htmlFor="monthly-limit">Monthly spending limit (USD)</Label><Input id="monthly-limit" type="number" min="0" max="100000" step="0.01" placeholder={Number(usage.monthly_limit_usd).toString()} value={limit} onChange={event => setLimit(event.target.value)} /></div><Button disabled={busy || limit === ''}>Save limit</Button></form>
      <section><h2 className="text-lg font-semibold mb-3">Usage by model</h2><div className="overflow-x-auto border rounded-lg"><table className="w-full text-sm text-left"><thead className="bg-muted/40 border-b"><tr><th className="p-4">Model</th><th className="p-4">Calls</th><th className="p-4">Reported input / output tokens</th><th className="p-4">Estimated</th><th className="p-4">Held</th></tr></thead><tbody>{usage.models.map(model => <tr key={model.provider + model.model} className="border-b last:border-0"><td className="p-4">{model.provider} / {model.model}</td><td className="p-4">{model.calls}</td><td className="p-4">{model.input_tokens.toLocaleString()} / {model.output_tokens.toLocaleString()}</td><td className="p-4">{usd(model.estimated_usd)}</td><td className="p-4">{usd(model.held_usd)}</td></tr>)}</tbody></table>{!usage.models.length && <p className="p-6 text-muted-foreground">No generation calls this month.</p>}</div></section></> : <p role="status">Loading spending…</p>}
    <section><h2 className="text-lg font-semibold mb-3">Generation call ledger</h2><div className="overflow-x-auto border rounded-lg"><table className="w-full text-sm text-left"><thead className="bg-muted/40 border-b"><tr><th className="p-3">Model / call</th><th className="p-3">Status</th><th className="p-3">Estimate or hold</th><th className="p-3">Run</th></tr></thead><tbody>{calls.map(call => <tr key={call.id} className="border-b last:border-0"><td className="p-3">{call.provider} / {call.model}<span className="block text-xs text-muted-foreground break-all">{call.id}</span></td><td className="p-3">{call.status}</td><td className="p-3">{usd(call.estimated_usd ?? call.reserved_usd)}</td><td className="p-3">{call.job_id && <Link className="text-primary underline" to={`/runs/${call.job_id}`}>Open run</Link>}</td></tr>)}</tbody></table>{!calls.length && <p className="p-4 text-muted-foreground">No calls recorded yet.</p>}</div><div className="flex gap-3 mt-3"><Button variant="outline" disabled={!skip} onClick={() => setSkip(value => Math.max(0, value - 20))}>Previous calls</Button><Button variant="outline" disabled={!more} onClick={() => setSkip(value => value + 20)}>Older calls</Button></div><p className="text-sm text-muted-foreground mt-3">An administrator can reconcile unresolved calls using provider-verified usage. Holds are never automatically discarded.</p></section>
    <section><h2 className="text-lg font-semibold mb-3">Configured prices per million tokens</h2><ul className="divide-y border rounded-lg">{rates.map(rate => <li key={rate.provider + rate.model} className="p-4 flex flex-wrap justify-between gap-3 text-sm"><span>{rate.provider} / {rate.model}</span><span>Input {usd(rate.input_per_million)} · Output {usd(rate.output_per_million)}</span></li>)}</ul><p className="text-sm text-muted-foreground mt-3">An administrator configures these rates. Unpriced cloud models cannot start generation.</p></section>
  </div>;
}

import { useCallback, useEffect, useRef, useState } from 'react';
import axios from 'axios';
import { Link, useParams } from 'react-router-dom';
import { getArticle, saveArticle, getRevisions, getRevision, restoreRevision } from '@/lib/workspaceApi';
import type { Article, Revision } from '@/lib/workspaceApi';
import { readRecovery, storeRecovery, clearRecovery, sameText, acknowledgeRecovery } from '@/lib/draftRecovery';
import { apiErrorMessage } from '@/lib/apiError';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import MarkdownWithCitations from '@/components/custom/MarkdownWithCitations';

function Editor({ article }: { article: Article }) {
  const [recovery] = useState(() => readRecovery(article.id));
  const [base, setBase] = useState(article);
  const [title, setTitle] = useState(recovery?.title ?? article.title);
  const [content, setContent] = useState(recovery?.content ?? article.content);
  const [conflict, setConflict] = useState(!!recovery && recovery.base_version !== article.version && !sameText(recovery, article));
  const [error, setError] = useState('');
  const [warning, setWarning] = useState('');
  const [saving, setSaving] = useState(false);
  const [revisions, setRevisions] = useState<Revision[]>([]);
  const [more, setMore] = useState(false);
  const [selected, setSelected] = useState<Revision | null>(null);
  const [revisionBusy, setRevisionBusy] = useState(false);
  const active = useRef(true);
  const inFlight = useRef(false);
  const latest = useRef({ title, content });
  const dirty = !sameText({ title, content }, base);
  useEffect(() => { active.current = true; return () => { active.current = false; }; }, []);
  const persistRecovery = useCallback((text: { title: string; content: string }, version: number) => {
    try { storeRecovery(article.id, { ...text, base_version: version }); }
    catch { if (active.current) setWarning('Browser recovery is unavailable. Keep this page open until your changes are saved.'); }
  }, [article.id]);
  function edit(nextTitle: string, nextContent: string) {
    latest.current = { title: nextTitle, content: nextContent };
    persistRecovery(latest.current, base.version);
    setTitle(nextTitle); setContent(nextContent); setError('');
  }
  const save = useCallback(async () => {
    if (inFlight.current || conflict || sameText(latest.current, base) || !latest.current.title.trim()) return;
    inFlight.current = true; setSaving(true); setError('');
    const text = { ...latest.current };
    try {
      const saved = await saveArticle(article.id, text.title, text.content, base.version);
      const current = { ...latest.current, base_version: base.version };
      const normalized = { ...current, title: current.title === text.title ? saved.title : current.title };
      try { acknowledgeRecovery(article.id, { ...saved, base_version: saved.version }, current, normalized); }
      catch { if (active.current) setWarning('Browser recovery could not be updated. The server save succeeded.'); }
      latest.current = { title: normalized.title, content: normalized.content };
      if (active.current) { setTitle(normalized.title); setBase(saved); }
    } catch (problem) {
      if (active.current) {
        if (axios.isAxiosError(problem) && problem.response?.status === 409) setConflict(true);
        setError(apiErrorMessage(problem, 'Save failed. Your changes are kept in this browser tab; retry when connected.'));
      }
    } finally { inFlight.current = false; if (active.current) setSaving(false); }
  }, [article.id, base, conflict]);
  useEffect(() => {
    if (!dirty || saving || conflict || error || !title.trim()) return;
    const timer = setTimeout(() => { void save(); }, 900);
    return () => clearTimeout(timer);
  }, [title, content, dirty, saving, conflict, error, save]);
  useEffect(() => {
    if (!dirty) return;
    const warn = (event: BeforeUnloadEvent) => { event.preventDefault(); event.returnValue = ''; };
    window.addEventListener('beforeunload', warn);
    return () => window.removeEventListener('beforeunload', warn);
  }, [dirty]);
  useEffect(() => {
    let current = true;
    getRevisions(article.id).then(page => { if (current) { setRevisions(page.items); setMore(page.has_more); } })
      .catch(() => { if (current) setWarning('Revision history could not be loaded. Your draft is still editable.'); });
    return () => { current = false; };
  }, [article.id, base.version]);
  function applySaved(saved: Article) {
    latest.current = { title: saved.title, content: saved.content };
    setBase(saved); setTitle(saved.title); setContent(saved.content); setConflict(false); setError(''); clearRecovery(article.id);
  }
  async function resolveConflict(keepEdits: boolean) {
    setRevisionBusy(true);
    try {
      const current = await getArticle(article.id);
      if (keepEdits) { setBase(current); setConflict(false); setError(''); persistRecovery(latest.current, current.version); }
      else applySaved(current);
    } catch (problem) { setError(apiErrorMessage(problem, 'Could not load the current version')); }
    finally { setRevisionBusy(false); }
  }
  async function chooseRevision(id: string) {
    setRevisionBusy(true);
    try { setSelected(await getRevision(article.id, id)); }
    catch (problem) { setError(apiErrorMessage(problem, 'Could not load revision')); }
    finally { setRevisionBusy(false); }
  }
  async function restore() {
    if (!selected || dirty || saving) return;
    setRevisionBusy(true);
    try { applySaved(await restoreRevision(article.id, selected.id, base.version)); setSelected(null); }
    catch (problem) { if (axios.isAxiosError(problem) && problem.response?.status === 409) setConflict(true); setError(apiErrorMessage(problem, 'Could not restore revision')); }
    finally { setRevisionBusy(false); }
  }
  function download() {
    const url = URL.createObjectURL(new Blob([content], { type: 'text/markdown;charset=utf-8' }));
    const anchor = document.createElement('a'); anchor.href = url; anchor.download = (title || 'draft').replace(/[^a-z0-9_-]/gi, '_') + '.md'; anchor.click(); URL.revokeObjectURL(url);
  }
  return <div className="space-y-5">
    <div className="flex flex-wrap justify-between gap-3 items-center"><Link to="/drafts" className="text-primary underline">All drafts</Link><div className="flex items-center gap-3"><span role="status" aria-live="polite" className="text-sm text-muted-foreground">{conflict ? 'Save conflict' : saving ? 'Saving…' : dirty ? 'Unsaved changes' : `Saved · v${base.version}`}</span><Button variant="outline" onClick={download}>Download Markdown</Button><Button disabled={!dirty || saving || conflict || !title.trim()} onClick={() => void save()}>Save now</Button></div></div>
    <div><Label htmlFor="draft-title">Article title</Label><Input id="draft-title" maxLength={500} value={title} onChange={event => edit(event.target.value, content)} className="mt-2 text-xl font-semibold h-12" />{!title.trim() && <p role="alert" className="mt-2 text-sm text-red-700">Add a title to save your draft.</p>}</div>
    {(error || warning || conflict) && <div role="alert" className="border border-amber-300 rounded-lg bg-amber-50 text-amber-950 p-4 space-y-3"><p>{conflict ? 'A newer saved version exists. Your text is preserved here; choose which version to continue with.' : error || warning}</p>{conflict && <div className="flex flex-wrap gap-3"><Button disabled={revisionBusy} variant="outline" onClick={() => void resolveConflict(false)}>Load latest saved draft</Button><Button disabled={revisionBusy} onClick={() => void resolveConflict(true)}>Keep my edits on latest version</Button></div>}{error && !conflict && <Button variant="outline" onClick={() => void save()}>Retry save</Button>}</div>}
    <div className="grid xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_13rem] gap-4 items-start">
      <section className="min-w-0"><Label htmlFor="draft-content">Write in Markdown</Label><textarea id="draft-content" maxLength={1000000} value={content} onChange={event => edit(title, event.target.value)} className="mt-2 w-full min-h-[65vh] resize-y rounded-lg border bg-white dark:bg-zinc-900 p-5 text-sm leading-7 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary" spellCheck /><p className="text-xs text-muted-foreground mt-2">{content.trim() ? content.trim().split(/\s+/).length.toLocaleString() : 0} words · Changes autosave after a short pause.</p></section>
      <section className="min-w-0"><h2 className="text-sm font-medium mb-2">Preview</h2><div className="min-h-[65vh] rounded-lg border bg-white dark:bg-zinc-900 p-5 prose prose-zinc dark:prose-invert prose-sm max-w-none break-words"><MarkdownWithCitations content={content} /></div></section>
      <aside className="xl:border-l xl:pl-4"><h2 className="font-semibold mb-3">Revision history</h2><div className="max-h-[50vh] overflow-auto space-y-2">{revisions.map(revision => <button key={revision.id} disabled={revisionBusy} onClick={() => void chooseRevision(revision.id)} className={`block w-full text-left text-sm rounded border p-3 focus-visible:ring-2 focus-visible:ring-primary ${selected?.id === revision.id ? 'bg-primary/10 border-primary' : 'hover:bg-muted'}`}><strong>Version {revision.version}</strong><span className="block text-xs text-muted-foreground mt-1">{revision.reason} · {new Date(revision.created_at).toLocaleString()}</span></button>)}</div>{more && <Button className="mt-3" variant="outline" onClick={() => { void getRevisions(article.id, revisions.length).then(page => { setRevisions(previous => [...previous, ...page.items]); setMore(page.has_more); }).catch(() => setWarning('Could not load more revisions')); }}>Load older revisions</Button>}
        {selected && <div className="mt-4 space-y-3"><h3 className="text-sm font-medium">Version {selected.version}</h3><div className="max-h-64 overflow-auto text-xs whitespace-pre-wrap rounded bg-muted p-3">{selected.content}</div><Button className="w-full" disabled={dirty || saving || revisionBusy || conflict} onClick={() => void restore()}>Restore this revision</Button><p className="text-xs text-muted-foreground">Save current edits first. Restoring creates a new revision.</p></div>}
      </aside>
    </div>
  </div>;
}
function Loader({ id }: { id: string }) {
  const [article, setArticle] = useState<Article | null>(null);
  const [error, setError] = useState('');
  useEffect(() => { let active = true; getArticle(id).then(value => { if (active) setArticle(value); }).catch(problem => { if (active) setError(apiErrorMessage(problem, 'Could not load draft')); }); return () => { active = false; }; }, [id]);
  return article ? <Editor article={article} /> : <p role={error ? 'alert' : 'status'}>{error || 'Loading draft…'}</p>;
}
export function DraftEditor() { const { id = '' } = useParams(); return <Loader key={id} id={id} />; }

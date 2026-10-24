import { api } from './api';
import type { OutlineSection } from './agentStream';

export type JobStatus = 'queued' | 'running' | 'awaiting_approval' | 'completed' | 'failed' | 'cancelled' | 'budget_exceeded';
export const stoppedStatuses = new Set<JobStatus>(['awaiting_approval', 'completed', 'failed', 'cancelled', 'budget_exceeded']);
export interface Job {
  id: string; topic: string; status: JobStatus; outline: OutlineSection[]; cancel_requested: boolean;
  error: string | null; active_step: string | null; cost_limit_usd: string; committed_usd: string;
  input_tokens: number; output_tokens: number; article_id: string | null; last_event_id: number;
  created_at: string; updated_at: string;
}
export interface Article {
  id: string; job_id: string | null; title: string; content: string; version: number; created_at: string; updated_at: string;
}
export interface Revision { id: string; version: number; title: string; reason: string; created_at: string; content?: string }
export interface ModelPrice { provider: string; model: string; input_per_million: string; output_per_million: string; max_output_tokens: number }
export interface Usage {
  period_start: string; monthly_limit_usd: string; estimated_usd: string; held_usd: string; committed_usd: string; remaining_usd: string;
  models: { provider: string; model: string; estimated_usd: string; held_usd: string; input_tokens: number; output_tokens: number; calls: number }[];
}
export interface Page<T> { items: T[]; has_more: boolean }
export const usd = (value: string | number) => new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', minimumFractionDigits: 2, maximumFractionDigits: 4 }).format(Number(value));
export const createJob = async (body: Record<string, unknown>): Promise<Job> => (await api.post('/jobs', body)).data;
export const getJobs = async (skip = 0): Promise<Page<Job>> => (await api.get('/jobs', { params: { skip } })).data;
export const getJob = async (id: string): Promise<Job> => (await api.get(`/jobs/${id}`)).data;
export const cancelJob = async (id: string): Promise<Job> => (await api.post(`/jobs/${id}/cancel`)).data;
export const resumeJob = async (id: string, body: { approved_outline?: OutlineSection[]; cost_limit_usd?: string }): Promise<Job> => (await api.post(`/jobs/${id}/resume`, body)).data;
export const getArticles = async (skip = 0): Promise<Page<Omit<Article, 'content'>>> => (await api.get('/articles', { params: { skip } })).data;
export const createArticle = async (title: string, content = ''): Promise<Article> => (await api.post('/articles', { title, content })).data;
export const getArticle = async (id: string): Promise<Article> => (await api.get(`/articles/${id}`)).data;
export const saveArticle = async (id: string, title: string, content: string, expected_version: number): Promise<Article> => (await api.patch(`/articles/${id}`, { title, content, expected_version })).data;
export const getRevisions = async (id: string, skip = 0): Promise<Page<Revision>> => (await api.get(`/articles/${id}/revisions`, { params: { skip } })).data;
export const getRevision = async (id: string, revision: string): Promise<Revision> => (await api.get(`/articles/${id}/revisions/${revision}`)).data;
export const restoreRevision = async (id: string, revision_id: string, expected_version: number): Promise<Article> => (await api.post(`/articles/${id}/restore`, { revision_id, expected_version })).data;
export const getUsage = async (): Promise<Usage> => (await api.get('/usage')).data;
export const getPrices = async (): Promise<{ models: ModelPrice[] }> => (await api.get('/usage/models')).data;
export const updateMonthlyLimit = async (monthly_limit_usd: string) => (await api.patch('/usage/limit', { monthly_limit_usd })).data;

// Keep a creation key until the response arrives, so a lost response can be retried safely.
export async function createJobOnce(payload: Record<string, unknown>): Promise<Job> {
  const serialized = JSON.stringify(payload);
  const key = 'blog-gen:pending-job';
  let cached: { payload: string; id: string } | null = null;
  try { cached = JSON.parse(sessionStorage.getItem(key) || 'null'); } catch { /* Replace corrupt recovery data. */ }
  if (!cached || cached.payload !== serialized) {
    cached = { payload: serialized, id: crypto.randomUUID() };
    sessionStorage.setItem(key, JSON.stringify(cached));
  }
  const job = await createJob({ ...payload, idempotency_key: cached.id });
  sessionStorage.removeItem(key);
  return job;
}

export interface UsageCall { id: string; job_id: string | null; provider: string; model: string; input_tokens: number | null; output_tokens: number | null; estimated_usd: string | null; reserved_usd: string; status: 'reserved' | 'recorded' | 'unresolved'; created_at: string }
export const getUsageCalls = async (skip = 0): Promise<Page<UsageCall>> => (await api.get('/usage/calls', { params: { skip } })).data;

import { fetchEventSource } from '@microsoft/fetch-event-source';
import { API_URL } from './apiConfig';

export interface OutlineSection {
  id: string;
  title: string;
  intent: string;
  source_ids: string[];
  content?: string | null;
}

export interface AgentEvent {
  step: string;
  status?: 'running' | 'completed' | 'failed';
  log?: string;
  output?: unknown;
  type?: 'interrupt' | 'error' | 'event' | 'end';
  payload?: OutlineSection[];
  finalContent?: string;
}

/** Safe to reconnect: subscriptions are GETs and carry a persisted event cursor. */
export async function subscribeJobEvents(
  jobId: string, after: number, signal: AbortSignal,
  onMessage: (id: number, event: string, data: Record<string, unknown>) => void,
  onConnection: (connected: boolean) => void,
) {
  if (signal.aborted) return;
  await fetchEventSource(`${API_URL}/jobs/${jobId}/events?after=${after}`, {
    method: 'GET', signal, openWhenHidden: true,
    headers: { Authorization: `Bearer ${localStorage.getItem('token')}` },
    async onopen(response) {
      if (!response.ok || !response.headers.get('content-type')?.startsWith('text/event-stream')) {
        throw new Error(`Unable to subscribe (${response.status})`);
      }
      onConnection(true);
    },
    onmessage(message) {
      if (message.data && message.id) onMessage(Number(message.id), message.event, JSON.parse(message.data));
    },
    onclose() { onConnection(false); },
    onerror(error) { onConnection(false); throw error; },
  });
}

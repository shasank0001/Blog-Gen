import { useEffect, useRef, useState } from 'react';
import { subscribeJobEvents } from '@/lib/agentStream';
import type { AgentEvent } from '@/lib/agentStream';
import { getJob, stoppedStatuses } from '@/lib/workspaceApi';
import type { Job } from '@/lib/workspaceApi';
import { apiErrorMessage } from '@/lib/apiError';

export function useJob(id: string) {
  const [job, setJob] = useState<Job | null>(null);
  const [events, setEvents] = useState<AgentEvent[]>([]);
  const [connected, setConnected] = useState(false);
  const [error, setError] = useState('');
  const [epoch, setEpoch] = useState(0);
  const cursor = useRef(0);
  useEffect(() => {
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout>;
    async function refresh() {
      const latest = await getJob(id);
      if (!controller.signal.aborted) setJob(latest);
      return latest;
    }
    async function run() {
      while (!controller.signal.aborted) {
        try {
          await refresh();
          await subscribeJobEvents(id, cursor.current, controller.signal, (eventId, name, data) => {
            if (controller.signal.aborted || eventId <= cursor.current) return;
            cursor.current = eventId;
            const event: AgentEvent = name === 'step_start' || name === 'step_complete'
              ? { step: String(data.step), type: 'event', status: name === 'step_start' ? 'running' : 'completed', output: data.output }
              : { step: 'system', type: 'event', log: name === 'status' ? `Run ${String(data.status)}` : name === 'interrupt' ? 'Outline ready for approval' : 'Article saved' };
            setEvents(previous => [...previous.slice(-199), event]);
            if (name === 'status' || name === 'interrupt' || name === 'end') void refresh().catch(() => {});
          }, value => { if (!controller.signal.aborted) { setConnected(value); if (value) setError(''); } });
          if (controller.signal.aborted) return;
          const latest = await refresh();
          if (stoppedStatuses.has(latest.status)) return;
        } catch (problem) {
          if (controller.signal.aborted) return;
          setError(apiErrorMessage(problem, 'Connection interrupted. Reconnecting to saved progress…'));
        }
        await new Promise<void>(resolve => { timer = setTimeout(resolve, 2000); controller.signal.addEventListener('abort', () => { clearTimeout(timer); resolve(); }, { once: true }); });
      }
    }
    void run();
    const poll = setInterval(() => { void refresh().catch(() => {}); }, 3000);
    return () => { controller.abort(); clearTimeout(timer); clearInterval(poll); };
  }, [id, epoch]);
  return { job, events, connected, error, reconnect: () => setEpoch(value => value + 1) };
}

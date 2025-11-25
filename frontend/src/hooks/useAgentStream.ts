import { useState, useCallback } from 'react';
import { fetchEventSource } from '@microsoft/fetch-event-source';

export interface AgentEvent {
  step: string;
  status?: 'running' | 'completed' | 'failed';
  log?: string;
  output?: any;
  type?: 'interrupt' | 'error' | 'event';
  payload?: any;
}

export const useAgentStream = () => {
  const [events, setEvents] = useState<AgentEvent[]>([]);
  const [activeNode, setActiveNode] = useState<string>('');
  const [isConnected, setIsConnected] = useState(false);
  const [threadId, setThreadId] = useState<string | null>(null);

  const stream = useCallback(async (url: string, body: any) => {
    setIsConnected(true);
    // Don't clear events on resume, only on new run? 
    // For now, let the caller decide when to clear.
    
    const token = localStorage.getItem('token');
    
    try {
      await fetchEventSource(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        },
        body: JSON.stringify(body),
        onopen(response) {
          if (response.ok) {
            return Promise.resolve();
          } else if (response.status === 401 || response.status === 403) {
            // Handle authentication errors
            localStorage.removeItem('token');
            localStorage.removeItem('user');
            window.location.href = '/login';
            return Promise.reject(new Error('Authentication required'));
          } else {
            return Promise.reject(new Error(`Failed to connect: ${response.statusText}`));
          }
        },
        onmessage(msg) {
          // msg.event is the event name (e.g., 'step_start', 'metadata')
          // msg.data is the JSON string
          
          if (!msg.data) return;
          
          try {
            const data = JSON.parse(msg.data);
            
            if (msg.event === 'metadata') {
              if (data.thread_id) {
                setThreadId(data.thread_id);
              }
            } else if (msg.event === 'step_start') {
              setActiveNode(data.step);
              setEvents(prev => [...prev, { 
                step: data.step, 
                status: 'running',
                type: 'event'
              }]);
            } else if (msg.event === 'step_complete') {
              setEvents(prev => {
                // Find the running step and update it, or append new one
                // Actually, for a log, we might just want to append a completion event
                // or update the last one.
                // Let's append for now to show history.
                return [...prev, {
                  step: data.step,
                  status: 'completed',
                  output: data.output,
                  type: 'event'
                }];
              });
            } else if (msg.event === 'interrupt') {
              setEvents(prev => [...prev, {
                step: 'system',
                type: 'interrupt',
                payload: data.payload
              }]);
            } else if (msg.event === 'error') {
               setEvents(prev => [...prev, {
                step: 'system',
                type: 'error',
                log: data.error
              }]);
            }
          } catch (e) {
            console.error('Failed to parse event data', e);
          }
        },
        onclose() {
          setIsConnected(false);
        },
        onerror(err) {
          console.error('Stream error:', err);
          setEvents(prev => [...prev, { step: 'system', type: 'error', log: String(err) }]);
          setIsConnected(false);
          throw err; // Rethrow to stop retrying
        }
      });
    } catch (err) {
      // Error handled in onerror
    }
  }, []);

  const startStream = useCallback((payload: any) => {
    setEvents([]);
    setThreadId(null);
    stream('http://localhost:8000/api/v1/agent/stream', payload);
  }, [stream]);

  const resumeStream = useCallback((threadId: string, approvedOutline: any) => {
    // We don't clear events here, so we can see the history
    stream('http://localhost:8000/api/v1/agent/resume', {
      thread_id: threadId,
      approved_outline: approvedOutline
    });
  }, [stream]);

  return { events, activeNode, isConnected, threadId, startStream, resumeStream };
};

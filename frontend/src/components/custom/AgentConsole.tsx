import { useEffect, useRef } from 'react';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import type { AgentEvent } from '@/hooks/useAgentStream';
import { Terminal, CheckCircle2, AlertCircle, Loader2, Link as LinkIcon, FileText, List, User } from 'lucide-react';

interface AgentConsoleProps {
  events: AgentEvent[];
  activeNode: string;
  isConnected: boolean;
}

const RenderOutput = ({ output }: { output: any }) => {
  if (!output) return null;

  let data = output;
  if (typeof output === 'string') {
    try {
      data = JSON.parse(output);
    } catch {
      // If it's just a string, display it as is
      return <p className="text-zinc-300 whitespace-pre-wrap">{output}</p>;
    }
  }

  // Handle Command objects (they have 'update' and 'goto' properties)
  if (data.update || data.goto) {
    const updates = data.update || {};
    const goto = data.goto;
    
    return (
      <div className="mt-2 space-y-1">
        {Object.keys(updates).length > 0 && (
          <div className="flex items-center gap-2 text-zinc-400 text-xs">
            <CheckCircle2 className="h-3 w-3 text-green-500" />
            <span>Updated: {Object.keys(updates).join(', ')}</span>
          </div>
        )}
        {goto && (
          <div className="flex items-center gap-2 text-zinc-400 text-xs">
            <span className="text-blue-400">→ Next: {goto}</span>
          </div>
        )}
      </div>
    );
  }

  // Handle Internal Indexer Output
  if (data.internal_links && Array.isArray(data.internal_links)) {
    return (
      <div className="mt-2 space-y-2">
        <div className="flex items-center gap-2 text-blue-400">
          <LinkIcon className="h-4 w-4" />
          <span className="font-semibold">Found {data.internal_links.length} Internal Links</span>
        </div>
        <div className="grid gap-1 pl-6">
          {data.internal_links.slice(0, 5).map((link: string, i: number) => (
            <a key={i} href={link} target="_blank" rel="noopener noreferrer" className="text-xs text-zinc-400 hover:text-blue-400 truncate block">
              {link}
            </a>
          ))}
          {data.internal_links.length > 5 && (
            <span className="text-xs text-zinc-500 italic">...and {data.internal_links.length - 5} more</span>
          )}
        </div>
      </div>
    );
  }

  // Handle Style Analyst Output
  if (data.style_profile) {
    return (
      <div className="mt-2 space-y-2 bg-zinc-900/50 p-3 rounded border border-zinc-800">
        <div className="flex items-center gap-2 text-purple-400">
          <User className="h-4 w-4" />
          <span className="font-semibold">Style Profile Analysis</span>
        </div>
        <div className="grid grid-cols-2 gap-2 text-xs">
          {Object.entries(data.style_profile).map(([key, value]) => (
            <div key={key} className="flex flex-col">
              <span className="text-zinc-500 capitalize">{key.replace(/_/g, ' ')}</span>
              <span className="text-zinc-300">{String(value)}</span>
            </div>
          ))}
        </div>
      </div>
    );
  }

  // Handle Research Data Output
  if (data.research_data && Array.isArray(data.research_data)) {
    return (
      <div className="mt-2 space-y-2">
        <div className="flex items-center gap-2 text-purple-400">
          <FileText className="h-4 w-4" />
          <span className="font-semibold">Research Gathered ({data.research_data.length} sources)</span>
        </div>
        <div className="grid gap-2 pl-6 max-h-40 overflow-y-auto pr-2">
          {data.research_data.map((item: any, i: number) => (
            <div key={i} className="bg-zinc-900/50 p-2 rounded border border-zinc-800 text-xs">
              <div className="flex items-center justify-between mb-1">
                <span className="font-semibold text-zinc-300 truncate max-w-[200px]">{item.title}</span>
                <Badge variant="outline" className="text-[10px] h-4 px-1 border-zinc-700 text-zinc-500">
                  {item.source}
                </Badge>
              </div>
              {item.url && item.url !== "Internal Knowledge Base" && item.url !== "User Input" && (
                <a href={item.url} target="_blank" rel="noopener noreferrer" className="text-blue-500 hover:underline truncate block mb-1">
                  {item.url}
                </a>
              )}
              <p className="text-zinc-500 line-clamp-2">{item.content}</p>
            </div>
          ))}
        </div>
      </div>
    );
  }

  // Handle Planner Output (Outline) - check both formats
  if (data.outline) {
    const sections = Array.isArray(data.outline) ? data.outline : (data.outline.sections || []);
    if (sections.length > 0) {
      return (
        <div className="mt-2 space-y-2">
          <div className="flex items-center gap-2 text-yellow-400">
            <List className="h-4 w-4" />
            <span className="font-semibold">Generated Outline ({sections.length} sections)</span>
          </div>
          <div className="pl-6 space-y-1">
            {sections.map((section: any, i: number) => (
              <div key={i} className="text-xs">
                <div className="flex items-start gap-2">
                  <span className="text-zinc-500 font-mono">{i + 1}.</span>
                  <div className="flex-1">
                    <div className="text-zinc-300 font-medium">{section.title}</div>
                    {section.intent && (
                      <div className="text-zinc-600 text-[10px] mt-0.5 italic">{section.intent.substring(0, 80)}...</div>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      );
    }
  }

  // Handle Final Article
  if (data.final_content) {
    return (
      <div className="mt-2">
        <div className="flex items-center gap-2 text-green-400 mb-2">
          <FileText className="h-4 w-4" />
          <span className="font-semibold">Article Generated</span>
        </div>
        <div className="bg-zinc-900 p-3 rounded text-xs text-zinc-400 max-h-32 overflow-y-auto whitespace-pre-wrap">
          {data.final_content.substring(0, 500)}...
        </div>
      </div>
    );
  }

  // Handle Draft Sections Update
  if (data.draft_sections) {
    const sectionCount = Object.keys(data.draft_sections).length;
    const sectionIds = Object.keys(data.draft_sections);
    return (
      <div className="mt-2 space-y-2">
        <div className="flex items-center gap-2 text-green-400">
          <CheckCircle2 className="h-4 w-4" />
          <span className="font-semibold">Section Drafted ({sectionCount} total)</span>
        </div>
        <div className="pl-6 space-y-1 text-xs text-zinc-400">
          {sectionIds.slice(-3).map((id, i) => (
            <div key={i} className="flex items-center gap-2">
              <span className="text-zinc-600">✓</span>
              <span>{id}</span>
            </div>
          ))}
        </div>
      </div>
    );
  }

  // Handle Critique Feedback
  if (data.critique_feedback && typeof data.critique_feedback === 'object') {
    const feedbackEntries = Object.entries(data.critique_feedback);
    if (feedbackEntries.length > 0) {
      const [sectionId, feedback] = feedbackEntries[feedbackEntries.length - 1];
      return (
        <div className="mt-2 space-y-2">
          <div className="flex items-center gap-2 text-yellow-400">
            <AlertCircle className="h-4 w-4" />
            <span className="font-semibold">Critique for {sectionId}</span>
          </div>
          <div className="pl-6 text-xs text-zinc-400 bg-zinc-900/50 p-2 rounded border border-zinc-800">
            {String(feedback).substring(0, 200)}...
          </div>
        </div>
      );
    }
  }

  // Handle Section Retries
  if (data.section_retries && typeof data.section_retries === 'object') {
    return (
      <div className="mt-2 flex items-center gap-2 text-zinc-400 text-xs">
        <span className="text-orange-400">↻ Revision in progress...</span>
      </div>
    );
  }

  // Handle current_section_index
  if (data.current_section_index !== undefined) {
    return (
      <div className="mt-2 flex items-center gap-2 text-zinc-400 text-xs">
        <span>Working on section {data.current_section_index + 1}</span>
      </div>
    );
  }

  // Fallback for generic objects - but filter out empty/unhelpful data
  if (typeof data === 'object') {
    // Skip objects that are just state updates without meaningful display data
    const keys = Object.keys(data);
    if (keys.length === 0) {
      return null;
    }
    
    // Only show JSON for objects that don't match our specific handlers
    // but have meaningful content
    const meaningfulKeys = keys.filter(k => 
      !['goto', 'update', '__typename'].includes(k)
    );
    
    if (meaningfulKeys.length === 0) {
      return null;
    }

    // For small objects, display them inline
    if (meaningfulKeys.length <= 3) {
      return (
        <div className="mt-2 space-y-1 text-xs">
          {meaningfulKeys.map(key => (
            <div key={key} className="flex gap-2 text-zinc-400">
              <span className="text-zinc-600">{key}:</span>
              <span>{String(data[key]).substring(0, 100)}</span>
            </div>
          ))}
        </div>
      );
    }

    // For larger objects, collapse into a summary
    return (
      <details className="mt-2 text-xs">
        <summary className="cursor-pointer text-zinc-500 hover:text-zinc-400">
          View output data ({meaningfulKeys.length} fields)
        </summary>
        <pre className="mt-2 p-2 bg-zinc-900 rounded text-zinc-400 overflow-x-auto max-h-40">
          {JSON.stringify(data, null, 2)}
        </pre>
      </details>
    );
  }

  return <p className="text-zinc-300 whitespace-pre-wrap">{String(data)}</p>;
};

export const AgentConsole = ({ events, activeNode, isConnected }: AgentConsoleProps) => {
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollIntoView({ behavior: 'smooth', block: 'end' });
    }
  }, [events]);

  // Helper to determine phase changes
  const getPhase = (step: string) => {
    if (['internal_indexer', 'style_analyst', 'researcher'].includes(step)) return 'Research & Analysis';
    if (['planner', 'human_approval'].includes(step)) return 'Planning';
    if (['writer', 'critic', 'visuals'].includes(step)) return 'Content Generation';
    if (step === 'publisher') return 'Publishing';
    return null;
  };

  // Insert phase separators
  const eventsWithPhases = events.reduce((acc: any[], event, index) => {
    const currentPhase = getPhase(event.step);
    const prevPhase = index > 0 ? getPhase(events[index - 1].step) : null;
    
    if (currentPhase && currentPhase !== prevPhase) {
      acc.push({ type: 'phase_separator', phase: currentPhase, key: `phase-${index}` });
    }
    acc.push({ ...event, key: `event-${index}` });
    return acc;
  }, []);

  return (
    <Card className="h-[600px] flex flex-col bg-zinc-950 text-zinc-50 border-zinc-800">
      <CardHeader className="flex flex-row items-center justify-between border-b border-zinc-800 py-4">
        <div className="flex items-center gap-2">
          <Terminal className="h-5 w-5 text-green-500" />
          <CardTitle className="text-lg font-mono">Agent Console</CardTitle>
        </div>
        <div className="flex items-center gap-2">
          {isConnected ? (
            <Badge variant="outline" className="border-green-500 text-green-500 animate-pulse">
              Live
            </Badge>
          ) : (
            <Badge variant="outline" className="border-zinc-600 text-zinc-400">
              Offline
            </Badge>
          )}
          {activeNode && (
            <Badge className="bg-blue-600 hover:bg-blue-700">
              Node: {activeNode}
            </Badge>
          )}
        </div>
      </CardHeader>
      <CardContent className="flex-1 p-0 overflow-hidden">
        <ScrollArea className="h-full p-4">
          <div className="space-y-4 font-mono text-sm">
            {eventsWithPhases.map((item) => {
              // Render phase separator
              if (item.type === 'phase_separator') {
                return (
                  <div key={item.key} className="flex items-center gap-3 my-6">
                    <div className="h-px flex-1 bg-gradient-to-r from-transparent via-zinc-700 to-transparent"></div>
                    <span className="text-zinc-500 text-xs font-semibold uppercase tracking-wider px-3 py-1 bg-zinc-900 rounded-full border border-zinc-800">
                      {item.phase}
                    </span>
                    <div className="h-px flex-1 bg-gradient-to-r from-transparent via-zinc-700 to-transparent"></div>
                  </div>
                );
              }

              const event = item;
              const index = parseInt(item.key.split('-')[1]);
              // Get a friendly node name
              const getNodeDisplayName = (step: string) => {
                const names: Record<string, string> = {
                  'internal_indexer': '🔗 Internal Indexer',
                  'style_analyst': '🎨 Style Analyst',
                  'researcher': '🔍 Researcher',
                  'planner': '📋 Planner',
                  'human_approval': '👤 Human Approval',
                  'writer': '✍️ Writer',
                  'critic': '🔎 Critic',
                  'visuals': '📊 Visuals Generator',
                  'publisher': '📤 Publisher'
                };
                return names[step] || step;
              };

              return (
                <div key={index} className="flex gap-3 animate-in fade-in slide-in-from-bottom-2">
                  <div className="mt-1 flex-shrink-0">
                    {event.status === 'completed' ? (
                      <CheckCircle2 className="h-4 w-4 text-green-500" />
                    ) : event.type === 'error' ? (
                      <AlertCircle className="h-4 w-4 text-red-500" />
                    ) : (
                      <Loader2 className="h-4 w-4 text-blue-500 animate-spin" />
                    )}
                  </div>
                  <div className="flex-1 space-y-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="font-bold text-blue-400 text-sm">
                        {getNodeDisplayName(event.step)}
                      </span>
                      {event.status && (
                        <Badge 
                          variant={event.status === 'completed' ? 'default' : 'outline'}
                          className={`text-[10px] h-4 px-1.5 ${
                            event.status === 'completed' 
                              ? 'bg-green-950 text-green-400 border-green-800' 
                              : 'border-zinc-700 text-zinc-500'
                          }`}
                        >
                          {event.status}
                        </Badge>
                      )}
                    </div>
                    {event.log && (
                      <p className="text-zinc-300 text-sm whitespace-pre-wrap leading-relaxed">{event.log}</p>
                    )}
                    {event.output && (
                      <RenderOutput output={event.output} />
                    )}
                  </div>
                </div>
              );
            })}
            <div ref={scrollRef} />
          </div>
        </ScrollArea>
      </CardContent>
    </Card>
  );
};

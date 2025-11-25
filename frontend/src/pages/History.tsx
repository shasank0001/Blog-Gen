import { useEffect, useState } from 'react';
import { getThreads, getAgentState } from '@/lib/api';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Loader2, FileText, Calendar, Clock, Download } from 'lucide-react';
import MarkdownWithCitations from '@/components/custom/MarkdownWithCitations';
import { format } from 'date-fns';

interface Thread {
  id: string;
  topic: string;
  status: 'running' | 'completed' | 'failed';
  created_at: string;
  updated_at?: string;
}

export const History = () => {
  const [threads, setThreads] = useState<Thread[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedThread, setSelectedThread] = useState<string | null>(null);
  const [threadContent, setThreadContent] = useState<string | null>(null);
  const [contentLoading, setContentLoading] = useState(false);

  useEffect(() => {
    fetchThreads();
  }, []);

  const fetchThreads = async () => {
    try {
      const data = await getThreads();
      setThreads(data);
    } catch (error) {
      console.error("Failed to fetch threads", error);
    } finally {
      setLoading(false);
    }
  };

  const handleViewThread = async (threadId: string) => {
    if (selectedThread === threadId) {
      setSelectedThread(null);
      setThreadContent(null);
      return;
    }

    setSelectedThread(threadId);
    setContentLoading(true);
    try {
      const state = await getAgentState(threadId);
      // Check if final_content exists in values
      if (state.values && state.values.final_content) {
        setThreadContent(state.values.final_content);
      } else {
        setThreadContent("No content available for this thread.");
      }
    } catch (error) {
      console.error("Failed to fetch thread state", error);
      setThreadContent("Error loading content.");
    } finally {
      setContentLoading(false);
    }
  };

  const downloadMarkdown = (content: string, filename: string) => {
    const blob = new Blob([content], { type: 'text/markdown' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${filename}.md`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">History</h1>
        <p className="text-muted-foreground">View past content generation runs.</p>
      </div>

      {loading ? (
        <div className="flex justify-center p-12">
          <Loader2 className="h-8 w-8 animate-spin text-primary" />
        </div>
      ) : threads.length === 0 ? (
        <Card>
          <CardContent className="flex flex-col items-center justify-center p-12 text-center">
            <FileText className="h-12 w-12 text-muted-foreground mb-4" />
            <h3 className="text-lg font-semibold">No history yet</h3>
            <p className="text-muted-foreground mb-4">Start generating content to see it here.</p>
            <Button onClick={() => window.location.href = '/generate'}>Go to Generator</Button>
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-4">
          {threads.map((thread) => (
            <Card key={thread.id} className="overflow-hidden">
              <CardHeader className="bg-zinc-50/50 dark:bg-zinc-900/50 pb-4">
                <div className="flex items-start justify-between">
                  <div className="space-y-1">
                    <CardTitle className="text-xl">{thread.topic}</CardTitle>
                    <CardDescription className="flex items-center gap-4 text-xs">
                      <span className="flex items-center gap-1">
                        <Calendar className="h-3 w-3" />
                        {format(new Date(thread.created_at), 'PPP')}
                      </span>
                      <span className="flex items-center gap-1">
                        <Clock className="h-3 w-3" />
                        {format(new Date(thread.created_at), 'p')}
                      </span>
                    </CardDescription>
                  </div>
                  <div className="flex items-center gap-2">
                    <Badge variant={thread.status === 'completed' ? 'default' : thread.status === 'failed' ? 'destructive' : 'secondary'}>
                      {thread.status}
                    </Badge>
                    <Button variant="outline" size="sm" onClick={() => handleViewThread(thread.id)}>
                      {selectedThread === thread.id ? 'Close' : 'View'}
                    </Button>
                  </div>
                </div>
              </CardHeader>
              
              {selectedThread === thread.id && (
                <CardContent className="p-6 border-t">
                  {contentLoading ? (
                    <div className="flex justify-center p-8">
                      <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
                    </div>
                  ) : (
                    <div className="space-y-4">
                      <div className="flex justify-end gap-2">
                        <Button variant="outline" size="sm" onClick={() => downloadMarkdown(threadContent || '', thread.topic)}>
                          <Download className="h-4 w-4 mr-2" />
                          Markdown
                        </Button>
                        {/* HTML Download omitted for simplicity as we don't have a converter handy in this file context */}
                      </div>
                      <div className="prose prose-zinc dark:prose-invert max-w-none p-4 border rounded-md bg-white dark:bg-zinc-950">
                        <MarkdownWithCitations content={threadContent || ''} />
                      </div>
                    </div>
                  )}
                </CardContent>
              )}
            </Card>
          ))}
        </div>
      )}
    </div>
  );
};

import { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { FileUploader } from '@/components/custom/FileUploader';
import { OutlineEditor } from '@/components/custom/OutlineEditor';
import { runAgent, resumeAgent } from '@/lib/api';
import { Loader2, Play, Plus, Trash2, CheckCircle, ArrowLeft } from 'lucide-react';
import ReactMarkdown from 'react-markdown';

export const GenerationWizard = () => {
  const [topic, setTopic] = useState('');
  const [toneUrls, setToneUrls] = useState('');
  const [availableBins, setAvailableBins] = useState<string[]>([]);
  const [selectedBins, setSelectedBins] = useState<string[]>([]);
  const [isRunning, setIsRunning] = useState(false);
  const [showUploader, setShowUploader] = useState(false);
  
  // Wizard State
  const [step, setStep] = useState<'config' | 'review' | 'generating' | 'complete'>('config');
  const [threadId, setThreadId] = useState<string | null>(null);
  const [generatedOutline, setGeneratedOutline] = useState<any[]>([]);
  const [finalArticle, setFinalArticle] = useState<string>('');

  useEffect(() => {
    const savedBins = localStorage.getItem('blog_gen_bins');
    if (savedBins) {
      setAvailableBins(JSON.parse(savedBins));
    }
  }, []);

  const handleBinAdded = (newBinId: string) => {
    if (!availableBins.includes(newBinId)) {
      const updatedBins = [...availableBins, newBinId];
      setAvailableBins(updatedBins);
      localStorage.setItem('blog_gen_bins', JSON.stringify(updatedBins));
      setSelectedBins(prev => [...prev, newBinId]);
    }
    setShowUploader(false);
  };

  const toggleBinSelection = (binId: string) => {
    setSelectedBins(prev => 
      prev.includes(binId) 
        ? prev.filter(id => id !== binId)
        : [...prev, binId]
    );
  };

  const removeBin = (binId: string) => {
    const updatedBins = availableBins.filter(id => id !== binId);
    setAvailableBins(updatedBins);
    localStorage.setItem('blog_gen_bins', JSON.stringify(updatedBins));
    setSelectedBins(prev => prev.filter(id => id !== binId));
  };

  const handleRun = async () => {
    if (!topic) return;
    setIsRunning(true);
    try {
      const urls = toneUrls.split('\n').filter(url => url.trim() !== '');
      const result = await runAgent(topic, urls, selectedBins);
      setThreadId(result.thread_id);
      
      if (result.status === 'interrupted') {
        setGeneratedOutline(result.state.outline);
        setStep('review');
      } else {
        setFinalArticle(result.state.final_content || 'No content generated.');
        setStep('complete');
      }
    } catch (error) {
      console.error('Failed to start agent:', error);
      alert('Failed to start agent. Check console for details.');
    } finally {
      setIsRunning(false);
    }
  };

  const handleApproveOutline = async (approvedOutline: any[]) => {
    if (!threadId) return;
    setStep('generating');
    try {
      const result = await resumeAgent(threadId, approvedOutline);
      setFinalArticle(result.state.final_content || 'No content generated.');
      setStep('complete');
    } catch (error) {
      console.error('Failed to resume agent:', error);
      alert('Failed to generate article. Check console for details.');
      setStep('review');
    }
  };

  if (step === 'review') {
    return (
      <div className="max-w-4xl mx-auto space-y-8">
        <div className="flex items-center space-x-4">
          <Button variant="ghost" onClick={() => setStep('config')}>
            <ArrowLeft className="mr-2 h-4 w-4" /> Back
          </Button>
          <h2 className="text-2xl font-bold tracking-tight">Review Outline</h2>
        </div>
        <OutlineEditor initialOutline={generatedOutline} onApprove={handleApproveOutline} />
      </div>
    );
  }

  if (step === 'generating') {
    return (
      <div className="max-w-4xl mx-auto py-20 text-center space-y-6">
        <Loader2 className="h-16 w-16 animate-spin mx-auto text-primary" />
        <h2 className="text-2xl font-bold">Writing your article...</h2>
        <p className="text-muted-foreground">This may take a few minutes. The agent is researching, drafting, and refining.</p>
      </div>
    );
  }

  if (step === 'complete') {
    return (
      <div className="max-w-4xl mx-auto space-y-8">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-4">
            <Button variant="ghost" onClick={() => setStep('config')}>
              <ArrowLeft className="mr-2 h-4 w-4" /> Start Over
            </Button>
            <h2 className="text-2xl font-bold tracking-tight text-green-600 flex items-center">
              <CheckCircle className="mr-2 h-6 w-6" /> Generation Complete
            </h2>
          </div>
          <Button onClick={() => navigator.clipboard.writeText(finalArticle)}>
            Copy to Clipboard
          </Button>
        </div>
        <Card className="overflow-hidden">
          <CardContent className="p-8 md:p-12 bg-white dark:bg-zinc-950">
            <article className="prose prose-slate dark:prose-invert max-w-none lg:prose-lg">
              <ReactMarkdown>{finalArticle}</ReactMarkdown>
            </article>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto space-y-8">
      <div className="space-y-2">
        <h2 className="text-2xl font-bold tracking-tight">New Content Generation</h2>
        <p className="text-muted-foreground">
          Configure the agent to research and write your blog post.
        </p>
      </div>

      <div className="grid gap-6 md:grid-cols-2">
        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>1. Topic & Style</CardTitle>
              <CardDescription>What should the agent write about?</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="topic">Topic / Title</Label>
                <Input 
                  id="topic" 
                  placeholder="e.g., The Future of AI in Healthcare" 
                  value={topic}
                  onChange={(e) => setTopic(e.target.value)}
                />
              </div>
              
              <div className="space-y-2">
                <Label htmlFor="toneUrls">Reference URLs (for Tone/Style)</Label>
                <Textarea 
                  id="toneUrls" 
                  placeholder="https://example.com/our-best-post&#10;https://competitor.com/great-article" 
                  className="min-h-[100px]"
                  value={toneUrls}
                  onChange={(e) => setToneUrls(e.target.value)}
                />
                <p className="text-xs text-muted-foreground">
                  Enter one URL per line. The agent will analyze these to match your brand voice.
                </p>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>3. Launch</CardTitle>
            </CardHeader>
            <CardContent>
              <Button 
                className="w-full" 
                size="lg" 
                onClick={handleRun} 
                disabled={isRunning || !topic}
              >
                {isRunning ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" /> Starting Agent...
                  </>
                ) : (
                  <>
                    <Play className="mr-2 h-4 w-4" /> Generate Content
                  </>
                )}
              </Button>
            </CardContent>
          </Card>
        </div>

        <div className="space-y-6">
          <Card className="h-full flex flex-col">
            <CardHeader>
              <CardTitle>2. Knowledge Base</CardTitle>
              <CardDescription>Select context for the agent to use.</CardDescription>
            </CardHeader>
            <CardContent className="flex-1 space-y-4">
              <div className="flex justify-between items-center">
                <Label>Available Bins</Label>
                <Button variant="outline" size="sm" onClick={() => setShowUploader(!showUploader)}>
                  {showUploader ? 'Cancel' : <><Plus className="mr-2 h-4 w-4" /> New Bin</>}
                </Button>
              </div>

              {showUploader && (
                <div className="p-4 border rounded-md bg-muted/20">
                  <FileUploader onUploadComplete={handleBinAdded} />
                </div>
              )}

              <div className="space-y-2">
                {availableBins.length === 0 ? (
                  <div className="text-sm text-muted-foreground text-center py-8 border-2 border-dashed rounded-md">
                    No knowledge bins found.<br/>Create one to give the agent context.
                  </div>
                ) : (
                  availableBins.map(bin => (
                    <div key={bin} className="flex items-center space-x-2 p-2 border rounded-md hover:bg-accent">
                      <input 
                        type="checkbox" 
                        id={`bin-${bin}`}
                        checked={selectedBins.includes(bin)}
                        onChange={() => toggleBinSelection(bin)}
                        className="h-4 w-4 rounded border-gray-300 text-primary focus:ring-primary"
                      />
                      <Label htmlFor={`bin-${bin}`} className="flex-1 cursor-pointer font-normal">
                        {bin}
                      </Label>
                      <Button variant="ghost" size="icon" className="h-8 w-8 text-destructive" onClick={() => removeBin(bin)}>
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>
                  ))
                )}
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
};

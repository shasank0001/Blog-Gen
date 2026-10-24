import { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { getBins, analyzeStyle, getProfiles } from '@/lib/api';
import { Loader2, Play, ExternalLink, Wand2, ChevronRight, ChevronLeft } from 'lucide-react';
import { Link, useNavigate } from 'react-router-dom';
import { createJobOnce } from '@/lib/workspaceApi';
import { apiErrorMessage } from '@/lib/apiError';

interface Bin {
  id: string;
  name: string;
}

interface Profile {
  id: string;
  name: string;
}

const MODEL_OPTIONS: Record<string, { id: string; name: string }[]> = {
  openai: [
    { id: 'gpt-5.1', name: 'GPT-5.1 (Best Overall)' },
    { id: 'gpt-5-mini', name: 'GPT-5 Mini (Fast & Efficient)' },
    { id: 'gpt-5-pro', name: 'GPT-5 Pro (Deep Reasoning)' },
  ],
  anthropic: [
    { id: 'claude-sonnet-4-5-20250929', name: 'Claude Sonnet 4.5 (Best Overall)' },
    { id: 'claude-haiku-4-5', name: 'Haiku 4.5 (Fastest)' },
    { id: 'claude-opus-4-1', name: 'Opus 4.1 (Deep Reasoning)' },
  ],
  google: [
    { id: 'gemini-3-pro-preview', name: 'Gemini 3.0 Pro (Next Gen Preview)' },
    { id: 'gemini-flash-latest', name: 'Gemini Flash (Fastest)' },
  ]
};

export const GenerationWizard = () => {
  const [topic, setTopic] = useState('');
  const [toneUrls, setToneUrls] = useState('');
  const [targetDomain, setTargetDomain] = useState('');
  const [availableBins, setAvailableBins] = useState<Bin[]>([]);
  const [availableProfiles, setAvailableProfiles] = useState<Profile[]>([]);
  const [selectedBins, setSelectedBins] = useState<string[]>([]);
  const [useLocal, setUseLocal] = useState(false);
  const [modelProvider, setModelProvider] = useState<string>('openai');
  const [modelName, setModelName] = useState<string>('gpt-5.1');
  const [styleProfile, setStyleProfile] = useState<string>('');
  const [selectedProfileId, setSelectedProfileId] = useState<string>('');
  const [isAnalyzingStyle, setIsAnalyzingStyle] = useState(false);
  const [researchSources, setResearchSources] = useState<string[]>(['web', 'internal']);
  const [deepResearchMode, setDeepResearchMode] = useState(false);
  const [blogSize, setBlogSize] = useState<'small' | 'medium' | 'large'>('medium');
  
  // New Research Brief State
  const [targetAudience, setTargetAudience] = useState('');
  const [researchGuidelines, setResearchGuidelines] = useState('');
  const [extraContext, setExtraContext] = useState('');
  
  const navigate = useNavigate();
  const [configStep, setConfigStep] = useState(1);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [runError, setRunError] = useState('');
  const [costLimit, setCostLimit] = useState('2.00');

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [bins, profiles] = await Promise.all([getBins(), getProfiles()]);
        setAvailableBins(bins);
        setAvailableProfiles(profiles);
      } catch (error) {
        console.error('Failed to fetch data:', error);
      }
    };
    fetchData();
  }, []);

  const handleAnalyzeStyle = async () => {
    const urls = toneUrls.split('\n').filter(url => url.trim() !== '');
    if (urls.length === 0) {
      alert('Please enter at least one URL to analyze.');
      return;
    }
    
    setIsAnalyzingStyle(true);
    try {
      const profile = await analyzeStyle(urls, useLocal);
      setStyleProfile(JSON.stringify(profile, null, 2));
    } catch (error) {
      console.error('Failed to analyze style:', error);
      alert('Failed to analyze style.');
    } finally {
      setIsAnalyzingStyle(false);
    }
  };

  const toggleBinSelection = (binId: string) => {
    setSelectedBins(prev => 
      prev.includes(binId) 
        ? prev.filter(id => id !== binId)
        : [...prev, binId]
    );
  };

  const handleRun = async () => {
    if (!topic) return;
    setIsSubmitting(true);
    setRunError('');
    try {
      const urls = toneUrls.split('\n').filter(url => url.trim() !== '');
      
      let parsedStyle = null;
      if (styleProfile) {
        try {
          parsedStyle = JSON.parse(styleProfile);
        } catch (e) {
          console.error("Invalid JSON in style profile", e);
          alert("Invalid JSON in Style Profile. Using default.");
        }
      }

      const job = await createJobOnce({
        topic,
        cost_limit_usd: costLimit,
        tone_urls: urls,
        selected_bins: selectedBins,
        target_domain: targetDomain,
        use_local: useLocal,
        model_provider: modelProvider,
        model_name: modelName,
        style_profile: parsedStyle,
        profile_id: (selectedProfileId && selectedProfileId !== '_none') ? selectedProfileId : undefined,
        research_sources: researchSources,
        deep_research_mode: deepResearchMode,
        blog_size: blogSize,
        target_audience: targetAudience,
        research_guidelines: researchGuidelines.split('\n').filter(l => l.trim() !== ''),
        extra_context: extraContext
      });
      navigate(`/runs/${job.id}`);
    } catch (error) {
      console.error('Failed to start agent:', error);
      setRunError(apiErrorMessage(error, 'Could not create generation run. Check your settings and try again.'));
    } finally { setIsSubmitting(false); }
  };

  const totalConfigSteps = 4;
  const nextConfigStep = () => setConfigStep(p => Math.min(totalConfigSteps, p + 1));
  const prevConfigStep = () => setConfigStep(p => Math.max(1, p - 1));

  return (
    <div className="max-w-4xl mx-auto space-y-8">
      <div className="space-y-2">
        <h2 className="text-2xl font-bold tracking-tight">New Content Generation</h2>
        <p className="text-muted-foreground">
          Configure the agent to research and write your blog post.
        </p>
      </div>

      {runError && <p role="alert" className="rounded border border-red-300 bg-red-50 p-4 text-red-900">{runError}</p>}

      {/* Progress Bar */}
      <div className="w-full bg-secondary h-2 rounded-full overflow-hidden">
        <div 
          className="bg-primary h-full transition-all duration-300 ease-in-out" 
          style={{ width: `${(configStep / totalConfigSteps) * 100}%` }}
        />
      </div>

      <div className="grid gap-6">
        {configStep === 1 && (
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
                <Label htmlFor="profile">Style Profile (Optional)</Label>
                <Select
                  value={selectedProfileId}
                  onValueChange={setSelectedProfileId}
                >
                  <SelectTrigger id="profile">
                    <SelectValue placeholder="Select a Style Profile..." />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="_none">None</SelectItem>
                    {availableProfiles.map(p => (
                      <SelectItem key={p.id} value={p.id}>{p.name}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <p className="text-xs text-muted-foreground">
                  Select a saved profile to automatically apply its tone and style.
                </p>
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
                <div className="flex justify-between items-center">
                  <p className="text-xs text-muted-foreground">
                    Enter one URL per line.
                  </p>
                  <Button 
                    variant="outline" 
                    size="sm" 
                    onClick={handleAnalyzeStyle}
                    disabled={isAnalyzingStyle || !toneUrls}
                  >
                    {isAnalyzingStyle ? <Loader2 className="h-3 w-3 animate-spin mr-1" /> : <Wand2 className="h-3 w-3 mr-1" />}
                    Analyze Style
                  </Button>
                </div>
              </div>

              {styleProfile && (
                <div className="space-y-2">
                  <Label htmlFor="styleProfile">Style DNA (JSON)</Label>
                  <Textarea 
                    id="styleProfile" 
                    value={styleProfile}
                    onChange={(e) => setStyleProfile(e.target.value)}
                    className="font-mono text-xs min-h-[150px]"
                  />
                </div>
              )}
            </CardContent>
          </Card>
        )}

        {configStep === 2 && (
          <Card>
            <CardHeader>
              <CardTitle>2. Research Brief</CardTitle>
              <CardDescription>Guide the agent's research strategy.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="audience">Target Audience</Label>
                <Input 
                  id="audience" 
                  placeholder="e.g., CTOs, Medical Professionals, Beginners" 
                  value={targetAudience}
                  onChange={(e) => setTargetAudience(e.target.value)}
                />
              </div>
              
              <div className="space-y-2">
                <Label htmlFor="guidelines">Research Guidelines / Questions</Label>
                <Textarea 
                  id="guidelines" 
                  placeholder="e.g., Find statistics on AI adoption in 2024&#10;Look for competitors to product X" 
                  className="min-h-[80px]"
                  value={researchGuidelines}
                  onChange={(e) => setResearchGuidelines(e.target.value)}
                />
                <p className="text-xs text-muted-foreground">
                  Specific questions or data points you want the agent to find. One per line.
                </p>
              </div>

              <div className="space-y-2">
                <Label htmlFor="context">Additional Context / Notes</Label>
                <Textarea 
                  id="context" 
                  placeholder="Paste any raw notes, key facts, or constraints here..." 
                  className="min-h-[100px]"
                  value={extraContext}
                  onChange={(e) => setExtraContext(e.target.value)}
                />
                <p className="text-xs text-muted-foreground">
                  This information will be treated as a primary source.
                </p>
              </div>
            </CardContent>
          </Card>
        )}

        {configStep === 3 && (
          <div className="grid gap-6 md:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle>3. Research Sources</CardTitle>
                <CardDescription>Select where the agent should research.</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid grid-cols-1 gap-3">
                  {[
                    { id: 'web', label: 'Web Search', desc: 'General internet search via Firecrawl' },
                    { id: 'social', label: 'Social Media', desc: 'Reddit & Twitter discussions' },
                    { id: 'academic', label: 'Academic Papers', desc: 'Arxiv research papers' },
                    { id: 'internal', label: 'Internal Knowledge', desc: 'Knowledge Base bins & Target domain' }
                  ].map(source => (
                    <div key={source.id} className="flex items-start space-x-3 p-2 border rounded-md hover:bg-accent/50">
                      <input
                        type="checkbox"
                        id={`source-${source.id}`}
                        className="mt-1 h-4 w-4 rounded border-gray-300 text-primary focus:ring-primary"
                        checked={researchSources.includes(source.id)}
                        onChange={(e) => {
                          if (e.target.checked) {
                            setResearchSources([...researchSources, source.id]);
                          } else {
                            setResearchSources(researchSources.filter(s => s !== source.id));
                          }
                        }}
                      />
                      <div className="space-y-1">
                        <Label htmlFor={`source-${source.id}`} className="cursor-pointer font-medium">
                          {source.label}
                        </Label>
                        <p className="text-xs text-muted-foreground">
                          {source.desc}
                        </p>
                      </div>
                    </div>
                  ))}
                </div>

                <div className="space-y-2 pt-4 border-t">
                  <Label htmlFor="targetDomain">Target Domain (for Internal Linking)</Label>
                  <Input 
                    id="targetDomain" 
                    placeholder="https://yourwebsite.com" 
                    value={targetDomain}
                    onChange={(e) => setTargetDomain(e.target.value)}
                  />
                  <p className="text-xs text-muted-foreground">
                    The agent will scan this site's sitemap to find relevant internal links.
                  </p>
                </div>
              </CardContent>
            </Card>

            <Card className="h-full flex flex-col">
              <CardHeader>
                <CardTitle>4. Knowledge Base</CardTitle>
                <CardDescription>Select context for the agent to use.</CardDescription>
              </CardHeader>
              <CardContent className="flex-1 space-y-4">
                <div className="flex justify-between items-center">
                  <Label>Available Bins</Label>
                  <Link to="/knowledge">
                    <Button variant="outline" size="sm">
                      <ExternalLink className="mr-2 h-4 w-4" /> Manage Bins
                    </Button>
                  </Link>
                </div>

                <div className="space-y-2">
                  {availableBins.length === 0 ? (
                    <div className="text-sm text-muted-foreground text-center py-8 border-2 border-dashed rounded-md">
                      No knowledge bins found.<br/>Create one in the Knowledge Base.
                    </div>
                  ) : (
                    availableBins.map(bin => (
                      <div key={bin.id} className="flex items-center space-x-2 p-2 border rounded-md hover:bg-accent">
                        <input 
                          type="checkbox" 
                          id={`bin-${bin.id}`}
                          checked={selectedBins.includes(bin.id)}
                          onChange={() => toggleBinSelection(bin.id)}
                          className="h-4 w-4 rounded border-gray-300 text-primary focus:ring-primary"
                        />
                        <Label htmlFor={`bin-${bin.id}`} className="flex-1 cursor-pointer font-normal">
                          {bin.name}
                        </Label>
                      </div>
                    ))
                  )}
                </div>
              </CardContent>
            </Card>
          </div>
        )}

        {configStep === 4 && (
          <Card>
            <CardHeader>
              <CardTitle>5. Launch & Privacy</CardTitle>
              <CardDescription>Select your AI model and privacy settings.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="space-y-4">
                <Label>Blog Length Target</Label>
                <Select
                  value={blogSize}
                  onValueChange={(value: 'small' | 'medium' | 'large') => setBlogSize(value)}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Select blog size" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="small">Small (2,000-3,000 words)</SelectItem>
                    <SelectItem value="medium">Medium (5,000-6,000 words)</SelectItem>
                    <SelectItem value="large">Large (10,000+ words)</SelectItem>
                  </SelectContent>
                </Select>
                <p className="text-xs text-muted-foreground">
                  The planner will allocate word budgets across sections to meet this target.
                </p>
              </div>

              <div className="space-y-2">
                <Label htmlFor="generation-limit">Run spending limit (USD)</Label>
                <Input id="generation-limit" type="number" min="0.0001" max="10000" step="0.01" value={costLimit} onChange={event => setCostLimit(event.target.value)} />
                <p className="text-xs text-muted-foreground">Estimated LLM charges only. Each call reserves budget before starting. Unpriced cloud models require administrator configuration. <Link className="underline" to="/costs">View prices and monthly limit</Link></p>
              </div>

              <div className="space-y-4">
                <Label>AI Model Selection</Label>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label htmlFor="modelProvider" className="text-xs text-muted-foreground">Provider</Label>
                    <Select
                      value={modelProvider}
                      onValueChange={(value) => {
                        setModelProvider(value);
                        // Reset model name to first option of new provider
                        if (MODEL_OPTIONS[value]?.length > 0) {
                          setModelName(MODEL_OPTIONS[value][0].id);
                        }
                      }}
                      disabled={useLocal}
                    >
                      <SelectTrigger id="modelProvider">
                        <SelectValue placeholder="Select provider" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="openai">OpenAI</SelectItem>
                        <SelectItem value="anthropic">Anthropic</SelectItem>
                        <SelectItem value="google">Google</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  
                  <div className="space-y-2">
                    <Label htmlFor="modelName" className="text-xs text-muted-foreground">Model</Label>
                    <Select
                      value={modelName}
                      onValueChange={setModelName}
                      disabled={useLocal}
                    >
                      <SelectTrigger id="modelName">
                        <SelectValue placeholder="Select model" />
                      </SelectTrigger>
                      <SelectContent>
                        {MODEL_OPTIONS[modelProvider]?.map(model => (
                          <SelectItem key={model.id} value={model.id}>{model.name}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                </div>
              </div>

              <div className="flex items-center space-x-2 border p-3 rounded-md bg-muted/20">
                <input
                  type="checkbox"
                  id="deepResearchMode"
                  className="h-4 w-4 rounded border-gray-300 text-primary focus:ring-primary"
                  checked={deepResearchMode}
                  onChange={(e) => setDeepResearchMode(e.target.checked)}
                />
                <div className="space-y-1 leading-none">
                  <Label htmlFor="deepResearchMode" className="cursor-pointer font-medium">
                    Enable Deep Research Agent
                  </Label>
                  <p className="text-xs text-muted-foreground">
                    Runs multiple research passes to fill gaps before planning. Slower but more thorough.
                  </p>
                </div>
              </div>

              <div className="flex items-center space-x-2 border p-3 rounded-md bg-muted/20">
                <input
                  type="checkbox"
                  id="useLocal"
                  className="h-4 w-4 rounded border-gray-300 text-primary focus:ring-primary"
                  checked={useLocal}
                  onChange={(e) => setUseLocal(e.target.checked)}
                />
                <div className="space-y-1 leading-none">
                  <Label htmlFor="useLocal" className="cursor-pointer font-medium">
                    Use Local Processing (Ollama)
                  </Label>
                  <p className="text-xs text-muted-foreground">
                    Process data locally for enhanced privacy. Overrides cloud model selection.
                  </p>
                </div>
              </div>
            </CardContent>
          </Card>
        )}
      </div>

      <div className="flex justify-between pt-4">
        <Button 
          variant="outline" 
          onClick={prevConfigStep} 
          disabled={configStep === 1}
        >
          <ChevronLeft className="mr-2 h-4 w-4" /> Back
        </Button>

        {configStep < totalConfigSteps ? (
          <Button onClick={nextConfigStep}>
            Next <ChevronRight className="ml-2 h-4 w-4" />
          </Button>
        ) : (
          <Button 
            size="lg" 
            onClick={handleRun} 
            disabled={isSubmitting || !topic}
          >
            {isSubmitting ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" /> Starting Agent...
              </>
            ) : (
              <>
                <Play className="mr-2 h-4 w-4" /> Generate Content
              </>
            )}
          </Button>
        )}
      </div>
    </div>
  );
};

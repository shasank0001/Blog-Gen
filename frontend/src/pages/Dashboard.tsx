import { GenerationWizard } from '@/pages/GenerationWizard';

export const Dashboard = () => {
  return (
    <div className="container mx-auto py-10 space-y-8">
      <div className="flex flex-col space-y-2">
        <h1 className="text-3xl font-bold tracking-tight">Content Strategist Agent</h1>
        <p className="text-muted-foreground">
          Turn your internal documents into authoritative, SEO-optimized articles.
        </p>
      </div>
      
      <GenerationWizard />
    </div>
  );
};

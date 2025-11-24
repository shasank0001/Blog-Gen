import { useEffect, useRef, useState } from 'react';
import mermaid from 'mermaid';
import { Maximize2, X } from 'lucide-react';
import { Button } from '@/components/ui/button';

mermaid.initialize({
  startOnLoad: false,
  theme: 'default',
  securityLevel: 'loose',
});

interface MermaidProps {
  chart: string;
}

export const Mermaid = ({ chart }: MermaidProps) => {
  const ref = useRef<HTMLDivElement>(null);
  const [svg, setSvg] = useState<string>('');
  const [isExpanded, setIsExpanded] = useState(false);

  useEffect(() => {
    if (chart) {
      const id = `mermaid-${Math.random().toString(36).substr(2, 9)}`;
      mermaid.render(id, chart).then(({ svg }) => {
        setSvg(svg);
      }).catch((error) => {
        console.error('Mermaid render error:', error);
        // Gracefully hide the diagram if there's a parse error
        // The backend validation should prevent most errors, but this is a safety net
        setSvg(`<div class="text-sm text-muted-foreground italic p-2">Diagram could not be rendered</div>`);
      });
    }
  }, [chart]);

  // Only show expand button if there's actual SVG content (not an error message)
  const hasValidDiagram = svg && svg.includes('<svg');

  return (
    <>
      <div className="relative group my-4 border rounded-lg p-4 bg-white dark:bg-zinc-900">
        {hasValidDiagram && (
          <div className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity z-10">
            <Button variant="outline" size="icon" onClick={() => setIsExpanded(true)} title="Expand Diagram">
              <Maximize2 className="h-4 w-4" />
            </Button>
          </div>
        )}
        <div 
          ref={ref} 
          dangerouslySetInnerHTML={{ __html: svg }} 
          className="flex justify-center overflow-auto max-h-[500px]" 
        />
      </div>

      {isExpanded && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 p-4" onClick={() => setIsExpanded(false)}>
          <div className="relative bg-white dark:bg-zinc-900 rounded-lg p-8 w-full h-full max-w-7xl max-h-[90vh] overflow-auto flex items-center justify-center" onClick={e => e.stopPropagation()}>
            <Button 
              variant="ghost" 
              size="icon" 
              className="absolute top-4 right-4 z-50" 
              onClick={() => setIsExpanded(false)}
            >
              <X className="h-6 w-6" />
            </Button>
            <div dangerouslySetInnerHTML={{ __html: svg }} className="w-full h-full flex items-center justify-center [&>svg]:w-full [&>svg]:h-full" />
          </div>
        </div>
      )}
    </>
  );
};

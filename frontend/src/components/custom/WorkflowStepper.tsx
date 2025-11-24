import { Check, Circle, Loader2 } from 'lucide-react';
import { cn } from '@/lib/utils';

interface WorkflowStepperProps {
  activeNode: string;
}

const STEPS = [
  { id: 'researcher', label: 'Research' },
  { id: 'planner', label: 'Plan' },
  { id: 'human_approval', label: 'Review' },
  { id: 'writer', label: 'Write' },
  { id: 'critic', label: 'Critique' },
  { id: 'visuals', label: 'Visuals' },
  { id: 'publisher', label: 'Publish' },
];

export const WorkflowStepper = ({ activeNode }: WorkflowStepperProps) => {
  const activeIndex = STEPS.findIndex(s => s.id === activeNode);
  
  const getStepStatus = (index: number) => {
    // If activeIndex is -1 (not started or unknown step), treat all as pending unless we want to show something else
    if (activeIndex === -1 && activeNode) {
        // Maybe map internal_indexer to researcher?
        if (activeNode === 'internal_indexer' || activeNode === 'style_analyst') {
            if (index === 0) return 'active';
        }
        return 'pending';
    }
    if (activeIndex === -1) return 'pending';
    
    if (index < activeIndex) return 'completed';
    if (index === activeIndex) return 'active';
    return 'pending';
  };

  return (
    <div className="w-full py-4">
      <div className="flex items-center justify-between relative">
        {/* Connecting Line */}
        <div className="absolute left-0 top-1/2 transform -translate-y-1/2 w-full h-0.5 bg-zinc-200 dark:bg-zinc-800 -z-10" />
        
        {STEPS.map((step, index) => {
          const status = getStepStatus(index);
          return (
            <div key={step.id} className="flex flex-col items-center gap-2 bg-background px-2">
              <div className={cn(
                "w-8 h-8 rounded-full flex items-center justify-center border-2 transition-all duration-300",
                status === 'completed' && "bg-green-500 border-green-500 text-white",
                status === 'active' && "bg-blue-500 border-blue-500 text-white animate-pulse",
                status === 'pending' && "bg-background border-zinc-300 dark:border-zinc-700 text-zinc-400"
              )}>
                {status === 'completed' ? (
                  <Check className="w-4 h-4" />
                ) : status === 'active' ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <Circle className="w-4 h-4" />
                )}
              </div>
              <span className={cn(
                "text-xs font-medium transition-colors duration-300",
                status === 'active' ? "text-blue-500" : "text-muted-foreground"
              )}>
                {step.label}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
};

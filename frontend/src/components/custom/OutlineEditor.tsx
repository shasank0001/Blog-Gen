import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Card, CardContent } from '@/components/ui/card';
import { ArrowUp, ArrowDown, Trash2, Plus } from 'lucide-react';

interface Section {
  id: string;
  title: string;
  intent: string;
  source_ids: string[];
  content?: string;
}

interface OutlineEditorProps {
  initialOutline: Section[];
  onApprove: (outline: Section[]) => void;
}

export const OutlineEditor = ({ initialOutline, onApprove }: OutlineEditorProps) => {
  const [outline, setOutline] = useState<Section[]>(initialOutline);

  const updateSection = (index: number, field: keyof Section, value: any) => {
    const newOutline = [...outline];
    newOutline[index] = { ...newOutline[index], [field]: value };
    setOutline(newOutline);
  };

  const moveSection = (index: number, direction: 'up' | 'down') => {
    if (direction === 'up' && index > 0) {
      const newOutline = [...outline];
      [newOutline[index - 1], newOutline[index]] = [newOutline[index], newOutline[index - 1]];
      setOutline(newOutline);
    } else if (direction === 'down' && index < outline.length - 1) {
      const newOutline = [...outline];
      [newOutline[index + 1], newOutline[index]] = [newOutline[index], newOutline[index + 1]];
      setOutline(newOutline);
    }
  };

  const removeSection = (index: number) => {
    const newOutline = outline.filter((_, i) => i !== index);
    setOutline(newOutline);
  };

  const addSection = () => {
    const newSection: Section = {
      id: `section-${Date.now()}`,
      title: 'New Section',
      intent: 'Describe the purpose of this section',
      source_ids: [],
    };
    setOutline([...outline, newSection]);
  };

  return (
    <div className="space-y-4">
      <h3 className="text-lg font-semibold">Review & Edit Outline</h3>
      <div className="space-y-2">
        {outline.map((section, index) => (
          <Card key={section.id}>
            <CardContent className="p-4 flex gap-4 items-start">
              <div className="flex flex-col gap-1 mt-1">
                <Button variant="ghost" size="icon" className="h-6 w-6" onClick={() => moveSection(index, 'up')} disabled={index === 0}>
                  <ArrowUp className="h-4 w-4" />
                </Button>
                <Button variant="ghost" size="icon" className="h-6 w-6" onClick={() => moveSection(index, 'down')} disabled={index === outline.length - 1}>
                  <ArrowDown className="h-4 w-4" />
                </Button>
              </div>
              <div className="flex-1 space-y-2">
                <Input 
                  value={section.title} 
                  onChange={(e) => updateSection(index, 'title', e.target.value)}
                  className="font-semibold"
                  placeholder="Section Title"
                />
                <Textarea 
                  value={section.intent} 
                  onChange={(e) => updateSection(index, 'intent', e.target.value)}
                  className="text-sm text-muted-foreground min-h-[60px]"
                  placeholder="Section Intent/Description"
                />
              </div>
              <Button variant="ghost" size="icon" className="text-destructive" onClick={() => removeSection(index)}>
                <Trash2 className="h-4 w-4" />
              </Button>
            </CardContent>
          </Card>
        ))}
      </div>
      <Button variant="outline" className="w-full" onClick={addSection}>
        <Plus className="mr-2 h-4 w-4" /> Add Section
      </Button>
      <div className="flex justify-end pt-4">
        <Button size="lg" onClick={() => onApprove(outline)}>
          Approve & Generate Article
        </Button>
      </div>
    </div>
  );
};

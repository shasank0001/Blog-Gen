import { useState, useEffect } from 'react';
import { getProfiles, createProfile, deleteProfile, updateProfile } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Plus, Trash2, User, Loader2, Edit2, Check, X } from 'lucide-react';
import { Textarea } from '@/components/ui/textarea';

interface Profile {
  id: string;
  name: string;
  description: string;
  tone_urls: string[];
  created_at: string;
}

export const Profiles = () => {
  const [profiles, setProfiles] = useState<Profile[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isCreating, setIsCreating] = useState(false);
  
  // Form State
  const [newName, setNewName] = useState('');
  const [newDescription, setNewDescription] = useState('');
  const [newToneUrls, setNewToneUrls] = useState('');

  // Edit State
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editName, setEditName] = useState('');
  const [editDescription, setEditDescription] = useState('');

  useEffect(() => {
    fetchProfiles();
  }, []);

  const fetchProfiles = async () => {
    setIsLoading(true);
    try {
      const data = await getProfiles();
      setProfiles(data);
    } catch (error) {
      console.error('Failed to fetch profiles', error);
    } finally {
      setIsLoading(false);
    }
  };

  const handleCreate = async () => {
    if (!newName.trim()) return;
    try {
      const urls = newToneUrls.split('\n').filter(u => u.trim());
      await createProfile(newName, newDescription, urls);
      setNewName('');
      setNewDescription('');
      setNewToneUrls('');
      setIsCreating(false);
      fetchProfiles();
    } catch (error) {
      console.error('Failed to create profile', error);
      alert('Failed to create profile. Please try again.');
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm('Are you sure?')) return;
    try {
      await deleteProfile(id);
      fetchProfiles();
    } catch (error) {
      console.error('Failed to delete profile', error);
    }
  };

  const startEdit = (profile: Profile) => {
    setEditingId(profile.id);
    setEditName(profile.name);
    setEditDescription(profile.description);
  };

  const cancelEdit = () => {
    setEditingId(null);
    setEditName('');
    setEditDescription('');
  };

  const saveEdit = async (id: string) => {
    try {
      await updateProfile(id, { name: editName, description: editDescription });
      setEditingId(null);
      fetchProfiles();
    } catch (error) {
      console.error('Failed to update profile', error);
    }
  };

  return (
    <div className="container mx-auto p-6 max-w-5xl">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Style Profiles</h1>
          <p className="text-muted-foreground mt-1">
            Manage writing styles and personas for your content.
          </p>
        </div>
        <Button onClick={() => setIsCreating(!isCreating)}>
          <Plus className="mr-2 h-4 w-4" /> New Profile
        </Button>
      </div>

      {isCreating && (
        <Card className="mb-8 border-primary/20 bg-primary/5 animate-in slide-in-from-top-2">
          <CardHeader>
            <CardTitle className="text-lg">Create New Profile</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-4 md:grid-cols-2">
              <div className="space-y-2">
                <label className="text-sm font-medium">Name</label>
                <Input 
                  placeholder="e.g., Tech Blog, LinkedIn Personal" 
                  value={newName}
                  onChange={(e) => setNewName(e.target.value)}
                />
              </div>
              <div className="space-y-2">
                <label className="text-sm font-medium">Description</label>
                <Input 
                  placeholder="Brief description of this style" 
                  value={newDescription}
                  onChange={(e) => setNewDescription(e.target.value)}
                />
              </div>
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">Reference URLs (One per line)</label>
              <Textarea 
                placeholder="https://example.com/blog-post-1&#10;https://example.com/blog-post-2"
                value={newToneUrls}
                onChange={(e) => setNewToneUrls(e.target.value)}
                className="h-24 font-mono text-xs"
              />
            </div>
            <div className="flex justify-end gap-2">
              <Button variant="ghost" onClick={() => setIsCreating(false)}>Cancel</Button>
              <Button onClick={handleCreate}>Create Profile</Button>
            </div>
          </CardContent>
        </Card>
      )}

      {isLoading ? (
        <div className="flex justify-center p-12"><Loader2 className="animate-spin h-8 w-8 text-muted-foreground" /></div>
      ) : profiles.length === 0 ? (
        <div className="text-center p-12 border-2 border-dashed rounded-lg">
          <User className="mx-auto h-12 w-12 text-muted-foreground/50" />
          <h3 className="mt-4 text-lg font-medium">No profiles yet</h3>
          <p className="text-muted-foreground">Create a style profile to customize your content generation.</p>
        </div>
      ) : (
        <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
          {profiles.map(profile => (
            <Card key={profile.id} className="flex flex-col">
              <CardHeader className="pb-3">
                <div className="flex items-start justify-between">
                  {editingId === profile.id ? (
                    <div className="flex-1 space-y-2 mr-2">
                      <Input 
                        value={editName} 
                        onChange={(e) => setEditName(e.target.value)}
                        className="h-8 font-bold"
                      />
                      <Input 
                        value={editDescription} 
                        onChange={(e) => setEditDescription(e.target.value)}
                        className="h-8 text-xs"
                      />
                    </div>
                  ) : (
                    <div className="space-y-1">
                      <CardTitle className="text-xl">{profile.name}</CardTitle>
                      <CardDescription className="line-clamp-2">{profile.description}</CardDescription>
                    </div>
                  )}
                  
                  <div className="flex gap-1">
                    {editingId === profile.id ? (
                      <>
                        <Button size="icon" variant="ghost" className="h-8 w-8 text-green-600" onClick={() => saveEdit(profile.id)}>
                          <Check className="h-4 w-4" />
                        </Button>
                        <Button size="icon" variant="ghost" className="h-8 w-8 text-red-600" onClick={cancelEdit}>
                          <X className="h-4 w-4" />
                        </Button>
                      </>
                    ) : (
                      <>
                        <Button size="icon" variant="ghost" className="h-8 w-8" onClick={() => startEdit(profile)}>
                          <Edit2 className="h-4 w-4 text-muted-foreground" />
                        </Button>
                        <Button size="icon" variant="ghost" className="h-8 w-8 hover:text-red-600" onClick={() => handleDelete(profile.id)}>
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </>
                    )}
                  </div>
                </div>
              </CardHeader>
              <CardContent className="flex-1">
                <div className="space-y-4">
                  <div>
                    <div className="text-xs font-medium text-muted-foreground mb-2 uppercase tracking-wider">Reference URLs</div>
                    <div className="space-y-1">
                      {profile.tone_urls && profile.tone_urls.length > 0 ? (
                        profile.tone_urls.slice(0, 3).map((url, i) => (
                          <div key={i} className="text-xs truncate text-blue-500 bg-blue-50 dark:bg-blue-900/20 p-1 rounded px-2">
                            {url}
                          </div>
                        ))
                      ) : (
                        <div className="text-xs text-muted-foreground italic">No references</div>
                      )}
                      {profile.tone_urls && profile.tone_urls.length > 3 && (
                        <div className="text-xs text-muted-foreground pl-1">+{profile.tone_urls.length - 3} more</div>
                      )}
                    </div>
                  </div>
                  <div className="pt-4 border-t text-xs text-muted-foreground flex justify-between items-center">
                    <span>Created {new Date(profile.created_at).toLocaleDateString()}</span>
                    <Badge variant="outline" className="font-mono text-[10px]">ID: {profile.id.slice(0, 8)}</Badge>
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
};
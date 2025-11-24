import { useState, useEffect } from 'react';
import { getBins, createBin, deleteBin, getBinFiles, updateBin, deleteDocument, resyncBin } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { FileUploader } from '@/components/custom/FileUploader';
import { Badge } from '@/components/ui/badge';
import { Plus, Trash2, Folder, FileText, Loader2, RefreshCw, Edit2, Check, X } from 'lucide-react';
import { cn } from '@/lib/utils';

interface Bin {
  id: string;
  name: string;
  created_at: string;
}

interface DocFile {
  id: string;
  filename: string;
  status: 'uploaded' | 'processing' | 'ready' | 'failed';
  created_at: string;
}

export const KnowledgeBase = () => {
  const [bins, setBins] = useState<Bin[]>([]);
  const [selectedBin, setSelectedBin] = useState<Bin | null>(null);
  const [files, setFiles] = useState<DocFile[]>([]);
  const [isLoadingBins, setIsLoadingBins] = useState(false);
  const [isLoadingFiles, setIsLoadingFiles] = useState(false);
  
  // Create Bin State
  const [isCreating, setIsCreating] = useState(false);
  const [newBinName, setNewBinName] = useState('');

  // Edit Bin State
  const [isEditingBin, setIsEditingBin] = useState(false);
  const [editBinName, setEditBinName] = useState('');
  const [isResyncing, setIsResyncing] = useState(false);

  useEffect(() => {
    fetchBins();
  }, []);

  useEffect(() => {
    if (selectedBin) {
      fetchFiles(selectedBin.id);
      setEditBinName(selectedBin.name);
      setIsEditingBin(false);
    } else {
      setFiles([]);
    }
  }, [selectedBin]);

  const fetchBins = async () => {
    setIsLoadingBins(true);
    try {
      const data = await getBins();
      setBins(data);
      if (!selectedBin && data.length > 0) {
          setSelectedBin(data[0]);
      }
    } catch (error) {
      console.error('Failed to fetch bins', error);
    } finally {
      setIsLoadingBins(false);
    }
  };

  const fetchFiles = async (binId: string) => {
    setIsLoadingFiles(true);
    try {
      const data = await getBinFiles(binId);
      setFiles(data);
    } catch (error) {
      console.error('Failed to fetch files', error);
    } finally {
      setIsLoadingFiles(false);
    }
  };

  const handleCreateBin = async () => {
    if (!newBinName.trim()) return;
    try {
      await createBin(newBinName);
      setNewBinName('');
      setIsCreating(false);
      fetchBins();
    } catch (error) {
      console.error('Failed to create bin', error);
      alert('Failed to create bin. Please try again.');
    }
  };

  const handleDeleteBin = async (binId: string, e?: React.MouseEvent) => {
    if (e) e.stopPropagation();
    if (!confirm('Are you sure? This will delete all files in this bin.')) return;
    try {
      await deleteBin(binId);
      if (selectedBin?.id === binId) {
        setSelectedBin(null);
      }
      fetchBins();
    } catch (error) {
      console.error('Failed to delete bin', error);
    }
  };

  const handleUpdateBin = async () => {
    if (!selectedBin || !editBinName.trim()) return;
    try {
      await updateBin(selectedBin.id, editBinName);
      setIsEditingBin(false);
      fetchBins();
      // Update selected bin name locally to avoid flicker
      setSelectedBin({ ...selectedBin, name: editBinName });
    } catch (error) {
      console.error('Failed to update bin', error);
    }
  };

  const handleResyncBin = async () => {
    if (!selectedBin) return;
    setIsResyncing(true);
    try {
      await resyncBin(selectedBin.id);
      fetchFiles(selectedBin.id);
    } catch (error) {
      console.error('Failed to resync bin', error);
    } finally {
      setIsResyncing(false);
    }
  };

  const handleDeleteDocument = async (docId: string) => {
    if (!selectedBin || !confirm('Are you sure you want to delete this document?')) return;
    try {
      await deleteDocument(docId);
      fetchFiles(selectedBin.id);
    } catch (error) {
      console.error('Failed to delete document', error);
    }
  };

  return (
    <div className="h-[calc(100vh-8rem)] flex flex-col md:flex-row gap-6">
      {/* Sidebar: Bins List */}
      <Card className="w-full md:w-80 flex flex-col h-full border-zinc-200 dark:border-zinc-800">
        <CardHeader className="pb-4 border-b border-zinc-100 dark:border-zinc-800">
          <div className="flex items-center justify-between">
            <CardTitle className="text-lg">Bins</CardTitle>
            <Button size="sm" variant="ghost" onClick={() => setIsCreating(!isCreating)}>
              <Plus className="h-4 w-4" />
            </Button>
          </div>
          {isCreating && (
            <div className="flex gap-2 mt-2 animate-in slide-in-from-top-2">
              <Input 
                placeholder="Bin Name" 
                value={newBinName} 
                onChange={(e) => setNewBinName(e.target.value)}
                className="h-8 text-sm"
              />
              <Button size="sm" onClick={handleCreateBin}>Add</Button>
            </div>
          )}
        </CardHeader>
        <CardContent className="flex-1 overflow-auto p-2 space-y-1">
          {isLoadingBins ? (
            <div className="flex justify-center p-4"><Loader2 className="animate-spin h-5 w-5 text-muted-foreground" /></div>
          ) : bins.length === 0 ? (
            <div className="text-center p-4 text-sm text-muted-foreground">No bins found. Create one to get started.</div>
          ) : (
            bins.map(bin => (
              <div
                key={bin.id}
                onClick={() => setSelectedBin(bin)}
                className={cn(
                  "flex items-center justify-between p-3 rounded-md cursor-pointer transition-colors text-sm group",
                  selectedBin?.id === bin.id 
                    ? "bg-primary/10 text-primary font-medium" 
                    : "hover:bg-zinc-100 dark:hover:bg-zinc-800 text-zinc-600 dark:text-zinc-400"
                )}
              >
                <div className="flex items-center gap-3 overflow-hidden">
                  <Folder className={cn("h-4 w-4 flex-shrink-0", selectedBin?.id === bin.id ? "fill-current" : "")} />
                  <span className="truncate">{bin.name}</span>
                </div>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-6 w-6 opacity-0 group-hover:opacity-100 transition-opacity"
                  onClick={(e) => handleDeleteBin(bin.id, e)}
                >
                  <Trash2 className="h-3 w-3 text-muted-foreground hover:text-red-500" />
                </Button>
              </div>
            ))
          )}
        </CardContent>
      </Card>

      {/* Main Content: Files */}
      <div className="flex-1 flex flex-col h-full min-w-0">
        {selectedBin ? (
          <div className="space-y-6 h-full flex flex-col">
            <div className="flex items-center justify-between">
              <div>
                <div className="flex items-center gap-2">
                  <Folder className="h-6 w-6 text-primary fill-primary/20" />
                  {isEditingBin ? (
                    <div className="flex items-center gap-2">
                      <Input 
                        value={editBinName} 
                        onChange={(e) => setEditBinName(e.target.value)}
                        className="h-8 w-64"
                      />
                      <Button size="icon" variant="ghost" className="h-8 w-8 text-green-600" onClick={handleUpdateBin}>
                        <Check className="h-4 w-4" />
                      </Button>
                      <Button size="icon" variant="ghost" className="h-8 w-8 text-red-600" onClick={() => setIsEditingBin(false)}>
                        <X className="h-4 w-4" />
                      </Button>
                    </div>
                  ) : (
                    <div className="flex items-center gap-2 group">
                      <h2 className="text-2xl font-bold">{selectedBin.name}</h2>
                      <Button 
                        size="icon" 
                        variant="ghost" 
                        className="h-6 w-6 opacity-0 group-hover:opacity-100 transition-opacity"
                        onClick={() => setIsEditingBin(true)}
                      >
                        <Edit2 className="h-3 w-3 text-muted-foreground" />
                      </Button>
                    </div>
                  )}
                </div>
                <p className="text-sm text-muted-foreground mt-1">
                  Manage documents and context for this knowledge bin.
                </p>
              </div>
              <Button 
                variant="outline" 
                size="sm" 
                onClick={handleResyncBin} 
                disabled={isResyncing}
                className="gap-2"
              >
                <RefreshCw className={cn("h-4 w-4", isResyncing && "animate-spin")} />
                {isResyncing ? 'Resyncing...' : 'Resync Bin'}
              </Button>
            </div>

            <div className="grid gap-6 md:grid-cols-3 flex-1 min-h-0">
               {/* File List */}
               <Card className="md:col-span-2 flex flex-col h-full border-zinc-200 dark:border-zinc-800">
                 <CardHeader className="pb-4 border-b border-zinc-100 dark:border-zinc-800">
                   <CardTitle className="text-base">Documents ({files.length})</CardTitle>
                 </CardHeader>
                 <div className="flex-1 overflow-auto">
                   <table className="w-full text-sm text-left">
                     <thead className="text-xs text-muted-foreground bg-zinc-50 dark:bg-zinc-900/50 uppercase sticky top-0">
                       <tr>
                         <th className="px-4 py-3 font-medium">Name</th>
                         <th className="px-4 py-3 font-medium">Status</th>
                         <th className="px-4 py-3 font-medium">Date</th>
                         <th className="px-4 py-3 font-medium text-right">Actions</th>
                       </tr>
                     </thead>
                     <tbody className="divide-y divide-zinc-100 dark:divide-zinc-800">
                       {isLoadingFiles ? (
                         <tr><td colSpan={4} className="p-8 text-center"><Loader2 className="mx-auto h-6 w-6 animate-spin text-muted-foreground" /></td></tr>
                       ) : files.length === 0 ? (
                         <tr><td colSpan={4} className="p-8 text-center text-muted-foreground">No files uploaded yet.</td></tr>
                       ) : (
                         files.map(file => (
                           <tr key={file.id} className="group hover:bg-zinc-50 dark:hover:bg-zinc-900/50 transition-colors">
                             <td className="px-4 py-3 font-medium flex items-center gap-2">
                               <FileText className="h-4 w-4 text-blue-500" />
                               <span className="truncate max-w-[200px]">{file.filename}</span>
                             </td>
                             <td className="px-4 py-3">
                               <Badge variant={
                                 file.status === 'ready' ? 'default' : 
                                 file.status === 'failed' ? 'destructive' : 'secondary'
                               } className="capitalize text-[10px] h-5 px-1.5">
                                 {file.status}
                               </Badge>
                             </td>
                             <td className="px-4 py-3 text-muted-foreground text-xs">
                               {new Date(file.created_at).toLocaleDateString()}
                             </td>
                             <td className="px-4 py-3 text-right">
                               <Button 
                                 variant="ghost" 
                                 size="icon" 
                                 className="h-6 w-6 opacity-0 group-hover:opacity-100 text-muted-foreground hover:text-red-500"
                                 onClick={() => handleDeleteDocument(file.id)}
                               >
                                 <Trash2 className="h-3 w-3" />
                               </Button>
                             </td>
                           </tr>
                         ))
                       )}
                     </tbody>
                   </table>
                 </div>
               </Card>

               {/* Upload Area */}
               <div className="md:col-span-1">
                 <Card className="h-full border-zinc-200 dark:border-zinc-800">
                   <CardHeader>
                     <CardTitle className="text-base">Upload</CardTitle>
                     <CardDescription>Add PDF documents to this bin.</CardDescription>
                   </CardHeader>
                   <CardContent>
                     <FileUploader 
                       selectedBinId={selectedBin.id} 
                       onUploadComplete={() => fetchFiles(selectedBin.id)} 
                     />
                   </CardContent>
                 </Card>
               </div>
            </div>
          </div>
        ) : (
          <div className="flex-1 flex flex-col items-center justify-center text-muted-foreground border-2 border-dashed border-zinc-200 dark:border-zinc-800 rounded-lg m-4">
            <Folder className="h-16 w-16 mb-4 text-zinc-300 dark:text-zinc-700" />
            <h3 className="text-lg font-medium text-zinc-900 dark:text-zinc-100">No Bin Selected</h3>
            <p>Select a knowledge bin from the sidebar to view files.</p>
          </div>
        )}
      </div>
    </div>
  );
};

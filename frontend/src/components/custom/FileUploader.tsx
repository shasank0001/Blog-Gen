import React, { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { uploadDocument } from '@/lib/api';
import { Upload, CheckCircle, AlertCircle } from 'lucide-react';

export const FileUploader = ({ onUploadComplete }: { onUploadComplete?: (binId: string) => void }) => {
  const [file, setFile] = useState<File | null>(null);
  const [binId, setBinId] = useState('default_bin');
  const [uploading, setUploading] = useState(false);
  const [status, setStatus] = useState<'idle' | 'success' | 'error'>('idle');

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setFile(e.target.files[0]);
      setStatus('idle');
    }
  };

  const handleUpload = async () => {
    if (!file) return;
    setUploading(true);
    try {
      await uploadDocument(file, 'user_123', binId);
      setStatus('success');
      if (onUploadComplete) {
        onUploadComplete(binId);
      }
    } catch (error) {
      console.error(error);
      setStatus('error');
    } finally {
      setUploading(false);
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Knowledge Bin Upload</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid w-full max-w-sm items-center gap-1.5">
          <Label htmlFor="binId">Bin Name</Label>
          <Input 
            id="binId" 
            value={binId} 
            onChange={(e: React.ChangeEvent<HTMLInputElement>) => setBinId(e.target.value)} 
            placeholder="e.g., Q4_Reports"
          />
        </div>
        
        <div className="grid w-full max-w-sm items-center gap-1.5">
          <Label htmlFor="file">PDF Document</Label>
          <Input id="file" type="file" accept=".pdf" onChange={handleFileChange} />
        </div>

        <Button onClick={handleUpload} disabled={!file || uploading}>
          {uploading ? 'Uploading...' : (
            <>
              <Upload className="mr-2 h-4 w-4" /> Upload to Bin
            </>
          )}
        </Button>

        {status === 'success' && (
          <div className="flex items-center text-green-600">
            <CheckCircle className="mr-2 h-4 w-4" /> Upload Complete
          </div>
        )}
        {status === 'error' && (
          <div className="flex items-center text-red-600">
            <AlertCircle className="mr-2 h-4 w-4" /> Upload Failed
          </div>
        )}
      </CardContent>
    </Card>
  );
};

import React, { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent } from '@/components/ui/card';
import { uploadDocument } from '@/lib/api';
import { Upload, CheckCircle, AlertCircle, Loader2 } from 'lucide-react';

interface FileUploaderProps {
  selectedBinId: string;
  onUploadComplete?: () => void;
}

export const FileUploader = ({ selectedBinId, onUploadComplete }: FileUploaderProps) => {
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [status, setStatus] = useState<'idle' | 'success' | 'error'>('idle');
  const [errorMessage, setErrorMessage] = useState('');

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setFile(e.target.files[0]);
      setStatus('idle');
      setErrorMessage('');
    }
  };

  const handleUpload = async () => {
    if (!file || !selectedBinId) return;
    setUploading(true);
    try {
      await uploadDocument(file, selectedBinId);
      setStatus('success');
      setFile(null);
      if (onUploadComplete) {
        onUploadComplete();
      }
    } catch (error: any) {
      console.error(error);
      setStatus('error');
      setErrorMessage(error.response?.data?.detail || 'Upload failed');
    } finally {
      setUploading(false);
    }
  };

  return (
    <Card className="border-dashed border-2">
      <CardContent className="flex flex-col items-center justify-center py-6 space-y-4">
        <div className="grid w-full max-w-sm items-center gap-1.5 text-center">
          <Label htmlFor="file" className="cursor-pointer">
            <div className="flex flex-col items-center space-y-2">
              <div className="p-4 bg-secondary rounded-full">
                <Upload className="h-6 w-6" />
              </div>
              <span className="text-sm font-medium">
                {file ? file.name : "Click to select PDF"}
              </span>
            </div>
          </Label>
          <Input 
            id="file" 
            type="file" 
            accept=".pdf"
            className="hidden" 
            onChange={handleFileChange} 
          />
        </div>

        {file && (
          <Button onClick={handleUpload} disabled={uploading}>
            {uploading ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Uploading...
              </>
            ) : (
              'Upload Document'
            )}
          </Button>
        )}

        {status === 'success' && (
          <div className="flex items-center text-green-600 text-sm">
            <CheckCircle className="mr-2 h-4 w-4" />
            Upload successful!
          </div>
        )}

        {status === 'error' && (
          <div className="flex items-center text-red-600 text-sm">
            <AlertCircle className="mr-2 h-4 w-4" />
            {errorMessage}
          </div>
        )}
      </CardContent>
    </Card>
  );
};

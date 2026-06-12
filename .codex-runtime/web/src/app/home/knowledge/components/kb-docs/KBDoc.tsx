import { useCallback, useEffect, useRef, useState } from 'react';
import { httpClient } from '@/app/infra/http/HttpClient';
import { KnowledgeBaseFile } from '@/app/infra/entities/api';
import { I18nObject, CustomApiError } from '@/app/infra/entities/common';
import { columns, DocumentFile } from './documents/columns';
import { DataTable } from './documents/data-table';
import FileUploadZone from './FileUploadZone';
import { toast } from 'sonner';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Upload, Search } from 'lucide-react';

export default function KBDoc({
  kbId,
  ragEngineName,
  ragEngineCapabilities,
}: {
  kbId: string;
  ragEngineName?: I18nObject;
  ragEngineCapabilities?: string[];
}) {
  const [documentsList, setDocumentsList] = useState<DocumentFile[]>([]);
  const [keyword, setKeyword] = useState('');
  const [uploadOpen, setUploadOpen] = useState(false);
  const { t } = useTranslation();
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const getDocumentsList = useCallback(async () => {
    const resp = await httpClient.getKnowledgeBaseFiles(kbId);
    const files = resp.files.map((file: KnowledgeBaseFile) => ({
      uuid: file.uuid,
      name: file.file_name,
      status: file.status,
      createdAt: file.created_at,
      chunkCount: file.chunk_count,
    }));
    setDocumentsList(files);
    return files;
  }, [kbId]);

  const startPolling = useCallback(() => {
    if (intervalRef.current) return;
    intervalRef.current = setInterval(() => {
      getDocumentsList().then((files) => {
        const allDone =
          files.length > 0 &&
          files.every(
            (doc: DocumentFile) =>
              doc.status === 'completed' || doc.status === 'failed',
          );
        if (allDone && intervalRef.current) {
          clearInterval(intervalRef.current);
          intervalRef.current = null;
        }
      });
    }, 5000);
  }, [getDocumentsList]);

  useEffect(() => {
    getDocumentsList().then((files) => {
      const hasProcessing = files.some(
        (doc: DocumentFile) =>
          doc.status !== 'completed' && doc.status !== 'failed',
      );
      if (hasProcessing) {
        startPolling();
      }
    });

    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    };
  }, [kbId, getDocumentsList, startPolling]);

  const handleUploadSuccess = () => {
    getDocumentsList();
    startPolling();
    setUploadOpen(false);
  };

  const handleUploadError = (error: string) => {
    console.error('Upload failed:', error);
  };

  const handleDelete = (id: string) => {
    httpClient
      .deleteKnowledgeBaseFile(kbId, id)
      .then(() => {
        getDocumentsList();
        toast.success(t('knowledge.documentsTab.fileDeleteSuccess'));
      })
      .catch((error) => {
        console.error('Delete failed:', error);
        toast.error(
          t('knowledge.documentsTab.fileDeleteFailed') +
            (error as CustomApiError).msg,
        );
      });
  };

  const filteredDocuments = documentsList.filter((doc) => {
    const normalizedKeyword = keyword.trim().toLowerCase();
    if (!normalizedKeyword) return true;
    return doc.name.toLowerCase().includes(normalizedKeyword);
  });

  return (
    <div className="space-y-4 pb-8">
      <div className="flex flex-col gap-3 rounded-lg border border-slate-200 bg-white p-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="relative w-full sm:max-w-sm">
          <Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-slate-400" />
          <Input
            value={keyword}
            onChange={(event) => setKeyword(event.target.value)}
            className="h-10 border-slate-200 bg-white pl-9 text-sm"
            placeholder={t('knowledge.documentsTab.searchPlaceholder')}
          />
        </div>
        <Button className="shrink-0" onClick={() => setUploadOpen(true)}>
          <Upload className="size-4" />
          {t('knowledge.documentsTab.uploadFile')}
        </Button>
      </div>

      <DataTable
        columns={columns(handleDelete, t)}
        data={filteredDocuments}
      />

      <FileUploadZone
        variant="modal"
        open={uploadOpen}
        onOpenChange={setUploadOpen}
        kbId={kbId}
        ragEngineName={ragEngineName}
        ragEngineCapabilities={ragEngineCapabilities}
        onUploadSuccess={handleUploadSuccess}
        onUploadError={handleUploadError}
      />
    </div>
  );
}

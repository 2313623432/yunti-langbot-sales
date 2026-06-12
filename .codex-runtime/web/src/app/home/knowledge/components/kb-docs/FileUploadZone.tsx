import React, { useCallback, useEffect, useId, useState } from 'react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Button } from '@/components/ui/button';
import { httpClient } from '@/app/infra/http/HttpClient';
import { toast } from 'sonner';
import { useTranslation } from 'react-i18next';
import { ParserInfo } from '@/app/infra/entities/api';
import { CustomApiError, I18nObject } from '@/app/infra/entities/common';
import { extractI18nObject } from '@/i18n/I18nProvider';
import { Upload } from 'lucide-react';
import { cn } from '@/lib/utils';

interface FileUploadZoneProps {
  kbId: string;
  ragEngineName?: I18nObject;
  ragEngineCapabilities?: string[];
  onUploadSuccess: () => void;
  onUploadError: (error: string) => void;
  variant?: 'inline' | 'modal';
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
}

export default function FileUploadZone({
  kbId,
  ragEngineName,
  ragEngineCapabilities,
  onUploadSuccess,
  onUploadError,
  variant = 'inline',
  open = false,
  onOpenChange,
}: FileUploadZoneProps) {
  const { t } = useTranslation();
  const inputId = useId();
  const [isDragOver, setIsDragOver] = useState(false);
  const [isUploading, setIsUploading] = useState(false);

  const [pendingFile, setPendingFile] = useState<File | null>(null);
  const [availableParsers, setAvailableParsers] = useState<ParserInfo[]>([]);
  const [selectedParser, setSelectedParser] = useState<string>('builtin');
  const [loadingParsers, setLoadingParsers] = useState(false);

  const ragEngineCanParse =
    ragEngineCapabilities?.includes('doc_parsing') ?? false;
  const ragEngineCanIngest =
    ragEngineCapabilities?.includes('doc_ingestion') ?? true;
  const canDirectUpload = ragEngineCanParse || ragEngineCanIngest;

  const resetUploadState = useCallback(() => {
    setPendingFile(null);
    setAvailableParsers([]);
    setSelectedParser('builtin');
    setIsDragOver(false);
    setLoadingParsers(false);
  }, []);

  useEffect(() => {
    if (variant === 'modal' && !open) {
      resetUploadState();
    }
  }, [open, variant, resetUploadState]);

  useEffect(() => {
    if (!pendingFile) return;

    const mimeType = pendingFile.type || undefined;
    setLoadingParsers(true);
    httpClient
      .listParsers(mimeType)
      .then((resp) => {
        const parsers = resp.parsers || [];
        setAvailableParsers(parsers);
        if (ragEngineCanParse) {
          setSelectedParser('builtin');
        } else if (parsers.length > 0) {
          setSelectedParser(parsers[0].plugin_id);
        } else {
          setSelectedParser('');
        }
      })
      .catch(() => {
        setAvailableParsers([]);
      })
      .finally(() => {
        setLoadingParsers(false);
      });
  }, [pendingFile, ragEngineCanParse]);

  const doUpload = useCallback(
    async (file: File, parserPluginId?: string) => {
      setIsUploading(true);
      const toastId = toast.loading(t('knowledge.documentsTab.uploadingFile'));

      try {
        const uploadResult = await httpClient.uploadDocumentFile(file);
        await httpClient.uploadKnowledgeBaseFile(
          kbId,
          uploadResult.file_id,
          parserPluginId,
        );

        toast.success(t('knowledge.documentsTab.uploadSuccess'), {
          id: toastId,
        });
        onUploadSuccess();
      } catch (error) {
        console.error('File upload failed:', error);
        const errorMessage =
          t('knowledge.documentsTab.uploadError') +
          (error as CustomApiError).msg;
        toast.error(errorMessage, { id: toastId });
        onUploadError(errorMessage);
      } finally {
        setIsUploading(false);
        resetUploadState();
      }
    },
    [kbId, onUploadSuccess, onUploadError, resetUploadState, t],
  );

  const handleFileSelected = useCallback(
    async (file: File) => {
      if (isUploading) return;

      const MAX_FILE_SIZE = 500 * 1024 * 1024;
      if (file.size > MAX_FILE_SIZE) {
        toast.error(t('knowledge.documentsTab.fileSizeExceeded'));
        return;
      }

      setLoadingParsers(true);
      setPendingFile(file);
    },
    [isUploading, t],
  );

  useEffect(() => {
    if (pendingFile && !loadingParsers && canDirectUpload) {
      doUpload(pendingFile);
    }
  }, [pendingFile, loadingParsers, canDirectUpload, doUpload]);

  const handleConfirmUpload = useCallback(() => {
    if (!pendingFile) return;
    const parserPluginId =
      selectedParser === 'builtin' ? undefined : selectedParser;
    doUpload(pendingFile, parserPluginId);
  }, [pendingFile, selectedParser, doUpload]);

  const handleCancelUpload = useCallback(() => {
    resetUploadState();
  }, [resetUploadState]);

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
  }, []);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setIsDragOver(false);

      const files = Array.from(e.dataTransfer.files);
      if (files.length > 0) {
        handleFileSelected(files[0]);
      }
    },
    [handleFileSelected],
  );

  const handleFileSelect = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const files = e.target.files;
      if (files && files.length > 0) {
        handleFileSelected(files[0]);
      }
      e.target.value = '';
    },
    [handleFileSelected],
  );

  const showParserSelector =
    pendingFile &&
    !loadingParsers &&
    !canDirectUpload &&
    availableParsers.length > 0;

  const noParserAvailable = !ragEngineCanParse && availableParsers.length === 0;

  const uploadBody = (
    <div className="space-y-4">
      {showParserSelector ? (
        <div className="space-y-3">
          <p className="text-sm font-medium text-slate-900 dark:text-slate-100">
            {pendingFile.name}
          </p>
          {noParserAvailable ? (
            <div className="rounded-md border border-yellow-200 bg-yellow-50 p-3 dark:border-yellow-800 dark:bg-yellow-900/20">
              <p className="text-sm text-yellow-800 dark:text-yellow-200">
                {t('knowledge.documentsTab.noParserAvailable')}
              </p>
              <p className="mt-1 text-sm text-yellow-800 dark:text-yellow-200">
                {t('knowledge.documentsTab.useBuiltinParserHint')}
              </p>
            </div>
          ) : (
            <div className="space-y-2">
              <label className="text-sm text-slate-600 dark:text-slate-400">
                {t('knowledge.documentsTab.selectParser')}
              </label>
              <Select value={selectedParser} onValueChange={setSelectedParser}>
                <SelectTrigger className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {ragEngineCanParse && (
                    <SelectItem value="builtin">
                      {ragEngineName
                        ? extractI18nObject(ragEngineName)
                        : t('knowledge.documentsTab.builtInParser')}
                    </SelectItem>
                  )}
                  {availableParsers.map((parser) => (
                    <SelectItem
                      key={parser.plugin_id}
                      value={parser.plugin_id}
                    >
                      {extractI18nObject(parser.name)}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          )}
          <div className="flex justify-end gap-2">
            <Button variant="outline" size="sm" onClick={handleCancelUpload}>
              {t('knowledge.documentsTab.cancelUpload')}
            </Button>
            {!noParserAvailable && (
              <Button size="sm" onClick={handleConfirmUpload}>
                {t('knowledge.documentsTab.confirmUpload')}
              </Button>
            )}
          </div>
        </div>
      ) : (
        <div
          className={cn(
            'relative rounded-lg border-2 border-dashed p-8 text-center transition-colors',
            isDragOver
              ? 'border-blue-500 bg-blue-50'
              : 'border-slate-200 hover:border-slate-300',
            (isUploading || loadingParsers) && 'pointer-events-none opacity-50',
          )}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
        >
          <input
            type="file"
            id={inputId}
            className="hidden"
            onChange={handleFileSelect}
            accept=".pdf,.doc,.docx,.txt,.md,.html,.xlsx,.zip"
            disabled={isUploading || loadingParsers}
          />

          <label htmlFor={inputId} className="block cursor-pointer">
            <div className="space-y-3">
              <div className="mx-auto flex size-12 items-center justify-center rounded-full bg-slate-100 text-slate-400">
                <Upload className="size-5" />
              </div>
              <div>
                <p className="text-base font-medium text-slate-900 dark:text-slate-100">
                  {isUploading
                    ? t('knowledge.documentsTab.uploading')
                    : t('knowledge.documentsTab.dragAndDrop')}
                </p>
                <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
                  {t('knowledge.documentsTab.supportedFormats')}
                </p>
              </div>
            </div>
          </label>
        </div>
      )}
    </div>
  );

  if (variant === 'modal') {
    return (
      <Dialog open={open} onOpenChange={onOpenChange}>
        <DialogContent className="sm:max-w-lg">
          <DialogHeader>
            <DialogTitle>{t('knowledge.documentsTab.uploadDialogTitle')}</DialogTitle>
            <DialogDescription>
              {t('knowledge.documentsTab.uploadDialogDescription')}
            </DialogDescription>
          </DialogHeader>
          {uploadBody}
        </DialogContent>
      </Dialog>
    );
  }

  return (
    <div className="mb-4 rounded-lg border border-slate-200 bg-white p-4">
      {uploadBody}
    </div>
  );
}

import { useState, type ChangeEvent } from 'react';
import { Upload } from 'lucide-react';
import { toast } from 'sonner';
import { httpClient } from '@/app/infra/http/HttpClient';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import {
  agentAvatarUrl,
  DEFAULT_AGENT_AVATAR,
  PRESET_AGENT_AVATARS,
} from './agentAvatar';

interface AgentAvatarPickerProps {
  value?: string;
  onChange: (value: string) => void;
  uploadInputId: string;
}

export default function AgentAvatarPicker({
  value,
  onChange,
  uploadInputId,
}: AgentAvatarPickerProps) {
  const [uploadingAvatar, setUploadingAvatar] = useState(false);
  const selectedAvatar = value || DEFAULT_AGENT_AVATAR;

  async function uploadAgentAvatar(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;

    try {
      setUploadingAvatar(true);
      const result = await httpClient.uploadImage(file);
      onChange(result.file_key);
      toast.success('头像已上传');
    } catch (error) {
      console.error('Agent avatar upload failed:', error);
      toast.error('头像上传失败');
    } finally {
      setUploadingAvatar(false);
      event.target.value = '';
    }
  }

  return (
    <div className="flex flex-col gap-4 rounded-md border border-slate-200 bg-slate-50 p-4 md:flex-row md:items-center">
      <img
        src={agentAvatarUrl(selectedAvatar)}
        alt="Agent头像预览"
        className="size-20 shrink-0 rounded-full border border-white bg-white object-cover shadow-sm"
      />
      <div className="min-w-0 flex-1 space-y-3">
        <div className="flex flex-wrap gap-2">
          {PRESET_AGENT_AVATARS.map((avatar) => {
            const selected = selectedAvatar === avatar.src;
            return (
              <button
                key={avatar.src}
                type="button"
                title={avatar.label}
                onClick={() => onChange(avatar.src)}
                className={cn(
                  'size-14 overflow-hidden rounded-full border bg-white p-0.5 transition',
                  selected
                    ? 'border-blue-500 ring-2 ring-blue-100'
                    : 'border-slate-200 hover:border-blue-300',
                )}
              >
                <img
                  src={avatar.src}
                  alt={avatar.label}
                  className="size-full rounded-full object-cover"
                />
              </button>
            );
          })}
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <Button
            type="button"
            variant="outline"
            className="h-9 rounded-md bg-white"
            disabled={uploadingAvatar}
            onClick={() => document.getElementById(uploadInputId)?.click()}
          >
            <Upload className="mr-1.5 size-4" />
            {uploadingAvatar ? '上传中' : '上传头像'}
          </Button>
          <input
            id={uploadInputId}
            type="file"
            className="hidden"
            accept="image/*"
            onChange={uploadAgentAvatar}
          />
        </div>
      </div>
    </div>
  );
}

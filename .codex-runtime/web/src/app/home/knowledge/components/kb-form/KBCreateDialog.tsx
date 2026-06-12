import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import KBForm from '@/app/home/knowledge/components/kb-form/KBForm';
import { useTranslation } from 'react-i18next';

interface KBCreateDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onCreated: (kbId: string) => void;
}

export default function KBCreateDialog({
  open,
  onOpenChange,
  onCreated,
}: KBCreateDialogProps) {
  const { t } = useTranslation();

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="flex max-h-[85vh] max-w-2xl flex-col gap-0 overflow-hidden p-0 sm:max-w-2xl">
        <DialogHeader className="shrink-0 border-b border-slate-100 px-6 py-5">
          <DialogTitle className="text-xl">
            {t('knowledge.createKnowledgeBase')}
          </DialogTitle>
          <DialogDescription>
            {t('knowledge.createDialogDescription')}
          </DialogDescription>
        </DialogHeader>

        <div className="min-h-0 flex-1 overflow-y-auto px-6 py-5">
          <KBForm
            initKbId={undefined}
            onNewKbCreated={(kbId) => {
              onCreated(kbId);
              onOpenChange(false);
            }}
            onKbUpdated={() => {}}
          />
        </div>

        <DialogFooter className="shrink-0 border-t border-slate-100 px-6 py-4">
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            {t('common.cancel')}
          </Button>
          <Button type="submit" form="kb-form">
            {t('common.submit')}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

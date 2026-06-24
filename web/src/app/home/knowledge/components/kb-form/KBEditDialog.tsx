import { useEffect } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { useTranslation } from 'react-i18next';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from '@/components/ui/form';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { httpClient } from '@/app/infra/http/HttpClient';
import { CustomApiError } from '@/app/infra/entities/common';
import { toast } from 'sonner';
import { DEFAULT_KB_EMOJI } from '@/app/home/knowledge/constants';

const getFormSchema = (t: (key: string) => string) =>
  z.object({
    name: z.string().min(1, { message: t('knowledge.kbNameRequired') }),
    description: z.string().optional(),
  });

interface KBEditDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  kbId: string;
  initialName: string;
  initialDescription?: string;
  onUpdated: () => void;
}

export default function KBEditDialog({
  open,
  onOpenChange,
  kbId,
  initialName,
  initialDescription,
  onUpdated,
}: KBEditDialogProps) {
  const { t } = useTranslation();
  const formSchema = getFormSchema(t);

  const form = useForm<z.infer<typeof formSchema>>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      name: initialName,
      description: initialDescription ?? '',
    },
  });

  useEffect(() => {
    if (open) {
      form.reset({
        name: initialName,
        description: initialDescription ?? '',
      });
    }
  }, [open, initialName, initialDescription, form]);

  const onSubmit = async (data: z.infer<typeof formSchema>) => {
    try {
      await httpClient.updateKnowledgeBase(kbId, {
        name: data.name,
        description: data.description ?? '',
        emoji: DEFAULT_KB_EMOJI,
      });
      toast.success(t('knowledge.updateKnowledgeBaseSuccess'));
      onUpdated();
      onOpenChange(false);
    } catch (err) {
      toast.error(
        t('knowledge.updateKnowledgeBaseFailed') + (err as CustomApiError).msg,
      );
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>{t('knowledge.editKbInfo')}</DialogTitle>
          <DialogDescription>{t('knowledge.editKbInfoDescription')}</DialogDescription>
        </DialogHeader>

        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
            <FormField
              control={form.control}
              name="name"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>
                    {t('knowledge.kbName')}
                    <span className="text-destructive">*</span>
                  </FormLabel>
                  <FormControl>
                    <Input {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            <FormField
              control={form.control}
              name="description"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>{t('knowledge.kbDescription')}</FormLabel>
                  <FormControl>
                    <Input {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            <DialogFooter>
              <Button
                type="button"
                variant="outline"
                onClick={() => onOpenChange(false)}
              >
                {t('common.cancel')}
              </Button>
              <Button type="submit">{t('common.save')}</Button>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  );
}

import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { useTranslation } from 'react-i18next';
import { Input } from '@/components/ui/input';
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from '@/components/ui/form';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { httpClient } from '@/app/infra/http/HttpClient';
import { CustomApiError } from '@/app/infra/entities/common';
import { toast } from 'sonner';
import {
  BUILTIN_KNOWLEDGE_ENGINE_ID,
  DEFAULT_KB_EMOJI,
} from '@/app/home/knowledge/constants';

const getFormSchema = (t: (key: string) => string) =>
  z.object({
    name: z.string().min(1, { message: t('knowledge.kbNameRequired') }),
    description: z.string().optional(),
  });

export default function KBForm({
  onNewKbCreated,
}: {
  initKbId?: string;
  onNewKbCreated: (kbId: string) => void;
  onKbUpdated?: (kbId: string) => void;
  onDirtyChange?: (dirty: boolean) => void;
}) {
  const { t } = useTranslation();
  const formSchema = getFormSchema(t);

  const form = useForm<z.infer<typeof formSchema>>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      name: '',
      description: '',
    },
  });

  const onSubmit = async (data: z.infer<typeof formSchema>) => {
    httpClient
      .createKnowledgeBase({
        name: data.name,
        description: data.description ?? '',
        emoji: DEFAULT_KB_EMOJI,
        knowledge_engine_plugin_id: BUILTIN_KNOWLEDGE_ENGINE_ID,
        creation_settings: {},
        retrieval_settings: {},
      })
      .then((res) => {
        onNewKbCreated(res.uuid);
      })
      .catch((err) => {
        console.error('create knowledge base failed', err);
        toast.error(
          t('knowledge.createKnowledgeBaseFailed') +
            (err as CustomApiError).msg,
        );
      });
  };

  return (
    <Form {...form}>
      <form
        onSubmit={form.handleSubmit(onSubmit)}
        id="kb-form"
        className="space-y-6"
      >
        <Card>
          <CardHeader>
            <CardTitle>{t('knowledge.basicInfo')}</CardTitle>
            <CardDescription>
              {t('knowledge.basicInfoDescription')}
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
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
          </CardContent>
        </Card>
      </form>
    </Form>
  );
}

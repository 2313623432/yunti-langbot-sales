import { useEffect } from 'react';
import { httpClient } from '@/app/infra/http/HttpClient';

import { zodResolver } from '@hookform/resolvers/zod';
import { useForm } from 'react-hook-form';
import { z } from 'zod';
import { useTranslation } from 'react-i18next';

import { Button } from '@/components/ui/button';
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from '@/components/ui/form';
import { Input } from '@/components/ui/input';
import { DialogFooter } from '@/components/ui/dialog';
import { toast } from 'sonner';
import { CustomApiError } from '@/app/infra/entities/common';
import {
  getDefaultBaseUrlForProtocol,
  getRequesterForProtocol,
  PROVIDER_PROTOCOLS,
  ProviderProtocol,
  resolveProviderProtocol,
} from '../../protocolUtils';

const getFormSchema = (t: (key: string) => string) =>
  z.object({
    name: z.string().min(1, { message: t('models.providerNameRequired') }),
    protocol: z.enum(['openai', 'claude', 'gemini'], {
      message: t('models.requesterRequired'),
    }),
    base_url: z.string(),
    api_key: z.string().optional(),
  });

interface ProviderFormProps {
  providerId?: string;
  onFormSubmit: () => void;
  onFormCancel: () => void;
}

export default function ProviderForm({
  providerId,
  onFormSubmit,
  onFormCancel,
}: ProviderFormProps) {
  const { t } = useTranslation();
  const formSchema = getFormSchema(t);

  const form = useForm<z.infer<typeof formSchema>>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      name: '',
      protocol: 'openai',
      base_url: getDefaultBaseUrlForProtocol('openai'),
      api_key: '',
    },
  });

  useEffect(() => {
    async function init() {
      if (providerId) {
        await loadProvider(providerId);
      }
    }
    init();
  }, [providerId]);

  async function loadProvider(id: string) {
    const resp = await httpClient.getModelProvider(id);
    const provider = resp.provider;
    const protocol = resolveProviderProtocol(provider);

    form.setValue('name', provider.name);
    form.setValue('protocol', protocol);
    form.setValue('base_url', provider.base_url);
    form.setValue('api_key', provider.api_keys?.[0] || '');
  }

  async function handleFormSubmit(values: z.infer<typeof formSchema>) {
    const protocol = values.protocol;
    const data = {
      name: values.name,
      protocol,
      requester: getRequesterForProtocol(protocol),
      base_url: values.base_url,
      api_keys: values.api_key ? [values.api_key] : [],
    };

    try {
      form.clearErrors();
      if (providerId) {
        await httpClient.updateModelProvider(providerId, data);
        toast.success(t('models.providerSaved'));
      } else {
        await httpClient.createModelProvider(data);
        toast.success(t('models.providerCreated'));
      }
      onFormSubmit();
    } catch (err) {
      toast.error(t('models.providerSaveError') + (err as CustomApiError).msg);
    }
  }

  function handleProtocolChange(protocol: ProviderProtocol) {
    form.setValue('protocol', protocol);
    if (!providerId || !form.getValues('base_url')) {
      form.setValue('base_url', getDefaultBaseUrlForProtocol(protocol));
    }
  }

  return (
    <Form {...form}>
      <form
        onSubmit={form.handleSubmit(handleFormSubmit, (errors) => {
          const firstError = Object.values(errors)[0];
          if (firstError?.message) {
            toast.error(String(firstError.message));
          } else {
            toast.error(t('models.providerSaveError'));
          }
        })}
        className="space-y-4"
      >
        <FormField
          control={form.control}
          name="name"
          render={({ field }) => (
            <FormItem>
              <FormLabel>
                {t('models.providerName')}
                <span className="text-red-500">*</span>
              </FormLabel>
              <FormControl>
                <Input
                  {...field}
                  placeholder={t('models.providerNamePlaceholder')}
                />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />

        <FormField
          control={form.control}
          name="protocol"
          render={({ field }) => (
            <FormItem>
              <FormLabel>
                {t('models.apiMode')}
                <span className="text-red-500">*</span>
              </FormLabel>
              <div className="flex flex-wrap gap-2">
                {PROVIDER_PROTOCOLS.map((protocol) => {
                  const active = field.value === protocol;
                  return (
                    <button
                      key={protocol}
                      type="button"
                      className={`rounded-full border px-4 py-1.5 text-sm transition-colors ${
                        active
                          ? 'border-violet-500 bg-violet-50 text-violet-700'
                          : 'border-slate-200 bg-background text-slate-700 hover:bg-slate-50'
                      }`}
                      onClick={() => handleProtocolChange(protocol)}
                    >
                      {t(`models.protocol.${protocol}`)}
                    </button>
                  );
                })}
              </div>
              <FormMessage />
              <p className="text-sm text-muted-foreground">
                {t('models.requesterHint')}
              </p>
            </FormItem>
          )}
        />

        <FormField
          control={form.control}
          name="base_url"
          render={({ field }) => (
            <FormItem>
              <FormLabel>{t('models.requestURL')}</FormLabel>
              <FormControl>
                <Input {...field} />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />

        <FormField
          control={form.control}
          name="api_key"
          render={({ field }) => (
            <FormItem>
              <FormLabel>{t('models.apiKey')}</FormLabel>
              <FormControl>
                <Input {...field} type="password" />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />

        <DialogFooter>
          <Button type="submit" disabled={form.formState.isSubmitting}>
            {t('common.save')}
          </Button>
          <Button type="button" variant="outline" onClick={onFormCancel}>
            {t('common.cancel')}
          </Button>
        </DialogFooter>
      </form>
    </Form>
  );
}

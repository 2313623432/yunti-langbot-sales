import { useEffect, useState } from 'react';
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
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectLabel,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { DialogFooter } from '@/components/ui/dialog';
import { toast } from 'sonner';
import { extractI18nObject } from '@/i18n/I18nProvider';
import { CustomApiError } from '@/app/infra/entities/common';

const DEFAULT_REQUESTER = 'openai-chat-completions';
const RECOMMENDED_REQUESTERS = [
  DEFAULT_REQUESTER,
  'anthropic-messages',
  'ollama-chat',
  'lmstudio-chat-completions',
];

const getFormSchema = (t: (key: string) => string) =>
  z.object({
    name: z.string().min(1, { message: t('models.providerNameRequired') }),
    requester: z.string().min(1, { message: t('models.requesterRequired') }),
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
      requester: '',
      base_url: '',
      api_key: '',
    },
  });

  const [requesterList, setRequesterList] = useState<
    {
      label: string;
      value: string;
      category: string;
      defaultUrl: string;
      description: string;
    }[]
  >([]);

  function getRequesterLabel(requester: { label: string; value: string }) {
    if (requester.value === 'openai-chat-completions') {
      return t('models.openaiCompatible');
    }
    if (requester.value === 'anthropic-messages') {
      return t('models.anthropicCompatible');
    }
    return requester.label;
  }

  function isRecommendedRequester(requester: { value: string }) {
    return RECOMMENDED_REQUESTERS.includes(requester.value);
  }

  useEffect(() => {
    async function init() {
      await loadRequesters();
      if (providerId) {
        await loadProvider(providerId);
      }
    }
    init();
  }, [providerId]);

  async function loadRequesters() {
    const resp = await httpClient.getProviderRequesters();
    const requesters = resp.requesters
      .filter((item) => item.name !== 'space-chat-completions')
      .map((item) => ({
        label: extractI18nObject(item.label),
        value: item.name,
        category: item.spec.provider_category || 'manufacturer',
        defaultUrl:
          item.spec.config
            .find((c) => c.name === 'base_url')
            ?.default?.toString() || '',
        description: extractI18nObject(item.description),
      }));

    setRequesterList(requesters);

    if (!providerId && !form.getValues('requester')) {
      const defaultRequester =
        requesters.find((item) => item.value === DEFAULT_REQUESTER) ||
        requesters.find(isRecommendedRequester);
      if (defaultRequester) {
        form.setValue('requester', defaultRequester.value);
        form.setValue('base_url', defaultRequester.defaultUrl);
      }
    }
  }

  function renderRequesterOption(requester: { label: string; value: string }) {
    const label = getRequesterLabel(requester);

    return (
      <SelectItem key={requester.value} value={requester.value}>
        <div className="flex items-center gap-2">
          <img
            src={httpClient.getProviderRequesterIconURL(requester.value)}
            alt={label}
            className="h-5 w-5 rounded"
          />
          <span>{label}</span>
        </div>
      </SelectItem>
    );
  }

  async function loadProvider(id: string) {
    const resp = await httpClient.getModelProvider(id);
    const provider = resp.provider;

    form.setValue('name', provider.name);
    form.setValue('requester', provider.requester);
    form.setValue('base_url', provider.base_url);
    form.setValue('api_key', provider.api_keys?.[0] || '');
  }

  async function handleFormSubmit(values: z.infer<typeof formSchema>) {
    const data = {
      name: values.name,
      requester: values.requester,
      base_url: values.base_url,
      api_keys: values.api_key ? [values.api_key] : [],
    };

    try {
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

  return (
    <Form {...form}>
      <form
        onSubmit={form.handleSubmit(handleFormSubmit)}
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
          name="requester"
          render={({ field }) => {
            const selectedRequester = requesterList.find(
              (r) => r.value === field.value,
            );
            const recommendedRequesters = requesterList.filter(
              isRecommendedRequester,
            );
            const builtinRequesters = requesterList.filter(
              (r) => r.category === 'builtin',
            );
            const otherRequesters = requesterList.filter(
              (r) => !isRecommendedRequester(r) && r.category !== 'builtin',
            );
            return (
              <FormItem>
                <FormLabel>
                  {t('models.requester')}
                  <span className="text-red-500">*</span>
                </FormLabel>
                <Select
                  onValueChange={(v) => {
                    field.onChange(v);
                    const req = requesterList.find((r) => r.value === v);
                    if (req && (!providerId || !form.getValues('base_url'))) {
                      form.setValue('base_url', req.defaultUrl);
                    }
                  }}
                  value={field.value}
                >
                  <SelectTrigger className="bg-background">
                    {selectedRequester ? (
                      <div className="flex items-center gap-2">
                        <img
                          src={httpClient.getProviderRequesterIconURL(
                            selectedRequester.value,
                          )}
                          alt={getRequesterLabel(selectedRequester)}
                          className="h-5 w-5 rounded"
                        />
                        <span>{getRequesterLabel(selectedRequester)}</span>
                      </div>
                    ) : (
                      <SelectValue placeholder={t('models.selectRequester')} />
                    )}
                  </SelectTrigger>
                  <SelectContent>
                    {recommendedRequesters.length > 0 && (
                      <SelectGroup>
                        <SelectLabel>
                          {t('models.recommendedProtocols')}
                        </SelectLabel>
                        {recommendedRequesters.map(renderRequesterOption)}
                      </SelectGroup>
                    )}
                    {otherRequesters.length > 0 && (
                      <SelectGroup>
                        <SelectLabel>
                          {t('models.otherProtocolAdapters')}
                        </SelectLabel>
                        {otherRequesters.map(renderRequesterOption)}
                      </SelectGroup>
                    )}
                    {builtinRequesters.length > 0 && (
                      <SelectGroup>
                        <SelectLabel>{t('models.builtin')}</SelectLabel>
                        {builtinRequesters.map(renderRequesterOption)}
                      </SelectGroup>
                    )}
                  </SelectContent>
                </Select>
                <FormMessage />
                <p className="text-sm text-muted-foreground">
                  {t('models.requesterHint')}
                </p>
                {selectedRequester?.description && (
                  <p className="text-xs text-muted-foreground">
                    {selectedRequester.description}
                  </p>
                )}
              </FormItem>
            );
          }}
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
          <Button type="submit">{t('common.save')}</Button>
          <Button type="button" variant="outline" onClick={onFormCancel}>
            {t('common.cancel')}
          </Button>
        </DialogFooter>
      </form>
    </Form>
  );
}

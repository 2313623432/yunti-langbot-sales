import { ExtraArg } from './types';

export const LLM_STRUCTURED_EXTRA_ARG_KEYS = new Set([
  'display_name',
  'context_window',
  'max_output_tokens',
  'streaming',
]);

export interface LLMModelFormValues {
  modelId: string;
  displayName: string;
  abilities: string[];
  streaming: boolean;
  contextWindow: string;
  maxOutputTokens: string;
  customExtraArgs: ExtraArg[];
}

export function getModelDisplayName(
  name: string,
  extraArgs?: object,
): string {
  const displayName = (extraArgs as { display_name?: string } | undefined)
    ?.display_name;
  return displayName?.trim() || name;
}

export function llmFormValuesFromModel(
  name: string,
  abilities: string[] = [],
  extraArgs?: object,
): LLMModelFormValues {
  const args = (extraArgs || {}) as Record<string, unknown>;
  const customExtraArgs = Object.entries(args)
    .filter(([key]) => !LLM_STRUCTURED_EXTRA_ARG_KEYS.has(key))
    .map(([key, value]) => {
      let type: ExtraArg['type'] = 'string';
      let stringValue: string;
      if (typeof value === 'number') {
        type = 'number';
        stringValue = String(value);
      } else if (typeof value === 'boolean') {
        type = 'boolean';
        stringValue = String(value);
      } else if (
        value !== null &&
        typeof value === 'object' &&
        !Array.isArray(value)
      ) {
        type = 'object';
        stringValue = JSON.stringify(value, null, 2);
      } else {
        stringValue = String(value ?? '');
      }
      return { key, type, value: stringValue };
    });

  return {
    modelId: name,
    displayName: typeof args.display_name === 'string' ? args.display_name : '',
    abilities,
    streaming: args.streaming !== false,
    contextWindow:
      typeof args.context_window === 'number'
        ? String(args.context_window)
        : '',
    maxOutputTokens:
      typeof args.max_output_tokens === 'number'
        ? String(args.max_output_tokens)
        : '',
    customExtraArgs,
  };
}

export function llmFormValuesToPayload(values: LLMModelFormValues): {
  name: string;
  abilities: string[];
  extraArgs: ExtraArg[];
} {
  const extraArgs: ExtraArg[] = [...values.customExtraArgs];
  if (values.displayName.trim()) {
    extraArgs.push({
      key: 'display_name',
      type: 'string',
      value: values.displayName.trim(),
    });
  }
  if (values.contextWindow.trim()) {
    extraArgs.push({
      key: 'context_window',
      type: 'number',
      value: values.contextWindow.trim(),
    });
  }
  if (values.maxOutputTokens.trim()) {
    extraArgs.push({
      key: 'max_output_tokens',
      type: 'number',
      value: values.maxOutputTokens.trim(),
    });
  }
  extraArgs.push({
    key: 'streaming',
    type: 'boolean',
    value: String(values.streaming),
  });

  return {
    name: values.modelId.trim(),
    abilities: values.abilities,
    extraArgs,
  };
}

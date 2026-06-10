import { useState, useEffect } from 'react';
import { Trash2, Eye, Wrench, Volume2, Check } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover';
import { useTranslation } from 'react-i18next';
import { LLMModel, EmbeddingModel } from '@/app/infra/entities/api';
import { ExtraArg, ModelType, TestResult } from '../types';
import ExtraArgsEditor from './ExtraArgsEditor';
import LLMModelFormFields from './LLMModelFormFields';
import {
  getModelDisplayName,
  llmFormValuesFromModel,
  llmFormValuesToPayload,
  LLMModelFormValues,
} from '../modelFormUtils';
import { userInfo } from '@/app/infra/http';

interface ModelItemProps {
  model: LLMModel | EmbeddingModel;
  modelType: ModelType;
  isLangBotModels: boolean;
  editModelPopoverOpen: string | null;
  deleteConfirmOpen: string | null;
  onOpenEditModel: (modelId: string) => void;
  onCloseEditModel: () => void;
  onOpenDeleteConfirm: (modelId: string) => void;
  onCloseDeleteConfirm: () => void;
  onDeleteModel: () => void;
  onUpdateModel: (
    name: string,
    abilities: string[],
    extraArgs: ExtraArg[],
  ) => Promise<void>;
  onTestModel: (
    name: string,
    abilities: string[],
    extraArgs: ExtraArg[],
  ) => Promise<void>;
  isSubmitting: boolean;
  isTesting: boolean;
  testResult: TestResult | null;
  onResetTestResult: () => void;
}

function convertExtraArgsToArray(extraArgs?: object): ExtraArg[] {
  if (!extraArgs) return [];
  return Object.entries(extraArgs).map(([key, value]) => {
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
      stringValue = String(value);
    }
    return { key, type, value: stringValue };
  });
}

export default function ModelItem({
  model,
  modelType,
  isLangBotModels,
  editModelPopoverOpen,
  deleteConfirmOpen,
  onOpenEditModel,
  onCloseEditModel,
  onOpenDeleteConfirm,
  onCloseDeleteConfirm,
  onDeleteModel,
  onUpdateModel,
  onTestModel,
  isSubmitting,
  isTesting,
  testResult,
  onResetTestResult,
}: ModelItemProps) {
  const { t } = useTranslation();

  const [editName, setEditName] = useState(model.name);
  const [editAbilities, setEditAbilities] = useState<string[]>(
    modelType === 'llm' ? (model as LLMModel).abilities || [] : [],
  );
  const [editExtraArgs, setEditExtraArgs] = useState<ExtraArg[]>(
    convertExtraArgsToArray(model.extra_args),
  );
  const [llmFormValues, setLlmFormValues] = useState<LLMModelFormValues>(() =>
    llmFormValuesFromModel(
      model.name,
      modelType === 'llm' ? (model as LLMModel).abilities || [] : [],
      model.extra_args,
    ),
  );

  const isEditOpen = editModelPopoverOpen === model.uuid;
  const isDeleteOpen = deleteConfirmOpen === model.uuid;

  // Reset form when popover opens
  useEffect(() => {
    if (isEditOpen) {
      setEditName(model.name);
      setEditAbilities(
        modelType === 'llm' ? (model as LLMModel).abilities || [] : [],
      );
      setEditExtraArgs(convertExtraArgsToArray(model.extra_args));
      setLlmFormValues(
        llmFormValuesFromModel(
          model.name,
          modelType === 'llm' ? (model as LLMModel).abilities || [] : [],
          model.extra_args,
        ),
      );
      onResetTestResult();
    }
  }, [isEditOpen]);

  const handleSave = async () => {
    if (modelType === 'llm') {
      const payload = llmFormValuesToPayload(llmFormValues);
      await onUpdateModel(payload.name, payload.abilities, payload.extraArgs);
      return;
    }
    await onUpdateModel(editName, editAbilities, editExtraArgs);
  };

  const handleTest = async () => {
    if (modelType === 'llm') {
      const payload = llmFormValuesToPayload(llmFormValues);
      await onTestModel(payload.name, payload.abilities, payload.extraArgs);
      return;
    }
    await onTestModel(editName, editAbilities, editExtraArgs);
  };

  const isPopoverDisabled =
    isLangBotModels && userInfo?.account_type !== 'space';
  const isVoiceOnlyModel =
    modelType === 'llm' &&
    (model as LLMModel).abilities?.includes('tts') &&
    ((model as LLMModel).abilities || []).every((ability) => ability === 'tts');

  return (
    <Popover
      open={isEditOpen && !isPopoverDisabled}
      onOpenChange={(open) => {
        if (isPopoverDisabled) return;
        if (open) {
          onOpenEditModel(model.uuid);
        } else {
          onCloseEditModel();
        }
      }}
    >
      <PopoverTrigger asChild>
        <div
          className={`flex items-center justify-between py-2 px-3 rounded-md border bg-background ${
            isPopoverDisabled
              ? 'cursor-not-allowed opacity-60'
              : 'hover:bg-accent cursor-pointer'
          }`}
        >
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-sm font-medium">
              {modelType === 'llm'
                ? getModelDisplayName(model.name, model.extra_args)
                : model.name}
            </span>
            {modelType === 'llm' &&
              getModelDisplayName(model.name, model.extra_args) !== model.name && (
                <span className="text-xs text-muted-foreground">{model.name}</span>
              )}
            <Badge variant="secondary" className="text-xs">
              {modelType === 'llm'
                ? isVoiceOnlyModel
                  ? t('models.ttsAbility')
                  : t('models.chat')
                : modelType === 'embedding'
                  ? t('models.embedding')
                  : t('models.rerank')}
            </Badge>
            {modelType === 'llm' &&
              (model as LLMModel).abilities?.includes('vision') && (
                <Badge variant="outline" className="text-xs gap-1">
                  <Eye className="h-3 w-3" />
                </Badge>
              )}
            {modelType === 'llm' &&
              (model as LLMModel).abilities?.includes('func_call') && (
                <Badge variant="outline" className="text-xs gap-1">
                  <Wrench className="h-3 w-3" />
                </Badge>
              )}
            {modelType === 'llm' &&
              (model as LLMModel).abilities?.includes('tts') && (
                <Badge variant="outline" className="text-xs gap-1">
                  <Volume2 className="h-3 w-3" />
                </Badge>
              )}
          </div>
          {!isLangBotModels && (
            <Popover
              open={isDeleteOpen}
              onOpenChange={(open) =>
                open ? onOpenDeleteConfirm(model.uuid) : onCloseDeleteConfirm()
              }
            >
              <PopoverTrigger asChild>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-7 w-7 flex-shrink-0"
                  onClick={(e) => {
                    e.stopPropagation();
                  }}
                >
                  <Trash2 className="h-4 w-4 text-muted-foreground hover:text-destructive" />
                </Button>
              </PopoverTrigger>
              <PopoverContent
                className="w-64"
                align="end"
                onClick={(e) => e.stopPropagation()}
              >
                <div className="space-y-3">
                  <p className="text-sm">{t('models.deleteConfirmation')}</p>
                  <div className="flex gap-2 justify-end">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => onCloseDeleteConfirm()}
                    >
                      {t('common.cancel')}
                    </Button>
                    <Button
                      variant="destructive"
                      size="sm"
                      onClick={() => {
                        onDeleteModel();
                        onCloseDeleteConfirm();
                      }}
                    >
                      {t('common.delete')}
                    </Button>
                  </div>
                </div>
              </PopoverContent>
            </Popover>
          )}
        </div>
      </PopoverTrigger>
      <PopoverContent
        className="w-80 max-h-[70vh] overflow-y-auto overscroll-none focus:outline-none focus-visible:outline-none focus-visible:ring-0"
        align="start"
        collisionPadding={16}
        style={{
          maxHeight: 'min(70vh, var(--radix-popover-content-available-height))',
        }}
        onWheel={(e) => e.stopPropagation()}
        onTouchMove={(e) => e.stopPropagation()}
      >
        <div className="space-y-3">
          {modelType === 'llm' ? (
            <LLMModelFormFields
              values={llmFormValues}
              onChange={setLlmFormValues}
              disabled={isLangBotModels}
            />
          ) : (
            <>
              <div className="space-y-2">
                <Label>{t('models.modelName')}</Label>
                <Input
                  placeholder={t('models.modelName')}
                  value={editName}
                  onChange={(e) => setEditName(e.target.value)}
                  disabled={isLangBotModels}
                />
              </div>

              <ExtraArgsEditor
                args={editExtraArgs}
                onChange={setEditExtraArgs}
                disabled={isLangBotModels}
                modelType={modelType}
              />
            </>
          )}

          <div className="flex gap-2">
            {!isLangBotModels && (
              <Button
                className="flex-1"
                size="sm"
                onClick={handleSave}
                disabled={isSubmitting || isTesting}
              >
                {isSubmitting ? t('common.saving') : t('common.save')}
              </Button>
            )}
            <Button
              className={isLangBotModels ? 'w-full' : 'flex-1'}
              size="sm"
              variant="outline"
              onClick={handleTest}
              disabled={isSubmitting || isTesting}
            >
              {isTesting ? (
                t('common.loading')
              ) : testResult?.success ? (
                <>
                  <Check className="h-4 w-4 mr-1 text-green-500" />
                  {(testResult.duration / 1000).toFixed(1)}s
                </>
              ) : (
                t('common.test')
              )}
            </Button>
          </div>
        </div>
      </PopoverContent>
    </Popover>
  );
}

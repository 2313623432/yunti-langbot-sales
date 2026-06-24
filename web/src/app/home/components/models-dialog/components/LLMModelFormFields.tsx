import { Eye, Wrench, Radio } from 'lucide-react';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Checkbox } from '@/components/ui/checkbox';
import { useTranslation } from 'react-i18next';
import { LLMModelFormValues } from '../modelFormUtils';
import ExtraArgsEditor from './ExtraArgsEditor';

interface LLMModelFormFieldsProps {
  values: LLMModelFormValues;
  onChange: (values: LLMModelFormValues) => void;
  disabled?: boolean;
  showCustomExtraArgs?: boolean;
}

export default function LLMModelFormFields({
  values,
  onChange,
  disabled = false,
  showCustomExtraArgs = true,
}: LLMModelFormFieldsProps) {
  const { t } = useTranslation();

  const toggleAbility = (ability: string, checked: boolean) => {
    const nextAbilities = checked
      ? [...values.abilities, ability]
      : values.abilities.filter((item) => item !== ability);
    onChange({ ...values, abilities: nextAbilities });
  };

  return (
    <div className="space-y-3">
      <div className="space-y-2">
        <Label>{t('models.modelId')}</Label>
        <Input
          placeholder={t('models.modelIdPlaceholder')}
          value={values.modelId}
          disabled={disabled}
          onChange={(e) => onChange({ ...values, modelId: e.target.value })}
        />
      </div>

      <div className="space-y-2">
        <Label>{t('models.displayName')}</Label>
        <Input
          placeholder={t('models.displayNamePlaceholder')}
          value={values.displayName}
          disabled={disabled}
          onChange={(e) => onChange({ ...values, displayName: e.target.value })}
        />
      </div>

      <div className="space-y-2">
        <Label>{t('models.abilities')}</Label>
        <div className="flex flex-wrap gap-4">
          <div className="flex items-center gap-2">
            <Checkbox
              id="llm-form-vision"
              checked={values.abilities.includes('vision')}
              disabled={disabled}
              onCheckedChange={(checked) =>
                toggleAbility('vision', checked as boolean)
              }
            />
            <Label htmlFor="llm-form-vision" className="text-sm">
              <Eye className="mr-1 inline h-3 w-3" />
              {t('models.visionAbility')}
            </Label>
          </div>
          <div className="flex items-center gap-2">
            <Checkbox
              id="llm-form-tools"
              checked={values.abilities.includes('func_call')}
              disabled={disabled}
              onCheckedChange={(checked) =>
                toggleAbility('func_call', checked as boolean)
              }
            />
            <Label htmlFor="llm-form-tools" className="text-sm">
              <Wrench className="mr-1 inline h-3 w-3" />
              {t('models.functionCallAbility')}
            </Label>
          </div>
          <div className="flex items-center gap-2">
            <Checkbox
              id="llm-form-streaming"
              checked={values.streaming}
              disabled={disabled}
              onCheckedChange={(checked) =>
                onChange({ ...values, streaming: checked as boolean })
              }
            />
            <Label htmlFor="llm-form-streaming" className="text-sm">
              <Radio className="mr-1 inline h-3 w-3" />
              {t('models.streamingAbility')}
            </Label>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div className="space-y-2">
          <Label>{t('models.contextWindow')}</Label>
          <Input
            type="number"
            min={0}
            placeholder="128000"
            value={values.contextWindow}
            disabled={disabled}
            onChange={(e) =>
              onChange({ ...values, contextWindow: e.target.value })
            }
          />
        </div>
        <div className="space-y-2">
          <Label>{t('models.maxOutputTokens')}</Label>
          <Input
            type="number"
            min={0}
            placeholder="16384"
            value={values.maxOutputTokens}
            disabled={disabled}
            onChange={(e) =>
              onChange({ ...values, maxOutputTokens: e.target.value })
            }
          />
        </div>
      </div>

      {showCustomExtraArgs && (
        <ExtraArgsEditor
          args={values.customExtraArgs}
          onChange={(customExtraArgs) =>
            onChange({ ...values, customExtraArgs })
          }
          disabled={disabled}
          modelType="llm"
        />
      )}
    </div>
  );
}

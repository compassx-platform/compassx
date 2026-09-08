import { useState } from 'react';
import type { VisualizationConfigProps } from '../types';
import SectionRow from '../common/SectionRow';
import FieldPill from '../common/FieldPill';
import Select from '../common/Select';
import FieldRow from '../common/FieldRow';
import AxisConfigPopover from '../common/AxisConfigPopover';
import NumberFormatSection from '../common/NumberFormatSection';
import ConditionalFormattingSection from '../common/ConditionalFormattingSection';

export default function CounterConfigSection({
  config,
  fieldOptions,
  getFieldType,
  patch,
  patchAxis,
}: VisualizationConfigProps) {
  const [openPopover, setOpenPopover] = useState<'value' | 'compare' | null>(null);
  const [showValuePicker, setShowValuePicker] = useState(false);
  const [showComparePicker, setShowComparePicker] = useState(false);

  const valueField = config.yFields?.[0] || '';
  const comparisonField = config.comparisonField || '';
  
  const mainTransform = config.yAxis?.transform;
  const activeMainTransform = mainTransform && mainTransform.toUpperCase() !== 'NONE' ? mainTransform.toUpperCase() : null;
  const mainPillLabel = activeMainTransform ? `${activeMainTransform}(${valueField})` : valueField;

  const compTransform = config.comparisonTransform || config.yAxis?.transform;
  const activeCompTransform = compTransform && compTransform.toUpperCase() !== 'NONE' ? compTransform.toUpperCase() : null;
  const compPillLabel = activeCompTransform ? `${activeCompTransform}(${comparisonField})` : comparisonField;

  return (
    <>
      {/* Primary Value / Metric Section */}
      <div style={{ position: 'relative' }}>
        <SectionRow
          title="Metric Value"
          onPlus={!valueField ? () => setShowValuePicker(!showValuePicker) : undefined}
        >
          {valueField ? (
            <FieldPill
              name={valueField}
              type={getFieldType(valueField)}
              displayName={mainPillLabel}
              onClick={() => setOpenPopover(openPopover === 'value' ? null : 'value')}
              onRemove={() => {
                patch({ yFields: [] });
                if (openPopover === 'value') setOpenPopover(null);
                setShowValuePicker(false);
              }}
            />
          ) : showValuePicker ? (
            <div style={{ marginTop: 4 }}>
              <Select
                value=""
                onChange={(v) => {
                  if (v) {
                    patch({ yFields: [v] });
                    setShowValuePicker(false);
                  }
                }}
                options={fieldOptions}
                placeholder="Select metric column..."
              />
            </div>
          ) : null}
        </SectionRow>

        {openPopover === 'value' && valueField && (
          <AxisConfigPopover
            fieldName={valueField}
            fieldType={getFieldType(valueField)}
            axisConfig={config.yAxis}
            fieldOptions={fieldOptions}
            onFieldChange={(newField) => patch({ yFields: [newField] })}
            hideDisplayName={true}
            hideScaleType={true}
            hideErrorBar={true}
            onUpdate={(updated) => patchAxis('yAxis', updated)}
            onClose={() => setOpenPopover(null)}
          />
        )}
      </div>

      {/* Comparison Field (Optional) for Delta / % Change */}
      <div style={{ position: 'relative' }}>
        <SectionRow
          title="Comparison Field (Optional)"
          tooltip="Computes delta value & percentage change against this field or second row"
          onPlus={!comparisonField ? () => setShowComparePicker(!showComparePicker) : undefined}
        >
          {comparisonField ? (
            <FieldPill
              name={comparisonField}
              type={getFieldType(comparisonField)}
              displayName={compPillLabel}
              onClick={() => setOpenPopover(openPopover === 'compare' ? null : 'compare')}
              onRemove={() => {
                patch({ comparisonField: undefined, comparisonTransform: undefined });
                if (openPopover === 'compare') setOpenPopover(null);
                setShowComparePicker(false);
              }}
            />
          ) : showComparePicker ? (
            <div style={{ marginTop: 4 }}>
              <Select
                value=""
                onChange={(v) => {
                  if (v) {
                    patch({ comparisonField: v });
                    setShowComparePicker(false);
                  }
                }}
                options={fieldOptions.filter((o) => o.value !== valueField)}
                placeholder="Select comparison column..."
              />
            </div>
          ) : null}
        </SectionRow>

        {openPopover === 'compare' && comparisonField && (
          <AxisConfigPopover
            fieldName={comparisonField}
            fieldType={getFieldType(comparisonField)}
            axisConfig={{ transform: config.comparisonTransform ?? config.yAxis?.transform ?? 'NONE' }}
            fieldOptions={fieldOptions.filter((o) => o.value !== valueField)}
            onFieldChange={(newField) => patch({ comparisonField: newField || undefined })}
            hideDisplayName={true}
            hideScaleType={true}
            hideErrorBar={true}
            onUpdate={(updated) => patch({ comparisonTransform: updated.transform })}
            onClose={() => setOpenPopover(null)}
          />
        )}
      </div>

      {/* Metric Label / Subtitle */}
      <div style={{ padding: '12px 14px', borderBottom: '1px solid #f0f0f0' }}>
        <FieldRow label="Sublabel / Caption">
          <input
            type="text"
            value={config.xField ?? ''}
            onChange={(e) => patch({ xField: e.target.value || undefined })}
            placeholder="e.g. Total Revenue (or custom subtitle)"
            style={{
              width: '100%',
              padding: '5px 8px',
              fontSize: '0.77rem',
              border: '1px solid var(--color-border)',
              borderRadius: 4,
              background: 'var(--color-surface)',
              color: 'var(--color-text)',
            }}
          />
        </FieldRow>

        <label
          style={{
            fontSize: '0.74rem',
            display: 'flex',
            alignItems: 'center',
            gap: 6,
            cursor: 'pointer',
            marginTop: 6,
          }}
        >
          <input
            type="checkbox"
            checked={config.showSparkline ?? true}
            onChange={(e) => patch({ showSparkline: e.target.checked })}
            style={{ accentColor: '#0052cc' }}
          />
          Show delta trend indicator
        </label>
      </div>

      {/* Number Formatting Section */}
      <NumberFormatSection
        numberFormat={config.numberFormat}
        onChange={(updated) => patch({ numberFormat: updated })}
        collapsible={true}
        defaultOpen={true}
      />

      {/* Conditional Formatting Section */}
      <ConditionalFormattingSection
        rules={config.conditionalFormatting}
        onChange={(updated) => patch({ conditionalFormatting: updated })}
        collapsible={true}
        defaultOpen={false}
      />
    </>
  );
}

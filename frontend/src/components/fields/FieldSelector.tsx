import React from 'react';
import { FieldFilter, Hierarchy, FIELD_COLORS } from '../../api/asset';

export interface FieldSelectorProps {
  value: FieldFilter;
  onChange: (f: FieldFilter) => void;
  hierarchy: Hierarchy | null;
  /** 'overlay' = see-through styling for use on top of the map. */
  variant?: 'default' | 'overlay';
}

export const FieldSelector: React.FC<FieldSelectorProps> = ({
  value,
  onChange,
  hierarchy,
  variant = 'default',
}) => {
  const isAllSelected = value === 'ALL';

  return (
    <div
      className={`inline-flex items-center gap-1 p-1 rounded-lg text-xs font-sans flex-wrap ${
        variant === 'overlay' ? 'text-white' : 'bg-[#0d1117] border border-border'
      }`}
    >
      {/* 'All fields' button */}
      <button
        type="button"
        onClick={() => onChange('ALL')}
        className={`px-2.5 py-1 rounded transition-colors flex items-center gap-1.5 focus:outline-none ${
          isAllSelected
            ? 'bg-surface text-white font-semibold border border-border'
            : 'text-textMuted hover:text-textMain hover:bg-surface/50 border border-transparent'
        }`}
      >
        <span>All fields</span>
        {hierarchy && hierarchy.n_wells !== undefined && (
          <span className="text-textMuted font-mono text-[10px]">({hierarchy.n_wells})</span>
        )}
      </button>

      {/* Loading state when hierarchy is null */}
      {!hierarchy && (
        <span className="text-xs text-textMuted px-2 font-mono">loading fields…</span>
      )}

      {/* Field buttons from hierarchy */}
      {hierarchy &&
        hierarchy.fields.map((fieldNode) => {
          const isSelected = value === fieldNode.field;
          const color = FIELD_COLORS[fieldNode.field] || '#8b949e';
          const counts = fieldNode.health_counts;
          const tooltip = counts
            ? `PRODUCING_OK: ${counts.PRODUCING_OK ?? 0} · AT_RISK: ${counts.AT_RISK ?? 0} · UNDERPERFORMING: ${counts.UNDERPERFORMING ?? 0} · NOT_PRODUCING: ${counts.NOT_PRODUCING ?? 0}`
            : undefined;

          return (
            <button
              key={fieldNode.field}
              type="button"
              title={tooltip}
              onClick={() => onChange(fieldNode.field)}
              className={`px-2.5 py-1 rounded transition-colors flex items-center gap-1.5 focus:outline-none ${
                isSelected
                  ? 'bg-surface text-white font-semibold border border-border'
                  : 'text-textMuted hover:text-textMain hover:bg-surface/50 border border-transparent'
              }`}
            >
              <span
                className="w-2 h-2 rounded-full inline-block shrink-0"
                style={{ backgroundColor: color }}
              />
              <span>{fieldNode.field}</span>
              <span className="text-textMuted font-mono text-[10px]">({fieldNode.n_wells})</span>
            </button>
          );
        })}
    </div>
  );
};

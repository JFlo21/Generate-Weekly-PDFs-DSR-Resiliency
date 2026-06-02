import { X } from 'lucide-react';
import { cn } from '../../lib/utils';
import { getVariantLabel } from '../../lib/variantLabels';

interface VariantFilterBarProps {
  options: string[];
  selected: string[];
  onChange: (next: string[]) => void;
}

export function VariantFilterBar({
  options,
  selected,
  onChange,
}: VariantFilterBarProps) {
  const toggle = (variant: string) => {
    if (selected.includes(variant)) {
      onChange(selected.filter((v) => v !== variant));
    } else {
      onChange([...selected, variant]);
    }
  };

  const remove = (variant: string) => {
    onChange(selected.filter((v) => v !== variant));
  };

  if (options.length === 0) return null;

  return (
    <div className="flex flex-wrap items-center gap-2">
      {/* Option toggles */}
      {options.map((option) => {
        const isSelected = selected.includes(option);
        return (
          <button
            key={option}
            onClick={() => toggle(option)}
            className={cn(
              'inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border transition-colors',
              isSelected
                ? 'bg-blue-100 text-blue-700 border-blue-200'
                : 'bg-slate-100 text-slate-600 border-slate-200 hover:bg-slate-200'
            )}
          >
            {getVariantLabel(option)}
          </button>
        );
      })}

      {/* Clearable chips for selected variants */}
      {selected.length > 0 && (
        <>
          <span className="text-slate-300">|</span>
          {selected.map((variant) => (
            <span
              key={`chip-${variant}`}
              className="inline-flex items-center gap-0.5 px-2 py-0.5 rounded-full text-xs font-medium border bg-blue-100 text-blue-700 border-blue-200"
            >
              {getVariantLabel(variant)}
              <button
                onClick={() => remove(variant)}
                aria-label={`Remove ${getVariantLabel(variant)} filter`}
                className="ml-0.5 hover:text-blue-900 transition-colors"
              >
                <X size={10} />
              </button>
            </span>
          ))}
          <button
            onClick={() => onChange([])}
            className="text-xs text-slate-500 hover:text-slate-700 transition-colors underline"
          >
            Clear
          </button>
        </>
      )}
    </div>
  );
}

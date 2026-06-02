import { useRef } from 'react';
import { Search, X } from 'lucide-react';

interface ArtifactSearchBarProps {
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
}

export function ArtifactSearchBar({
  value,
  onChange,
  placeholder = 'Search by WR # or week-ending (e.g. 90001 or 05/26/25)',
}: ArtifactSearchBarProps) {
  const inputRef = useRef<HTMLInputElement>(null);

  return (
    <div className="relative">
      <Search
        size={16}
        className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none"
      />
      <input
        ref={inputRef}
        type="search"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="w-full pl-9 pr-9 py-2.5 rounded-xl border border-slate-200 bg-white text-sm text-slate-800 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-brand-red/30 focus:border-brand-red/40 transition-all"
      />
      {value && (
        <button
          onClick={() => {
            onChange('');
            inputRef.current?.focus();
          }}
          className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 transition-colors"
          aria-label="Clear search"
        >
          <X size={14} />
        </button>
      )}
    </div>
  );
}

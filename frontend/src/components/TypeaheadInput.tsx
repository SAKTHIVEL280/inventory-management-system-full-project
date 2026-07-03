import { useEffect, useMemo, useRef, useState } from 'react';

/**
 * Shared searchable type-ahead input with full keyboard support:
 *  - ArrowDown / ArrowUp: move the highlighted option
 *  - Enter: select the highlighted option
 *  - Esc: close the dropdown
 *  - Typing: filters the options
 * Free-text is allowed (the raw value is emitted on change), matching the prior
 * per-page behaviour, so existing/legacy values still work.
 */
export type TypeaheadInputProps = {
  id?: string;
  value: string;
  options: string[];
  placeholder?: string;
  onChange: (nextValue: string) => void;
  className?: string;
  showAllWhenFocused?: boolean;
  autoComplete?: string;
  disabled?: boolean;
  limit?: number;
};

export const TypeaheadInput = ({
  id,
  value,
  options,
  placeholder,
  onChange,
  className = 'hms-input',
  showAllWhenFocused = false,
  autoComplete = 'off',
  disabled = false,
  limit = 12,
}: TypeaheadInputProps) => {
  const [isOpen, setIsOpen] = useState(false);
  const [hasTypedSinceFocus, setHasTypedSinceFocus] = useState(false);
  const [highlight, setHighlight] = useState(0);
  const listRef = useRef<HTMLDivElement>(null);

  const filteredOptions = useMemo(() => {
    const needle = showAllWhenFocused && !hasTypedSinceFocus ? '' : value.trim().toLowerCase();
    const base = [...new Set(options.map((o) => o.trim()).filter((o) => o.length > 0))];
    if (!needle) return base.slice(0, limit);
    const starts = base.filter((o) => o.toLowerCase().startsWith(needle));
    const includes = base.filter((o) => !o.toLowerCase().startsWith(needle) && o.toLowerCase().includes(needle));
    return [...new Set([...starts, ...includes])].slice(0, limit);
  }, [hasTypedSinceFocus, options, showAllWhenFocused, value, limit]);

  // Keep the highlight in range whenever the option set changes.
  useEffect(() => {
    setHighlight((h) => (filteredOptions.length === 0 ? 0 : Math.min(h, filteredOptions.length - 1)));
  }, [filteredOptions]);

  const select = (option: string) => {
    onChange(option);
    setHasTypedSinceFocus(false);
    setIsOpen(false);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (disabled) return;
    if ((e.key === 'ArrowDown' || e.key === 'ArrowUp') && !isOpen) {
      setIsOpen(true);
      return;
    }
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setHighlight((h) => (filteredOptions.length ? (h + 1) % filteredOptions.length : 0));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setHighlight((h) => (filteredOptions.length ? (h - 1 + filteredOptions.length) % filteredOptions.length : 0));
    } else if (e.key === 'Enter') {
      if (isOpen && filteredOptions[highlight] !== undefined) {
        e.preventDefault();
        select(filteredOptions[highlight]);
      }
    } else if (e.key === 'Escape') {
      setIsOpen(false);
    }
  };

  // Scroll the highlighted option into view.
  useEffect(() => {
    if (!isOpen || !listRef.current) return;
    const el = listRef.current.children[highlight] as HTMLElement | undefined;
    el?.scrollIntoView({ block: 'nearest' });
  }, [highlight, isOpen]);

  return (
    <div className="relative">
      <input
        id={id}
        className={className}
        value={value}
        placeholder={placeholder}
        autoComplete={autoComplete}
        disabled={disabled}
        role="combobox"
        aria-expanded={isOpen}
        aria-autocomplete="list"
        onFocus={() => { setHasTypedSinceFocus(false); setHighlight(0); setIsOpen(true); }}
        onBlur={() => { window.setTimeout(() => setIsOpen(false), 120); setHasTypedSinceFocus(false); }}
        onKeyDown={handleKeyDown}
        onChange={(event) => { setHasTypedSinceFocus(true); onChange(event.target.value); setHighlight(0); setIsOpen(true); }}
      />
      {isOpen && !disabled && filteredOptions.length > 0 && (
        <div ref={listRef} className="absolute z-30 mt-1 max-h-52 w-full overflow-auto rounded-lg border border-neutral-200 bg-white shadow-lg">
          {filteredOptions.map((option, idx) => (
            <button
              key={`${id ?? 'ta'}-${option}`}
              type="button"
              className={`block w-full px-3 py-2 text-left text-sm text-neutral-700 ${idx === highlight ? 'bg-neutral-100' : 'hover:bg-neutral-100'}`}
              onMouseEnter={() => setHighlight(idx)}
              onMouseDown={(event) => { event.preventDefault(); select(option); }}
            >
              {option}
            </button>
          ))}
        </div>
      )}
    </div>
  );
};

export default TypeaheadInput;

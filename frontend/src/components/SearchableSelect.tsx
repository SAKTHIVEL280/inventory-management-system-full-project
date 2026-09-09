import { useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import { createPortal } from 'react-dom';

/**
 * Reusable "type / search -> view matching results -> choose" selector for
 * lookup fields that map a display label to an id (customer, supplier, product,
 * stockist, sales manager, ...). Unlike a native <select> it lets the user type
 * to filter; unlike TypeaheadInput it emits the option's `value` (id), not the
 * raw text.
 *
 * Filtering matches the option label plus any `keywords` (e.g. customer code,
 * phone, GSTIN) so users can search by "relevant details", not just the name.
 * Keyboard: ArrowUp/Down to move, Enter to choose, Esc to close.
 */
export type SearchableOption = {
  value: string;
  label: string;
  /** Secondary line shown under the label in the dropdown (e.g. code · phone). */
  sublabel?: string;
  /** Extra text included in the search (not displayed), e.g. phone, GSTIN. */
  keywords?: string;
};

type Props = {
  id?: string;
  value: string;
  options: SearchableOption[];
  onChange: (value: string) => void;
  placeholder?: string;
  className?: string;
  disabled?: boolean;
  /** Text for the clear/none entry; when set, a "clear" row is offered. */
  allowClear?: boolean;
  emptyMessage?: string;
  /** Max options rendered at once (default 50). */
  limit?: number;
};

export const SearchableSelect = ({
  id,
  value,
  options,
  onChange,
  placeholder = 'Search…',
  className = 'hms-input',
  disabled = false,
  allowClear = false,
  emptyMessage = 'No matches found',
  limit = 50,
}: Props) => {
  const [isOpen, setIsOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [editing, setEditing] = useState(false);
  const [highlight, setHighlight] = useState(0);
  const listRef = useRef<HTMLDivElement>(null);
  const wrapRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  // The dropdown is rendered in a portal with fixed positioning so it is never
  // clipped by an ancestor with `overflow` (e.g. a horizontally scrollable line-item
  // grid). We track the input's viewport rect and flip the list above when there is
  // not enough room below.
  const [menuPos, setMenuPos] = useState<{ left: number; top: number; width: number; maxHeight: number; placement: 'below' | 'above' }>();

  const recomputePosition = () => {
    const el = inputRef.current;
    if (!el) return;
    const r = el.getBoundingClientRect();
    const GAP = 4;
    const DESIRED = 256; // max-h-64
    const spaceBelow = window.innerHeight - r.bottom - GAP;
    const spaceAbove = r.top - GAP;
    const placeAbove = spaceBelow < Math.min(DESIRED, 160) && spaceAbove > spaceBelow;
    const maxHeight = Math.max(120, Math.min(DESIRED, placeAbove ? spaceAbove : spaceBelow));
    setMenuPos({
      left: r.left,
      top: placeAbove ? r.top - GAP : r.bottom + GAP,
      width: r.width,
      maxHeight,
      placement: placeAbove ? 'above' : 'below',
    });
  };

  // Keep the menu aligned to the input while open (on scroll/resize of any ancestor).
  useLayoutEffect(() => {
    if (!isOpen) return;
    recomputePosition();
    const onChange = () => recomputePosition();
    window.addEventListener('scroll', onChange, true); // capture: catches ancestor scrolls
    window.addEventListener('resize', onChange);
    return () => {
      window.removeEventListener('scroll', onChange, true);
      window.removeEventListener('resize', onChange);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isOpen]);

  const selected = useMemo(() => options.find((o) => o.value === value) ?? null, [options, value]);

  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase();
    if (!needle) return options.slice(0, limit);
    const scored = options.filter((o) => {
      const hay = `${o.label} ${o.sublabel ?? ''} ${o.keywords ?? ''}`.toLowerCase();
      return hay.includes(needle);
    });
    // Prioritise label prefix matches for a more intuitive order.
    scored.sort((a, b) => {
      const ap = a.label.toLowerCase().startsWith(needle) ? 0 : 1;
      const bp = b.label.toLowerCase().startsWith(needle) ? 0 : 1;
      return ap - bp;
    });
    return scored.slice(0, limit);
  }, [options, query, limit]);

  useEffect(() => {
    setHighlight((h) => (filtered.length === 0 ? 0 : Math.min(h, filtered.length - 1)));
  }, [filtered]);

  useEffect(() => {
    if (!isOpen || !listRef.current) return;
    const el = listRef.current.children[highlight] as HTMLElement | undefined;
    el?.scrollIntoView({ block: 'nearest' });
  }, [highlight, isOpen]);

  const choose = (option: SearchableOption | null) => {
    onChange(option ? option.value : '');
    setEditing(false);
    setQuery('');
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
      setHighlight((h) => (filtered.length ? (h + 1) % filtered.length : 0));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setHighlight((h) => (filtered.length ? (h - 1 + filtered.length) % filtered.length : 0));
    } else if (e.key === 'Enter') {
      if (isOpen && filtered[highlight]) {
        e.preventDefault();
        choose(filtered[highlight]);
      }
    } else if (e.key === 'Escape') {
      setIsOpen(false);
      setEditing(false);
      setQuery('');
    }
  };

  const displayValue = editing ? query : selected?.label ?? '';

  return (
    <div className="relative" ref={wrapRef}>
      <input
        id={id}
        ref={inputRef}
        className={className}
        value={displayValue}
        placeholder={selected ? selected.label : placeholder}
        autoComplete="off"
        disabled={disabled}
        role="combobox"
        aria-expanded={isOpen}
        aria-autocomplete="list"
        onFocus={() => { setEditing(true); setQuery(''); setHighlight(0); setIsOpen(true); }}
        onBlur={() => { window.setTimeout(() => { setIsOpen(false); setEditing(false); setQuery(''); }, 120); }}
        onKeyDown={handleKeyDown}
        onChange={(e) => { setEditing(true); setQuery(e.target.value); setHighlight(0); setIsOpen(true); }}
      />
      {isOpen && !disabled && menuPos && createPortal(
        <div
          ref={listRef}
          className="fixed z-[1000] overflow-auto rounded-lg border border-neutral-200 bg-white shadow-lg"
          style={{ left: menuPos.left, top: menuPos.placement === 'above' ? undefined : menuPos.top, bottom: menuPos.placement === 'above' ? window.innerHeight - menuPos.top : undefined, width: menuPos.width, maxHeight: menuPos.maxHeight }}
        >
          {allowClear && (
            <button
              type="button"
              className="block w-full border-b border-neutral-100 px-3 py-2 text-left text-sm italic text-neutral-400 hover:bg-neutral-100"
              onMouseDown={(e) => { e.preventDefault(); choose(null); }}
            >
              Clear selection
            </button>
          )}
          {filtered.length === 0 ? (
            <div className="px-3 py-2 text-sm text-neutral-400">{emptyMessage}</div>
          ) : (
            filtered.map((option, idx) => (
              <button
                key={option.value}
                type="button"
                className={`block w-full px-3 py-2 text-left ${idx === highlight ? 'bg-neutral-100' : 'hover:bg-neutral-100'}`}
                onMouseEnter={() => setHighlight(idx)}
                onMouseDown={(e) => { e.preventDefault(); choose(option); }}
              >
                <span className="block truncate text-sm text-neutral-800">{option.label}</span>
                {option.sublabel && <span className="block truncate text-xs text-neutral-400">{option.sublabel}</span>}
              </button>
            ))
          )}
        </div>,
        document.body,
      )}
    </div>
  );
};

export default SearchableSelect;

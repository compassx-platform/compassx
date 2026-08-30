/**
 * Searchable picker for the principal a grant is made to.
 *
 * A grant addresses a principal by id, but an administrator thinks in names, so
 * the list is searched by name and email and the id is only ever shown as a
 * fallback for a principal whose name could not be resolved.
 */
import { useMemo, useState } from 'react';
import { Search, Users, User as UserIcon } from 'lucide-react';

import type { PrincipalOption } from '../governanceTypes';

interface Props {
  options: PrincipalOption[];
  value: PrincipalOption | null;
  onChange: (option: PrincipalOption) => void;
  isLoading?: boolean;
  /** Principals already holding a grant here — shown, but marked. */
  existingIds?: ReadonlySet<string>;
}

export default function PrincipalPicker({
  options,
  value,
  onChange,
  isLoading = false,
  existingIds,
}: Props) {
  const [search, setSearch] = useState('');

  const matches = useMemo(() => {
    const term = search.trim().toLowerCase();
    if (!term) return options;
    return options.filter(
      (option) =>
        option.label.toLowerCase().includes(term) ||
        option.detail?.toLowerCase().includes(term) ||
        option.id.toLowerCase().includes(term),
    );
  }, [options, search]);

  return (
    <div className="gov-principal-picker">
      <div className="gov-search-field">
        <Search size={14} aria-hidden="true" />
        <input
          type="text"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          placeholder="Search users and groups…"
          aria-label="Search users and groups"
        />
      </div>

      <div className="gov-principal-list" role="listbox" aria-label="Principals">
        {isLoading && <div className="uc-empty-inline">Loading principals…</div>}

        {!isLoading && matches.length === 0 && (
          <div className="uc-empty-inline">
            {search.trim() ? 'No principal matches that search.' : 'No principals available.'}
          </div>
        )}

        {matches.map((option) => {
          const selected = value?.id === option.id;
          const alreadyGranted = existingIds?.has(option.id) ?? false;
          return (
            <button
              key={`${option.type}:${option.id}`}
              type="button"
              role="option"
              aria-selected={selected}
              className={`gov-principal-row${selected ? ' is-selected' : ''}`}
              onClick={() => onChange(option)}
            >
              <span className="gov-principal-icon" aria-hidden="true">
                {option.type === 'group' ? <Users size={14} /> : <UserIcon size={14} />}
              </span>
              <span className="gov-principal-text">
                <span className="gov-principal-name">{option.label}</span>
                {option.detail && <span className="gov-principal-detail">{option.detail}</span>}
              </span>
              {alreadyGranted && <span className="uc-chip gov-chip-muted">Has access</span>}
            </button>
          );
        })}
      </div>
    </div>
  );
}

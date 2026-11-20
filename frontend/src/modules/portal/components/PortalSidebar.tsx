import { useEffect, useRef, useState, type MouseEvent as ReactMouseEvent } from 'react';
import { NavLink } from 'react-router-dom';
import { MoreHorizontal, Settings } from 'lucide-react';
import { CURATED_TECH_DATA_ICONS } from '@/components/icons/TechDataIcons';
import { EAM_NAV_ICONS, resolveScreenIcon, selectedIconName } from '../portalIcons';
import { useScopedPath } from '@/lib/appNavigation';
import { useToast } from '@/lib/toast';
import {
  PortalItem,
  PortalSection,
  usePortalAvailableItems,
  useUpdatePortalConfig,
} from '../hooks/usePortalConfig';
import { portalItemTo } from '../moduleFrame';
import './portal-sidebar.css';

type MenuTargetInput =
  | { kind: 'group'; id: string }
  | { kind: 'item'; id: string; sectionId: string };

type MenuTarget = MenuTargetInput & { top: number; left: number };

type AddKind = 'app' | 'dashboard' | 'link';

interface PortalSidebarProps {
  sections?: PortalSection[];
  canEdit: boolean;
  selectedItemId?: string | null;
}

function IconChoices({ value, onChange }: { value: string; onChange: (name: string) => void }) {
  const choices = [
    ...EAM_NAV_ICONS.map((icon) => ({ name: icon.name, label: icon.label, component: icon.component })),
    ...CURATED_TECH_DATA_ICONS.map((icon) => ({ name: icon.name, label: icon.description, component: icon.component })),
  ];
  return (
    <div>
      <p className="portal-nav-pop-label">Icon</p>
      <div className="portal-nav-icon-grid" role="listbox" aria-label="Icon">
      {choices.map((icon) => {
        const Glyph = icon.component;
        return (
          <button
            key={icon.name}
            type="button"
            role="option"
            aria-selected={value === icon.name}
            aria-label={icon.label}
            title={icon.label}
            className={value === icon.name ? 'is-on' : ''}
            onClick={() => onChange(icon.name)}
          >
            <Glyph size={16} />
          </button>
        );
      })}
      </div>
    </div>
  );
}

function fitPopup(top: number) {
  return Math.max(8, Math.min(top, window.innerHeight - 360));
}

function placeMenu(target: HTMLElement) {
  const rect = target.getBoundingClientRect();
  const top = rect.bottom + 4 + 180 > window.innerHeight ? Math.max(8, rect.top - 180) : rect.bottom + 4;
  const left = Math.min(rect.left, window.innerWidth - 180);
  return { top, left };
}

export function PortalSidebar({ sections, canEdit, selectedItemId }: PortalSidebarProps) {
  const toast = useToast();
  const appPath = useScopedPath();
  const updateMutation = useUpdatePortalConfig();
  const { data: available } = usePortalAvailableItems();
  const [local, setLocal] = useState<PortalSection[]>(sections ?? []);
  const [menu, setMenu] = useState<MenuTarget | null>(null);
  const [editing, setEditing] = useState<{ sectionId: string; itemId: string; top: number; left: number } | null>(null);
  const [renamingGroup, setRenamingGroup] = useState<{ id: string; top: number; left: number } | null>(null);
  const [groupTitle, setGroupTitle] = useState('');
  const [editTitle, setEditTitle] = useState('');
  const [editPath, setEditPath] = useState('');
  const [editUrl, setEditUrl] = useState('');
  const [editIcon, setEditIcon] = useState('');
  const [chosenIcon, setChosenIcon] = useState('');
  const [addKind, setAddKind] = useState<AddKind>('app');
  const [addFor, setAddFor] = useState<{ sectionId: string; top: number; left: number } | null>(null);
  const [search, setSearch] = useState('');
  const [draftTitle, setDraftTitle] = useState('');
  const [draftPath, setDraftPath] = useState('');
  const [draft, setDraft] = useState<{
    type: 'app' | 'dashboard';
    targetId: string;
    appType?: string | null;
    status?: string | null;
    url?: string | null;
  } | null>(null);
  const [linkTitle, setLinkTitle] = useState('');
  const [linkUrl, setLinkUrl] = useState('');
  const menuRef = useRef<HTMLDivElement | null>(null);
  const addRef = useRef<HTMLDivElement | null>(null);
  const editRef = useRef<HTMLFormElement | null>(null);

  useEffect(() => {
    setLocal(sections ?? []);
  }, [sections]);

  useEffect(() => {
    function onDown(event: MouseEvent) {
      const target = event.target as Node;
      if (menuRef.current?.contains(target) || addRef.current?.contains(target) || editRef.current?.contains(target)) return;
      setMenu(null);
      setAddFor(null);
      setEditing(null);
      setRenamingGroup(null);
    }
    document.addEventListener('mousedown', onDown);
    return () => document.removeEventListener('mousedown', onDown);
  }, []);

  async function commit(next: PortalSection[]) {
    const previous = local;
    setLocal(next);
    setMenu(null);
    try {
      await updateMutation.mutateAsync(next);
    } catch (err: any) {
      setLocal(previous);
      toast.error(err?.response?.data?.detail || 'Could not update the sidebar.');
    }
  }

  function openMenu(event: ReactMouseEvent<HTMLButtonElement>, next: MenuTargetInput) {
    event.preventDefault();
    event.stopPropagation();
    const spot = placeMenu(event.currentTarget);
    setAddFor(null);
    setEditing(null);
    setRenamingGroup(null);
    setMenu({ ...next, ...spot } as MenuTarget);
  }

  function updateItem(sectionId: string, itemId: string, patch: Partial<PortalItem>) {
    return local.map((section) => {
      if (section.id !== sectionId) return section;
      return {
        ...section,
        items: section.items.map((item) => (item.id === itemId ? { ...item, ...patch } : item)),
      };
    });
  }

  function moveSection(index: number, direction: 'up' | 'down') {
    const target = direction === 'up' ? index - 1 : index + 1;
    if (target < 0 || target >= local.length) return;
    const copy = [...local];
    const current = copy[index];
    copy[index] = copy[target];
    copy[target] = current;
    void commit(copy);
  }

  function moveItem(sectionId: string, index: number, direction: 'up' | 'down') {
    const next = local.map((section) => {
      if (section.id !== sectionId) return section;
      const target = direction === 'up' ? index - 1 : index + 1;
      if (target < 0 || target >= section.items.length) return section;
      const copy = [...section.items];
      const current = copy[index];
      copy[index] = copy[target];
      copy[target] = current;
      return { ...section, items: copy.map((item, order) => ({ ...item, order })) };
    });
    void commit(next);
  }

  function beginEdit(sectionId: string, item: PortalItem) {
    if (!menu) return;
    setEditing({ sectionId, itemId: item.id, top: menu.top, left: menu.left });
    setEditTitle(item.title);
    setEditPath(item.path || '');
    setEditUrl(item.url || '');
    setEditIcon(selectedIconName(item));
    setMenu(null);
    setAddFor(null);
    setRenamingGroup(null);
  }

  function saveEdit(sectionId: string, item: PortalItem) {
    if (!editTitle.trim()) {
      toast.error('A screen name is required');
      return;
    }
    void commit(
      updateItem(sectionId, item.id, {
        title: editTitle.trim(),
        path: item.type === 'app' ? editPath.trim() || undefined : item.path,
        url: item.type === 'external_link' ? editUrl.trim() : item.url,
        icon: editIcon || item.icon,
      }),
    );
    setEditing(null);
  }

  function beginAdd(sectionId: string, anchor: HTMLElement) {
    const spot = placeMenu(anchor);
    setMenu(null);
    setDraft(null);
    setSearch('');
    setLinkTitle('');
    setLinkUrl('');
    setChosenIcon('');
    setAddKind('app');
    setAddFor({ sectionId, ...spot });
  }

  function addItem(sectionId: string, item: PortalItem) {
    void commit(
      local.map((section) =>
        section.id === sectionId ? { ...section, items: [...section.items, { ...item, order: section.items.length }] } : section,
      ),
    );
    setAddFor(null);
    setDraft(null);
  }

  function confirmDraft(sectionId: string) {
    if (!draft || !draftTitle.trim()) {
      toast.error('A screen name is required');
      return;
    }
    addItem(sectionId, {
      id: `item_${draft.type}_${draft.targetId}_${Date.now()}`,
      type: draft.type,
      target_id: draft.targetId,
      title: draftTitle.trim(),
      icon: chosenIcon || (draft.type === 'dashboard' ? 'BarChart2' : 'LayoutGrid'),
      is_visible: true,
      order: 99,
      app_type: draft.appType,
      status: draft.status,
      url: draft.url,
      path: draft.type === 'app' ? draftPath.trim() || undefined : undefined,
    });
  }

  function confirmLink(sectionId: string) {
    if (!linkTitle.trim() || !linkUrl.trim()) {
      toast.error('A name and a web address are required');
      return;
    }
    addItem(sectionId, {
      id: `item_ext_${Date.now()}`,
      type: 'external_link',
      target_id: `ext_${Date.now()}`,
      title: linkTitle.trim(),
      icon: chosenIcon || 'Globe',
      is_visible: true,
      order: 99,
      url: linkUrl.trim(),
    });
  }

  const editingItem = editing
    ? local.find((section) => section.id === editing.sectionId)?.items.find((item) => item.id === editing.itemId)
    : undefined;

  const query = search.trim().toLowerCase();
  const apps = (available?.apps || []).filter((app) => app.name.toLowerCase().includes(query));
  const dashboards = (available?.dashboards || []).filter((dash) => dash.name.toLowerCase().includes(query));
  const visibleCount = local.reduce((count, section) => count + section.items.filter((item) => item.is_visible).length, 0);

  return (
    <div className={`app-sidebar-section portal-nav ${canEdit ? 'is-editable' : ''}`} style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <div style={{ flex: 1, overflowY: 'auto' }}>
        {local.map((section, sectionIndex) => {
          const items = canEdit ? section.items : section.items.filter((item) => item.is_visible);
          if (!canEdit && items.length === 0) return null;
          return (
            <div key={section.id} className="app-sidebar-group">
              {section.title && (
                <div className="app-sidebar-divider-label portal-nav-label">
                  <span>{section.title}</span>
                  {canEdit && (
                    <button
                      type="button"
                      className={`portal-nav-more ${menu?.kind === 'group' && menu.id === section.id ? 'is-open' : ''}`}
                      aria-label={`Actions for ${section.title || 'group'}`}
                      onMouseDown={(event) => event.stopPropagation()}
                      onClick={(event) => openMenu(event, { kind: 'group', id: section.id })}
                    >
                      <MoreHorizontal size={14} />
                    </button>
                  )}
                </div>
              )}
              {!section.title && canEdit && (
                <button
                  type="button"
                  className={`portal-nav-more portal-nav-group-more ${menu?.kind === 'group' && menu.id === section.id ? 'is-open' : ''}`}
                  aria-label="Actions for group"
                  onMouseDown={(event) => event.stopPropagation()}
                  onClick={(event) => openMenu(event, { kind: 'group', id: section.id })}
                >
                  <MoreHorizontal size={14} />
                </button>
              )}
              {items.map((item) => {
                const itemIndex = section.items.findIndex((candidate) => candidate.id === item.id);
                const Icon = resolveScreenIcon(item);
                const selected = selectedItemId === item.id;
                return (
                  <div key={item.id} className={`portal-nav-row ${item.is_visible ? '' : 'is-hidden'}`}>
                    {item.type === 'external_link' && item.url ? (
                      <a className={`app-sidebar-link ${selected ? 'is-active' : ''}`} href={item.url} target="_blank" rel="noopener noreferrer" title={item.title}>
                        <Icon size={16} className="app-sidebar-link-icon" />
                        <span className="app-sidebar-link-label">{item.title}</span>
                      </a>
                    ) : (
                      <NavLink className={() => `app-sidebar-link ${selected ? 'is-active' : ''}`} to={appPath(portalItemTo(item))} title={item.title}>
                        <Icon size={16} className="app-sidebar-link-icon" />
                        <span className="app-sidebar-link-label">{item.title}</span>
                      </NavLink>
                    )}
                    {canEdit && (
                      <button
                        type="button"
                        className={`portal-nav-more ${menu?.kind === 'item' && menu.id === item.id ? 'is-open' : ''}`}
                        aria-label={`Actions for ${item.title}`}
                        onMouseDown={(event) => event.stopPropagation()}
                        onClick={(event) => openMenu(event, { kind: 'item', id: item.id, sectionId: section.id })}
                      >
                        <MoreHorizontal size={14} />
                      </button>
                    )}
                    {menu?.kind === 'item' && menu.id === item.id && (
                      <div ref={menuRef} className="portal-nav-menu" style={{ top: menu.top, left: menu.left }}>
                        <button type="button" onClick={() => beginEdit(section.id, item)}>Edit</button>
                        <button type="button" disabled={itemIndex === 0} onClick={() => moveItem(section.id, itemIndex, 'up')}>Move up</button>
                        <button type="button" disabled={itemIndex === section.items.length - 1} onClick={() => moveItem(section.id, itemIndex, 'down')}>Move down</button>
                        <button type="button" onClick={() => commit(updateItem(section.id, item.id, { is_visible: !item.is_visible }))}>
                          {item.is_visible ? 'Hide' : 'Show'}
                        </button>
                        <button
                          type="button"
                          className="is-danger"
                          onClick={() =>
                            commit(
                              local.map((group) =>
                                group.id === section.id ? { ...group, items: group.items.filter((candidate) => candidate.id !== item.id) } : group,
                              ),
                            )
                          }
                        >
                          Remove
                        </button>
                      </div>
                    )}
                  </div>
                );
              })}
              {menu?.kind === 'group' && menu.id === section.id && (
                <div ref={menuRef} className="portal-nav-menu" style={{ top: menu.top, left: menu.left }}>
                  <button
                    type="button"
                    onClick={() => {
                      if (!menu) return;
                      setGroupTitle(section.title);
                      setRenamingGroup({ id: section.id, top: menu.top, left: menu.left });
                      setMenu(null);
                      setEditing(null);
                    }}
                  >
                    Rename
                  </button>
                  <button
                    type="button"
                    onClick={(event) => beginAdd(section.id, event.currentTarget)}
                  >
                    Add a screen
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      const created: PortalSection = { id: `sec_${Date.now()}`, title: 'New group', items: [] };
                      const copy = [...local];
                      copy.splice(sectionIndex + 1, 0, created);
                      void commit(copy);
                    }}
                  >
                    New group
                  </button>
                  <button type="button" disabled={sectionIndex === 0} onClick={() => moveSection(sectionIndex, 'up')}>Move up</button>
                  <button type="button" disabled={sectionIndex === local.length - 1} onClick={() => moveSection(sectionIndex, 'down')}>Move down</button>
                  <button type="button" className="is-danger" onClick={() => commit(local.filter((group) => group.id !== section.id))}>
                    Delete group
                  </button>
                </div>
              )}
            </div>
          );
        })}

        {canEdit && local.length === 0 && (
          <button
            type="button"
            className="portal-nav-new"
            onClick={() => void commit([{ id: `sec_${Date.now()}`, title: 'New group', items: [] }])}
          >
            New group
          </button>
        )}

        {!canEdit && visibleCount === 0 && <div className="portal-nav-empty">No items pinned to sidebar.</div>}
      </div>

      {canEdit && (
        <NavLink
          to={appPath('/portal/settings')}
          className={({ isActive }) => `portal-nav-settings${isActive ? ' is-active' : ''}`}
          title="Portal settings"
        >
          <Settings size={16} />
          <span>Portal settings</span>
        </NavLink>
      )}

      {addFor && (
        <div ref={addRef} className="portal-nav-add" style={{ top: fitPopup(addFor.top), left: Math.min(addFor.left, window.innerWidth - 276) }}>
          {!draft && addKind !== 'link' && (
            <input value={search} placeholder="Search" aria-label="Search" onChange={(event) => setSearch(event.target.value)} autoFocus />
          )}
          <div className="portal-nav-kinds">
            {(['app', 'dashboard', 'link'] as AddKind[]).map((kind) => (
              <button key={kind} type="button" className={addKind === kind ? 'is-on' : ''} onClick={() => { setAddKind(kind); setDraft(null); }}>
                {kind === 'app' ? 'App' : kind === 'dashboard' ? 'Dashboard' : 'Link'}
              </button>
            ))}
          </div>
          {addKind === 'app' && !draft && (
            <div className="portal-nav-results">
              {apps.map((app) => (
                <button
                  key={app.id}
                  type="button"
                  onClick={() => {
                    setDraft({ type: 'app', targetId: app.id, appType: app.app_type, status: app.status, url: app.route });
                    setDraftTitle(app.name);
                    setDraftPath('');
                  }}
                >
                  <strong>{app.name}</strong>
                  <em>App</em>
                </button>
              ))}
              {apps.length === 0 && <p className="portal-nav-empty">No apps match.</p>}
            </div>
          )}
          {addKind === 'dashboard' && !draft && (
            <div className="portal-nav-results">
              {dashboards.map((dash) => (
                <button
                  key={dash.id}
                  type="button"
                  onClick={() => {
                    setDraft({ type: 'dashboard', targetId: dash.id, status: dash.is_draft ? 'draft' : 'published' });
                    setDraftTitle(dash.name);
                  }}
                >
                  <strong>{dash.name}</strong>
                  <em>Dashboard</em>
                </button>
              ))}
              {dashboards.length === 0 && <p className="portal-nav-empty">No dashboards match.</p>}
            </div>
          )}
          {draft && (
            <form
              className="portal-nav-edit"
              onSubmit={(event) => {
                event.preventDefault();
                confirmDraft(addFor.sectionId);
              }}
            >
              <input value={draftTitle} aria-label="Screen name" onChange={(event) => setDraftTitle(event.target.value)} autoFocus />
              {draft.type === 'app' && (
                <input value={draftPath} aria-label="Page" placeholder="Home" onChange={(event) => setDraftPath(event.target.value)} />
              )}
              <IconChoices value={chosenIcon} onChange={setChosenIcon} />
              <button type="submit" className="portal-nav-save">Add</button>
            </form>
          )}
          {addKind === 'link' && (
            <form
              className="portal-nav-edit"
              onSubmit={(event) => {
                event.preventDefault();
                confirmLink(addFor.sectionId);
              }}
            >
              <input value={linkTitle} aria-label="Screen name" placeholder="Name" onChange={(event) => setLinkTitle(event.target.value)} />
              <input value={linkUrl} aria-label="Web address" placeholder="https://" onChange={(event) => setLinkUrl(event.target.value)} />
              <IconChoices value={chosenIcon} onChange={setChosenIcon} />
              <button type="submit" className="portal-nav-save">Add</button>
            </form>
          )}
        </div>
      )}

      {editing && editingItem && (
        <form
          ref={editRef}
          className="portal-nav-add portal-nav-pop"
          style={{ top: fitPopup(editing.top), left: Math.min(editing.left, window.innerWidth - 276) }}
          onSubmit={(event) => {
            event.preventDefault();
            saveEdit(editing.sectionId, editingItem);
          }}
        >
          <p className="portal-nav-pop-title">Edit screen</p>
          <label>
            Screen name
            <input value={editTitle} aria-label="Screen name" onChange={(event) => setEditTitle(event.target.value)} autoFocus />
          </label>
          {editingItem.type === 'app' && (
            <label>
              Page
              <input value={editPath} aria-label="Page" placeholder="Home" onChange={(event) => setEditPath(event.target.value)} />
            </label>
          )}
          {editingItem.type === 'external_link' && (
            <label>
              Web address
              <input value={editUrl} aria-label="Web address" placeholder="https://" onChange={(event) => setEditUrl(event.target.value)} />
            </label>
          )}
          <IconChoices value={editIcon} onChange={setEditIcon} />
          <div className="portal-nav-pop-actions">
            <button type="submit" className="portal-nav-save">Save</button>
            <button type="button" className="portal-nav-cancel" onClick={() => setEditing(null)}>Cancel</button>
          </div>
        </form>
      )}

      {renamingGroup && (
        <form
          ref={editRef}
          className="portal-nav-add portal-nav-pop"
          style={{ top: renamingGroup.top, left: Math.min(renamingGroup.left, window.innerWidth - 276) }}
          onSubmit={(event) => {
            event.preventDefault();
            void commit(local.map((group) => (group.id === renamingGroup.id ? { ...group, title: groupTitle.trim() } : group)));
            setRenamingGroup(null);
          }}
        >
          <p className="portal-nav-pop-title">Rename group</p>
          <label>
            Group name
            <input value={groupTitle} aria-label="Group name" onChange={(event) => setGroupTitle(event.target.value)} autoFocus />
          </label>
          <div className="portal-nav-pop-actions">
            <button type="submit" className="portal-nav-save">Save</button>
            <button type="button" className="portal-nav-cancel" onClick={() => setRenamingGroup(null)}>Cancel</button>
          </div>
        </form>
      )}
    </div>
  );
}

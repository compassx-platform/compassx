import React, { useState, useEffect } from 'react';
import {
  X,
  Plus,
  Trash2,
  ChevronUp,
  ChevronDown,
  Eye,
  EyeOff,
  LayoutGrid,
  BarChart2,
  Globe,
  Code2,
  Folder,
  Sparkles,
  Link,
  Check,
  Save,
  Loader2,
  Search,
} from 'lucide-react';
import {
  PortalConfig,
  PortalSection,
  PortalItem,
  usePortalAvailableItems,
  useUpdatePortalConfig,
} from '../hooks/usePortalConfig';
import { useToast } from '@/lib/toast';

interface CustomizeSidebarDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  currentConfig?: PortalConfig;
}

export function CustomizeSidebarDrawer({
  isOpen,
  onClose,
  currentConfig,
}: CustomizeSidebarDrawerProps) {
  const toast = useToast();
  const { data: availableData, isLoading: availableLoading } = usePortalAvailableItems();
  const updateMutation = useUpdatePortalConfig();

  const [sections, setSections] = useState<PortalSection[]>([]);
  const [addItemSectionId, setAddItemSectionId] = useState<string | null>(null);
  const [pickerTab, setPickerTab] = useState<'apps' | 'dashboards' | 'custom'>('apps');
  const [searchQuery, setSearchQuery] = useState('');
  const [customLinkTitle, setCustomLinkTitle] = useState('');
  const [customLinkUrl, setCustomLinkUrl] = useState('');

  useEffect(() => {
    if (currentConfig?.sections) {
      // Deep clone sections for local state editing
      setSections(JSON.parse(JSON.stringify(currentConfig.sections)));
    }
  }, [currentConfig, isOpen]);

  if (!isOpen) return null;

  function handleAddSection() {
    const newSection: PortalSection = {
      id: `sec_${Date.now()}`,
      title: 'New Category',
      items: [],
    };
    setSections([...sections, newSection]);
  }

  function handleRemoveSection(secId: string) {
    setSections(sections.filter((s) => s.id !== secId));
  }

  function handleMoveSection(index: number, direction: 'up' | 'down') {
    const targetIdx = direction === 'up' ? index - 1 : index + 1;
    if (targetIdx < 0 || targetIdx >= sections.length) return;
    const copy = [...sections];
    const temp = copy[index];
    copy[index] = copy[targetIdx];
    copy[targetIdx] = temp;
    setSections(copy);
  }

  function handleUpdateSectionTitle(secId: string, newTitle: string) {
    setSections(
      sections.map((s) => (s.id === secId ? { ...s, title: newTitle } : s))
    );
  }

  function handleToggleItemVisibility(secId: string, itemId: string) {
    setSections(
      sections.map((sec) => {
        if (sec.id !== secId) return sec;
        return {
          ...sec,
          items: sec.items.map((it) =>
            it.id === itemId ? { ...it, is_visible: !it.is_visible } : it
          ),
        };
      })
    );
  }

  function handleMoveItem(secId: string, index: number, direction: 'up' | 'down') {
    setSections(
      sections.map((sec) => {
        if (sec.id !== secId) return sec;
        const targetIdx = direction === 'up' ? index - 1 : index + 1;
        if (targetIdx < 0 || targetIdx >= sec.items.length) return sec;
        const copy = [...sec.items];
        const temp = copy[index];
        copy[index] = copy[targetIdx];
        copy[targetIdx] = temp;
        // Update order indices
        return {
          ...sec,
          items: copy.map((it, idx) => ({ ...it, order: idx })),
        };
      })
    );
  }

  function handleRemoveItem(secId: string, itemId: string) {
    setSections(
      sections.map((sec) => {
        if (sec.id !== secId) return sec;
        return {
          ...sec,
          items: sec.items.filter((it) => it.id !== itemId),
        };
      })
    );
  }

  function handleAddExistingApp(secId: string, app: any) {
    const newItem: PortalItem = {
      id: `item_app_${app.id}_${Date.now()}`,
      type: 'app',
      target_id: app.id,
      title: app.name,
      icon: app.app_type === 'react' ? 'LayoutGrid' : 'Sparkles',
      is_visible: true,
      order: 99,
      app_type: app.app_type,
      status: app.status,
      url: app.route,
    };

    setSections(
      sections.map((sec) => (sec.id === secId ? { ...sec, items: [...sec.items, newItem] } : sec))
    );
    setAddItemSectionId(null);
  }

  function handleAddExistingDashboard(secId: string, dash: any) {
    const newItem: PortalItem = {
      id: `item_dash_${dash.id}_${Date.now()}`,
      type: 'dashboard',
      target_id: dash.id,
      title: dash.name,
      icon: 'BarChart2',
      is_visible: true,
      order: 99,
      status: dash.is_draft ? 'draft' : 'published',
    };

    setSections(
      sections.map((sec) => (sec.id === secId ? { ...sec, items: [...sec.items, newItem] } : sec))
    );
    setAddItemSectionId(null);
  }

  function handleAddCustomLink(secId: string) {
    if (!customLinkTitle.trim() || !customLinkUrl.trim()) {
      toast.error('Title and URL are required');
      return;
    }
    const newItem: PortalItem = {
      id: `item_ext_${Date.now()}`,
      type: 'external_link',
      target_id: `ext_${Date.now()}`,
      title: customLinkTitle.trim(),
      icon: 'Globe',
      is_visible: true,
      order: 99,
      url: customLinkUrl.trim(),
    };

    setSections(
      sections.map((sec) => (sec.id === secId ? { ...sec, items: [...sec.items, newItem] } : sec))
    );
    setCustomLinkTitle('');
    setCustomLinkUrl('');
    setAddItemSectionId(null);
  }

  async function handleSave() {
    try {
      await updateMutation.mutateAsync(sections);
      toast.success('Portal sidebar layout saved.');
      onClose();
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || 'Failed to save portal layout.');
    }
  }

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 9999,
        background: 'rgba(15, 23, 42, 0.65)',
        backdropFilter: 'blur(4px)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: 24,
      }}
    >
      <div
        className="glass animate-fade-in"
        style={{
          width: '100%',
          maxWidth: 720,
          maxHeight: '90vh',
          background: 'var(--color-surface)',
          border: '1px solid var(--color-border)',
          borderRadius: 16,
          display: 'flex',
          flexDirection: 'column',
          boxShadow: '0 24px 48px rgba(0,0,0,0.25)',
          overflow: 'hidden',
        }}
      >
        {/* Header */}
        <div
          style={{
            padding: '18px 24px',
            borderBottom: '1px solid var(--color-border)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}
        >
          <div>
            <h2 style={{ margin: 0, fontSize: '1.2rem', fontWeight: 600, color: 'var(--color-text)' }}>
              Customize Portal Sidebar
            </h2>
            <p style={{ margin: '4px 0 0', fontSize: '0.84rem', color: 'var(--color-text-muted)' }}>
              Organize categories, reorder items, and manage app & dashboard visibility for your workspace.
            </p>
          </div>
          <button
            onClick={onClose}
            style={{
              background: 'transparent',
              border: 'none',
              color: 'var(--color-text-muted)',
              cursor: 'pointer',
              padding: 6,
              borderRadius: 8,
            }}
          >
            <X size={20} />
          </button>
        </div>

        {/* Body / Section List */}
        <div style={{ flex: 1, overflowY: 'auto', padding: '20px 24px', display: 'flex', flexDirection: 'column', gap: 20 }}>
          {sections.map((section, sIdx) => (
            <div
              key={section.id}
              style={{
                background: 'var(--color-bg)',
                border: '1px solid var(--color-border)',
                borderRadius: 12,
                padding: 16,
              }}
            >
              {/* Section Header */}
              <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 12 }}>
                <Folder size={18} style={{ color: 'var(--color-primary)', flexShrink: 0 }} />
                <input
                  type="text"
                  value={section.title}
                  onChange={(e) => handleUpdateSectionTitle(section.id, e.target.value)}
                  placeholder="Category Name"
                  style={{
                    flex: 1,
                    background: 'var(--color-surface)',
                    border: '1px solid var(--color-border)',
                    borderRadius: 6,
                    padding: '6px 10px',
                    fontSize: '0.9rem',
                    fontWeight: 600,
                    color: 'var(--color-text)',
                  }}
                />
                <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                  <button
                    onClick={() => handleMoveSection(sIdx, 'up')}
                    disabled={sIdx === 0}
                    title="Move Category Up"
                    style={{
                      background: 'transparent',
                      border: 'none',
                      color: sIdx === 0 ? 'var(--color-border)' : 'var(--color-text-muted)',
                      cursor: sIdx === 0 ? 'default' : 'pointer',
                      padding: 4,
                    }}
                  >
                    <ChevronUp size={16} />
                  </button>
                  <button
                    onClick={() => handleMoveSection(sIdx, 'down')}
                    disabled={sIdx === sections.length - 1}
                    title="Move Category Down"
                    style={{
                      background: 'transparent',
                      border: 'none',
                      color: sIdx === sections.length - 1 ? 'var(--color-border)' : 'var(--color-text-muted)',
                      cursor: sIdx === sections.length - 1 ? 'default' : 'pointer',
                      padding: 4,
                    }}
                  >
                    <ChevronDown size={16} />
                  </button>
                  <button
                    onClick={() => handleRemoveSection(section.id)}
                    title="Delete Category"
                    style={{
                      background: 'transparent',
                      border: 'none',
                      color: 'var(--color-danger)',
                      cursor: 'pointer',
                      padding: 4,
                    }}
                  >
                    <Trash2 size={16} />
                  </button>
                </div>
              </div>

              {/* Items in Section */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginBottom: 10 }}>
                {section.items.map((item, iIdx) => (
                  <div
                    key={item.id}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: 10,
                      padding: '8px 12px',
                      background: 'var(--color-surface)',
                      border: '1px solid var(--color-border)',
                      borderRadius: 8,
                      opacity: item.is_visible ? 1 : 0.5,
                    }}
                  >
                    {item.type === 'app' ? (
                      <LayoutGrid size={16} style={{ color: 'var(--color-primary)', flexShrink: 0 }} />
                    ) : item.type === 'dashboard' ? (
                      <BarChart2 size={16} style={{ color: '#10b981', flexShrink: 0 }} />
                    ) : (
                      <Globe size={16} style={{ color: '#6366f1', flexShrink: 0 }} />
                    )}

                    <span style={{ flex: 1, fontSize: '0.86rem', fontWeight: 500, color: 'var(--color-text)' }}>
                      {item.title}
                    </span>

                    <span
                      style={{
                        fontSize: '0.72rem',
                        padding: '2px 6px',
                        borderRadius: 4,
                        background: 'var(--color-surface-hover)',
                        color: 'var(--color-text-muted)',
                        textTransform: 'uppercase',
                        fontWeight: 600,
                      }}
                    >
                      {item.type}
                    </span>

                    {/* Actions */}
                    <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                      <button
                        onClick={() => handleToggleItemVisibility(section.id, item.id)}
                        title={item.is_visible ? 'Hide from sidebar' : 'Show in sidebar'}
                        style={{
                          background: 'transparent',
                          border: 'none',
                          color: item.is_visible ? 'var(--color-primary)' : 'var(--color-text-muted)',
                          cursor: 'pointer',
                          padding: 4,
                        }}
                      >
                        {item.is_visible ? <Eye size={16} /> : <EyeOff size={16} />}
                      </button>
                      <button
                        onClick={() => handleMoveItem(section.id, iIdx, 'up')}
                        disabled={iIdx === 0}
                        style={{
                          background: 'transparent',
                          border: 'none',
                          color: iIdx === 0 ? 'var(--color-border)' : 'var(--color-text-muted)',
                          cursor: iIdx === 0 ? 'default' : 'pointer',
                          padding: 4,
                        }}
                      >
                        <ChevronUp size={16} />
                      </button>
                      <button
                        onClick={() => handleMoveItem(section.id, iIdx, 'down')}
                        disabled={iIdx === section.items.length - 1}
                        style={{
                          background: 'transparent',
                          border: 'none',
                          color: iIdx === section.items.length - 1 ? 'var(--color-border)' : 'var(--color-text-muted)',
                          cursor: iIdx === section.items.length - 1 ? 'default' : 'pointer',
                          padding: 4,
                        }}
                      >
                        <ChevronDown size={16} />
                      </button>
                      <button
                        onClick={() => handleRemoveItem(section.id, item.id)}
                        title="Remove from category"
                        style={{
                          background: 'transparent',
                          border: 'none',
                          color: 'var(--color-danger)',
                          cursor: 'pointer',
                          padding: 4,
                        }}
                      >
                        <Trash2 size={16} />
                      </button>
                    </div>
                  </div>
                ))}

                {section.items.length === 0 && (
                  <div
                    style={{
                      padding: 12,
                      textAlign: 'center',
                      fontSize: '0.82rem',
                      color: 'var(--color-text-muted)',
                      border: '1px dashed var(--color-border)',
                      borderRadius: 8,
                    }}
                  >
                    No items in this category yet.
                  </div>
                )}
              </div>

              {/* Add Item Button */}
              <button
                className="btn-outline"
                onClick={() => setAddItemSectionId(section.id)}
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: 6,
                  padding: '6px 12px',
                  borderRadius: 6,
                  fontSize: '0.82rem',
                  cursor: 'pointer',
                }}
              >
                <Plus size={14} /> Add App or Dashboard
              </button>
            </div>
          ))}

          <button
            className="btn-outline"
            onClick={handleAddSection}
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: 8,
              padding: 12,
              borderRadius: 10,
              border: '1px dashed var(--color-border)',
              cursor: 'pointer',
              fontWeight: 500,
            }}
          >
            <Plus size={16} /> Add New Category Section
          </button>
        </div>

        {/* Footer */}
        <div
          style={{
            padding: '16px 24px',
            borderTop: '1px solid var(--color-border)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'flex-end',
            gap: 12,
            background: 'var(--color-surface)',
          }}
        >
          <button className="btn-outline" onClick={onClose} style={{ padding: '8px 18px', borderRadius: 8, cursor: 'pointer' }}>
            Cancel
          </button>
          <button
            className="btn-primary"
            onClick={handleSave}
            disabled={updateMutation.isPending}
            style={{ display: 'inline-flex', alignItems: 'center', gap: 6, padding: '8px 20px', borderRadius: 8, cursor: 'pointer' }}
          >
            {updateMutation.isPending ? <Loader2 size={16} className="spin" /> : <Save size={16} />}
            Save Changes
          </button>
        </div>
      </div>

      {/* Add Item Sub-Modal Picker */}
      {addItemSectionId && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            zIndex: 10000,
            background: 'rgba(0, 0, 0, 0.5)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: 20,
          }}
        >
          <div
            className="glass animate-fade-in"
            style={{
              width: '100%',
              maxWidth: 520,
              background: 'var(--color-surface)',
              border: '1px solid var(--color-border)',
              borderRadius: 14,
              display: 'flex',
              flexDirection: 'column',
              boxShadow: 'var(--shadow-lg)',
              overflow: 'hidden',
            }}
          >
            <div
              style={{
                padding: '14px 20px',
                borderBottom: '1px solid var(--color-border)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
              }}
            >
              <h3 style={{ margin: 0, fontSize: '1rem', fontWeight: 600, color: 'var(--color-text)' }}>
                Add to Category
              </h3>
              <button
                onClick={() => setAddItemSectionId(null)}
                style={{ background: 'transparent', border: 'none', color: 'var(--color-text-muted)', cursor: 'pointer' }}
              >
                <X size={18} />
              </button>
            </div>

            {/* Tabs */}
            <div style={{ display: 'flex', borderBottom: '1px solid var(--color-border)', background: 'var(--color-bg)' }}>
              <button
                onClick={() => setPickerTab('apps')}
                style={{
                  flex: 1,
                  padding: '10px 0',
                  border: 'none',
                  background: pickerTab === 'apps' ? 'var(--color-surface)' : 'transparent',
                  color: pickerTab === 'apps' ? 'var(--color-primary)' : 'var(--color-text-muted)',
                  fontWeight: pickerTab === 'apps' ? 600 : 400,
                  fontSize: '0.86rem',
                  cursor: 'pointer',
                  borderBottom: pickerTab === 'apps' ? '2px solid var(--color-primary)' : 'none',
                }}
              >
                Applications
              </button>
              <button
                onClick={() => setPickerTab('dashboards')}
                style={{
                  flex: 1,
                  padding: '10px 0',
                  border: 'none',
                  background: pickerTab === 'dashboards' ? 'var(--color-surface)' : 'transparent',
                  color: pickerTab === 'dashboards' ? 'var(--color-primary)' : 'var(--color-text-muted)',
                  fontWeight: pickerTab === 'dashboards' ? 600 : 400,
                  fontSize: '0.86rem',
                  cursor: 'pointer',
                  borderBottom: pickerTab === 'dashboards' ? '2px solid var(--color-primary)' : 'none',
                }}
              >
                Dashboards
              </button>
              <button
                onClick={() => setPickerTab('custom')}
                style={{
                  flex: 1,
                  padding: '10px 0',
                  border: 'none',
                  background: pickerTab === 'custom' ? 'var(--color-surface)' : 'transparent',
                  color: pickerTab === 'custom' ? 'var(--color-primary)' : 'var(--color-text-muted)',
                  fontWeight: pickerTab === 'custom' ? 600 : 400,
                  fontSize: '0.86rem',
                  cursor: 'pointer',
                  borderBottom: pickerTab === 'custom' ? '2px solid var(--color-primary)' : 'none',
                }}
              >
                External URL
              </button>
            </div>

            {/* Content */}
            <div style={{ padding: 16, maxHeight: 320, overflowY: 'auto' }}>
              {pickerTab === 'apps' && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                  {availableData?.apps.map((app) => (
                    <button
                      key={app.id}
                      onClick={() => handleAddExistingApp(addItemSectionId, app)}
                      className="btn-outline"
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        padding: '10px 14px',
                        borderRadius: 8,
                        textAlign: 'left',
                        cursor: 'pointer',
                      }}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                        <LayoutGrid size={16} style={{ color: 'var(--color-primary)' }} />
                        <div>
                          <div style={{ fontWeight: 600, fontSize: '0.88rem', color: 'var(--color-text)' }}>{app.name}</div>
                          <div style={{ fontSize: '0.76rem', color: 'var(--color-text-muted)' }}>{app.app_type} • {app.status}</div>
                        </div>
                      </div>
                      <Plus size={16} />
                    </button>
                  ))}
                  {(!availableData?.apps || availableData.apps.length === 0) && (
                    <div style={{ padding: 20, textAlign: 'center', color: 'var(--color-text-muted)', fontSize: '0.86rem' }}>
                      No applications found in this workspace.
                    </div>
                  )}
                </div>
              )}

              {pickerTab === 'dashboards' && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                  {availableData?.dashboards.map((dash) => (
                    <button
                      key={dash.id}
                      onClick={() => handleAddExistingDashboard(addItemSectionId, dash)}
                      className="btn-outline"
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        padding: '10px 14px',
                        borderRadius: 8,
                        textAlign: 'left',
                        cursor: 'pointer',
                      }}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                        <BarChart2 size={16} style={{ color: '#10b981' }} />
                        <div>
                          <div style={{ fontWeight: 600, fontSize: '0.88rem', color: 'var(--color-text)' }}>{dash.name}</div>
                          <div style={{ fontSize: '0.76rem', color: 'var(--color-text-muted)' }}>
                            {dash.is_draft ? 'Draft' : 'Published'}
                          </div>
                        </div>
                      </div>
                      <Plus size={16} />
                    </button>
                  ))}
                  {(!availableData?.dashboards || availableData.dashboards.length === 0) && (
                    <div style={{ padding: 20, textAlign: 'center', color: 'var(--color-text-muted)', fontSize: '0.86rem' }}>
                      No dashboards found in this workspace.
                    </div>
                  )}
                </div>
              )}

              {pickerTab === 'custom' && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                  <div>
                    <label style={{ display: 'block', fontSize: '0.82rem', fontWeight: 500, marginBottom: 4, color: 'var(--color-text)' }}>
                      Link Title
                    </label>
                    <input
                      type="text"
                      placeholder="e.g. Documentation Hub"
                      value={customLinkTitle}
                      onChange={(e) => setCustomLinkTitle(e.target.value)}
                      style={{
                        width: '100%',
                        padding: '8px 12px',
                        background: 'var(--color-bg)',
                        border: '1px solid var(--color-border)',
                        borderRadius: 6,
                        fontSize: '0.88rem',
                        color: 'var(--color-text)',
                      }}
                    />
                  </div>
                  <div>
                    <label style={{ display: 'block', fontSize: '0.82rem', fontWeight: 500, marginBottom: 4, color: 'var(--color-text)' }}>
                      Web URL
                    </label>
                    <input
                      type="url"
                      placeholder="https://example.com"
                      value={customLinkUrl}
                      onChange={(e) => setCustomLinkUrl(e.target.value)}
                      style={{
                        width: '100%',
                        padding: '8px 12px',
                        background: 'var(--color-bg)',
                        border: '1px solid var(--color-border)',
                        borderRadius: 6,
                        fontSize: '0.88rem',
                        color: 'var(--color-text)',
                      }}
                    />
                  </div>
                  <button
                    className="btn-primary"
                    onClick={() => handleAddCustomLink(addItemSectionId)}
                    style={{ padding: '8px 16px', borderRadius: 6, marginTop: 4, cursor: 'pointer' }}
                  >
                    Add Link
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

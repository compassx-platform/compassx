import { useRef, useState } from 'react';
import { usePortalConfig, useUpdatePortalSettings } from '../hooks/usePortalConfig';
import { useWorkspaceContext } from '@/lib/workspaceContext';
import './portal-settings.css';

const MAX_LOGO_BYTES = 400_000;

export default function PortalSettingsPage() {
  const { data, isLoading } = usePortalConfig();
  const update = useUpdatePortalSettings();
  const workspace = useWorkspaceContext();
  const fileRef = useRef<HTMLInputElement | null>(null);
  const [error, setError] = useState('');
  const canEdit = Boolean(
    workspace.is_account_admin
    || workspace.current_user_role === 'workspace_admin'
    || workspace.current_user_role === 'admin',
  );
  const logo = data?.settings?.logo || '';

  function chooseFile(file: File | undefined) {
    if (!file) return;
    if (!file.type.startsWith('image/')) {
      setError('Choose an image file.');
      return;
    }
    if (file.size > MAX_LOGO_BYTES) {
      setError('Choose an image under 400 KB.');
      return;
    }
    const reader = new FileReader();
    reader.onload = () => {
      const value = String(reader.result || '');
      setError('');
      update.mutate(value, {
        onError: () => setError('Could not save the logo.'),
      });
    };
    reader.readAsDataURL(file);
  }

  return (
    <div className="portal-settings">
      <header className="portal-settings-head">
        <h1>Portal settings</h1>
        <p>These settings apply to this workspace portal. Platform screens and linked applications keep the CompassX logo.</p>
      </header>

      <section className="portal-settings-card" aria-labelledby="portal-logo-heading">
        <h2 id="portal-logo-heading">Company logo</h2>
        <p>Shown in place of the CompassX logo in the portal sidebar.</p>
        <div className="portal-settings-logo-row">
          <div className="portal-settings-preview" aria-label="Logo preview">
            {logo ? <img src={logo} alt="Company logo" /> : <span>No logo yet</span>}
          </div>
          {canEdit && (
            <div className="portal-settings-actions">
              <button
                type="button"
                className="portal-settings-upload"
                disabled={update.isPending || isLoading}
                onClick={() => fileRef.current?.click()}
              >
                {logo ? 'Replace logo' : 'Upload logo'}
              </button>
              {logo && (
                <button
                  type="button"
                  className="portal-settings-remove"
                  disabled={update.isPending}
                  onClick={() => {
                    setError('');
                    update.mutate(null, { onError: () => setError('Could not remove the logo.') });
                  }}
                >
                  Remove
                </button>
              )}
              <input
                ref={fileRef}
                type="file"
                accept="image/png,image/jpeg,image/webp,image/gif,image/svg+xml"
                hidden
                onChange={(event) => {
                  chooseFile(event.target.files?.[0]);
                  event.target.value = '';
                }}
              />
            </div>
          )}
        </div>
        {error && <p className="portal-settings-error" role="alert">{error}</p>}
        {!canEdit && <p className="portal-settings-note">A workspace admin can change this logo.</p>}
      </section>
    </div>
  );
}

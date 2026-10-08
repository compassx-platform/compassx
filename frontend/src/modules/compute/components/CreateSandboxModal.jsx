// @ts-nocheck
import { useState } from 'react';
import { Box, Plus, Trash2, Cpu, Terminal, Shield } from 'lucide-react';

const CONSUMER_MODULES = [
  { id: 'app', label: 'App Engine', desc: 'Application build & deployment runner' },
  { id: 'agent', label: 'Agent Runtime', desc: 'Nova AI code interpreter & tools' },
  { id: 'omnigent_dev', label: 'Dev Studio', desc: 'Interactive workspace sandbox' },
  { id: 'notebook', label: 'Notebook', desc: 'Jupyter kernel & interactive compute' },
  { id: 'job', label: 'Jobs Runner', desc: 'Batch pipeline execution' },
  { id: 'generic', label: 'Custom Sandbox', desc: 'General-purpose compute sandbox' },
];

const PRESET_IMAGES = [
  { label: 'Python 3.11 Slim', value: 'python:3.11-slim' },
  { label: 'Node.js 20 LTS', value: 'node:20-slim' },
  { label: 'CompassX Runtime Base', value: 'compassx/runtime-base:latest' },
  { label: 'Debian Bookworm', value: 'debian:bookworm-slim' },
];

/**
 * Modal to provision a new compute sandbox on-demand.
 */
export default function CreateSandboxModal({ isOpen, onClose, onProvision }) {
  const [name, setName] = useState('');
  const [consumerModule, setConsumerModule] = useState('app');
  const [image, setImage] = useState('python:3.11-slim');
  const [customImage, setCustomImage] = useState('');
  const [ports, setPorts] = useState('8080');
  const [initCommand, setInitCommand] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  if (!isOpen) return null;

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!name.trim()) {
      setError('Sandbox name is required.');
      return;
    }

    setLoading(true);
    setError(null);

    const parsedPorts = ports
      .split(',')
      .map((p) => parseInt(p.trim(), 10))
      .filter((p) => !isNaN(p) && p > 0);

    const selectedImage = customImage.trim() || image;

    const initScripts = [];
    if (initCommand.trim()) {
      initScripts.push({
        name: 'Startup Script',
        command: initCommand.trim(),
        timeout_seconds: 120,
      });
    }

    const spec = {
      name: name.trim(),
      consumer_module: consumerModule,
      image: selectedImage,
      ports: parsedPorts,
      init_scripts: initScripts,
      working_dir: '/workspace',
    };

    try {
      await onProvision(spec);
      onClose();
      setName('');
      setInitCommand('');
    } catch (err) {
      setError(err?.response?.data?.message || err?.message || 'Failed to provision sandbox');
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <div
        onClick={onClose}
        style={{
          position: 'fixed',
          inset: 0,
          background: 'rgba(0, 0, 0, 0.4)',
          zIndex: 999,
        }}
      />
      <div
        style={{
          position: 'fixed',
          top: '50%',
          left: '50%',
          transform: 'translate(-50%, -50%)',
          zIndex: 1000,
          background: 'var(--color-surface)',
          borderRadius: '8px',
          border: '1px solid var(--color-border)',
          boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.2)',
          maxWidth: '560px',
          width: '90vw',
          maxHeight: '90vh',
          overflowY: 'auto',
        }}
      >
        <div style={{ padding: '20px 24px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Box size={18} color="var(--color-primary)" />
              <h2 style={{ margin: 0, fontSize: '16px', fontWeight: 700, color: 'var(--color-text)' }}>
                Provision Compute Sandbox
              </h2>
            </div>
            <button
              onClick={onClose}
              style={{
                background: 'none',
                border: 'none',
                fontSize: '20px',
                cursor: 'pointer',
                color: 'var(--color-text-muted)',
              }}
            >
              ×
            </button>
          </div>

          <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            {/* Sandbox Name */}
            <div>
              <label style={{ display: 'block', fontSize: '12px', fontWeight: 600, color: 'var(--color-text)', marginBottom: '6px' }}>
                Sandbox Name *
              </label>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="e.g., app-build-sandbox-1"
                style={{
                  width: '100%',
                  height: '32px',
                  padding: '0 10px',
                  borderRadius: '4px',
                  border: '1px solid var(--color-border)',
                  background: 'var(--color-surface)',
                  color: 'var(--color-text)',
                  fontSize: '12px',
                }}
              />
            </div>

            {/* Consumer Module Selection */}
            <div>
              <label style={{ display: 'block', fontSize: '12px', fontWeight: 600, color: 'var(--color-text)', marginBottom: '6px' }}>
                Consumer Module *
              </label>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '8px' }}>
                {CONSUMER_MODULES.map((mod) => {
                  const active = consumerModule === mod.id;
                  return (
                    <div
                      key={mod.id}
                      onClick={() => setConsumerModule(mod.id)}
                      style={{
                        padding: '8px 10px',
                        borderRadius: '4px',
                        border: `1px solid ${active ? 'var(--color-primary)' : 'var(--color-border)'}`,
                        background: active ? 'var(--color-primary-muted, rgba(99,102,241,0.08))' : 'var(--color-surface)',
                        cursor: 'pointer',
                        display: 'flex',
                        flexDirection: 'column',
                        gap: '2px',
                      }}
                    >
                      <span style={{ fontSize: '12px', fontWeight: 600, color: active ? 'var(--color-primary)' : 'var(--color-text)' }}>
                        {mod.label}
                      </span>
                      <span style={{ fontSize: '10px', color: 'var(--color-text-muted)' }}>{mod.desc}</span>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Runtime Image */}
            <div>
              <label style={{ display: 'block', fontSize: '12px', fontWeight: 600, color: 'var(--color-text)', marginBottom: '6px' }}>
                Base Image
              </label>
              <select
                value={image}
                onChange={(e) => {
                  setImage(e.target.value);
                  setCustomImage('');
                }}
                style={{
                  width: '100%',
                  height: '32px',
                  padding: '0 10px',
                  borderRadius: '4px',
                  border: '1px solid var(--color-border)',
                  background: 'var(--color-surface)',
                  color: 'var(--color-text)',
                  fontSize: '12px',
                  marginBottom: '6px',
                }}
              >
                {PRESET_IMAGES.map((img) => (
                  <option key={img.value} value={img.value}>
                    {img.label} ({img.value})
                  </option>
                ))}
              </select>
              <input
                type="text"
                value={customImage}
                onChange={(e) => setCustomImage(e.target.value)}
                placeholder="Or enter custom container image (e.g. ubuntu:22.04)"
                style={{
                  width: '100%',
                  height: '30px',
                  padding: '0 10px',
                  borderRadius: '4px',
                  border: '1px solid var(--color-border)',
                  background: 'var(--color-surface)',
                  color: 'var(--color-text)',
                  fontSize: '11px',
                }}
              />
            </div>

            {/* Exposed Ports */}
            <div>
              <label style={{ display: 'block', fontSize: '12px', fontWeight: 600, color: 'var(--color-text)', marginBottom: '6px' }}>
                Exposed Ports (comma separated)
              </label>
              <input
                type="text"
                value={ports}
                onChange={(e) => setPorts(e.target.value)}
                placeholder="8080, 8501, 3000"
                style={{
                  width: '100%',
                  height: '32px',
                  padding: '0 10px',
                  borderRadius: '4px',
                  border: '1px solid var(--color-border)',
                  background: 'var(--color-surface)',
                  color: 'var(--color-text)',
                  fontSize: '12px',
                }}
              />
            </div>

            {/* Optional Init Script */}
            <div>
              <label style={{ display: 'block', fontSize: '12px', fontWeight: 600, color: 'var(--color-text)', marginBottom: '6px' }}>
                Initial Startup Command (Optional)
              </label>
              <input
                type="text"
                value={initCommand}
                onChange={(e) => setInitCommand(e.target.value)}
                placeholder="e.g., pip install fastapi uvicorn"
                style={{
                  width: '100%',
                  height: '32px',
                  padding: '0 10px',
                  borderRadius: '4px',
                  border: '1px solid var(--color-border)',
                  background: 'var(--color-surface)',
                  color: 'var(--color-text)',
                  fontSize: '12px',
                  fontFamily: 'monospace',
                }}
              />
            </div>

            {/* Error Message */}
            {error && (
              <div
                style={{
                  padding: '8px 12px',
                  background: 'rgba(239, 68, 68, 0.1)',
                  border: '1px solid #ef4444',
                  borderRadius: '4px',
                  color: '#ef4444',
                  fontSize: '12px',
                }}
              >
                {error}
              </div>
            )}

            {/* Form Actions */}
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px', paddingTop: '8px' }}>
              <button
                type="button"
                className="compute-secondary-btn"
                onClick={onClose}
                disabled={loading}
              >
                Cancel
              </button>
              <button
                type="submit"
                className="compute-primary-btn"
                disabled={loading}
              >
                {loading ? 'Provisioning...' : 'Provision Sandbox'}
              </button>
            </div>
          </form>
        </div>
      </div>
    </>
  );
}

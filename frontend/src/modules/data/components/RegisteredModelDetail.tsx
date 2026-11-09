import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Loader2, Package } from 'lucide-react';
import api from '@/lib/api';

export interface CatalogModelAlias {
  alias: string;
  version: number;
}

export interface CatalogModelVersion {
  version: number;
  run_id: string | null;
  source: string;
  artifact_path: string;
  status: string;
  comment: string | null;
  storage_location: string | null;
  files: string[];
  metrics: Record<string, number | string>;
  params: Record<string, string | number>;
  aliases: string[];
  created_by: string;
  created_at: string;
}

export interface CatalogRegisteredModel {
  id: string;
  catalog_name: string;
  schema_name: string;
  name: string;
  full_name: string;
  comment: string | null;
  owner: string;
  storage_location: string | null;
  created_at: string;
  updated_at: string;
  created_by: string;
  updated_by: string;
  aliases: CatalogModelAlias[];
  versions: CatalogModelVersion[];
  latest_version?: number | null;
}

interface Props {
  catalog: string;
  schema: string;
  name: string;
}

export default function RegisteredModelDetail({ catalog, schema, name }: Props) {
  const queryClient = useQueryClient();
  const [aliasName, setAliasName] = useState('champion');
  const [aliasVersion, setAliasVersion] = useState('');
  const [message, setMessage] = useState<string | null>(null);

  const modelQuery = useQuery({
    queryKey: ['uc-model', catalog, schema, name],
    queryFn: () =>
      api
        .get<CatalogRegisteredModel>(
          `/catalog/catalogs/${encodeURIComponent(catalog)}/schemas/${encodeURIComponent(schema)}/models/${encodeURIComponent(name)}`,
        )
        .then((response) => response.data),
  });

  const aliasMutation = useMutation({
    mutationFn: () =>
      api.put(
        `/catalog/catalogs/${encodeURIComponent(catalog)}/schemas/${encodeURIComponent(schema)}/models/${encodeURIComponent(name)}/aliases/${encodeURIComponent(aliasName)}`,
        { alias: aliasName, version: Number(aliasVersion) },
      ),
    onSuccess: () => {
      setMessage(`Alias ${aliasName} now points at version ${aliasVersion}.`);
      queryClient.invalidateQueries({ queryKey: ['uc-model', catalog, schema, name] });
      queryClient.invalidateQueries({ queryKey: ['uc-schema-models', catalog, schema] });
    },
    onError: (error: any) => {
      setMessage(error?.response?.data?.detail || 'Could not set the alias.');
    },
  });

  if (modelQuery.isLoading) {
    return (
      <div className="uc-empty-state">
        <Loader2 size={24} className="spin" />
        <p>Loading model...</p>
      </div>
    );
  }
  if (!modelQuery.data) {
    return <div className="uc-empty-state"><p>This model is not in the catalog.</p></div>;
  }

  const model = modelQuery.data;
  const latest = model.versions[0];

  return (
    <div className="uc-panel">
      <div className="uc-panel-header-row">
        <div className="uc-panel-header-title">
          <Package size={22} className="text-primary" />
          <h2>{model.full_name}</h2>
        </div>
      </div>
      <div className="uc-tab-content">
        <div className="uc-detail-grid">
          <section className="uc-card">
            <h3>Model</h3>
            <p>{model.comment || 'Registered from an MLflow run into this catalog schema.'}</p>
            <dl>
              <dt>Owner</dt>
              <dd>{model.owner}</dd>
              <dt>Storage</dt>
              <dd>{model.storage_location || '—'}</dd>
              <dt>Aliases</dt>
              <dd>
                {model.aliases.length
                  ? model.aliases.map((item) => `${item.alias} → v${item.version}`).join(', ')
                  : 'None'}
              </dd>
            </dl>
          </section>
          {latest && (
            <section className="uc-card">
              <h3>Latest version {latest.version}</h3>
              <p>Status {latest.status}. Source {latest.source}.</p>
              <dl>
                {Object.entries(latest.metrics).map(([key, value]) => (
                  <span key={key}>
                    <dt>{key}</dt>
                    <dd>{String(value)}</dd>
                  </span>
                ))}
              </dl>
            </section>
          )}
        </div>

        <section className="uc-card" style={{ marginTop: 16 }}>
          <h3>Versions</h3>
          <table className="uc-assets-table">
            <thead>
              <tr>
                <th>Version</th>
                <th>Status</th>
                <th>Aliases</th>
                <th>Run</th>
                <th>Created</th>
              </tr>
            </thead>
            <tbody>
              {model.versions.map((version) => (
                <tr key={version.version}>
                  <td>{version.version}</td>
                  <td>{version.status}</td>
                  <td>{version.aliases.join(', ') || '—'}</td>
                  <td style={{ fontFamily: 'monospace', fontSize: 11 }}>{version.run_id || '—'}</td>
                  <td>{new Date(version.created_at).toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>

        <section className="uc-card" style={{ marginTop: 16 }}>
          <h3>Set alias</h3>
          <form
            onSubmit={(event) => {
              event.preventDefault();
              aliasMutation.mutate();
            }}
            style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}
          >
            <input value={aliasName} onChange={(event) => setAliasName(event.target.value)} placeholder="champion" />
            <input value={aliasVersion} onChange={(event) => setAliasVersion(event.target.value)} placeholder="Version" />
            <button type="submit" className="btn-primary" disabled={aliasMutation.isPending || !aliasName || !aliasVersion}>
              Save alias
            </button>
          </form>
          {message && <p>{message}</p>}
        </section>
      </div>
    </div>
  );
}

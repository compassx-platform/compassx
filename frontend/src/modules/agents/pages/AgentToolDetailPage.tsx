import { Wrench } from "lucide-react";
import { useParams } from "react-router-dom";
import { AppTable, type AppTableColumn } from "@/components/common/AppTable";
import { useScopedNavigate } from "@/lib/appNavigation";
import { getAvailableTool, type AtomicToolInfo } from "@/modules/agents/toolCatalog";

export default function AgentToolDetailPage() {
  const navigate = useScopedNavigate();
  const { toolKey } = useParams();
  const tool = getAvailableTool(toolKey);

  const atomicColumns: AppTableColumn<AtomicToolInfo>[] = [
    {
      key: "name",
      header: "Atomic Tool",
      width: "30%",
      render: (atomicTool) => (
        <div>
          <div style={{ fontWeight: 500, fontSize: "0.875rem" }}>{atomicTool.name}</div>
          <div style={{ fontSize: "0.72rem", color: "var(--color-text-muted)", marginTop: 1 }}>{atomicTool.key}</div>
        </div>
      ),
    },
    {
      key: "description",
      header: "Description",
      render: (atomicTool) => <span style={{ color: "var(--color-text-muted)" }}>{atomicTool.description}</span>,
    },
  ];

  if (!tool) {
    return (
      <div className="page-section agents-page">
        <div className="asset-import-breadcrumb" aria-label="Breadcrumb" style={{ marginBottom: 8 }}>
          <button type="button" onClick={() => navigate("/agents")} className="asset-breadcrumb-link">Agents</button>
          <span>/</span>
          <button type="button" onClick={() => navigate("/agents?tab=tools")} className="asset-breadcrumb-link">Tools</button>
          <span>/</span>
          <span className="asset-breadcrumb-current">Not Found</span>
        </div>
        <div className="page-header">
          <div>
            <h1 className="page-title">Tool Not Found</h1>
            <p className="page-subtitle">The requested tool is not available.</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="page-section agents-page">
      <div className="asset-import-breadcrumb" aria-label="Breadcrumb" style={{ marginBottom: 8 }}>
        <button type="button" onClick={() => navigate("/agents")} className="asset-breadcrumb-link">Agents</button>
        <span>/</span>
        <button type="button" onClick={() => navigate("/agents?tab=tools")} className="asset-breadcrumb-link">Tools</button>
        <span>/</span>
        <span className="asset-breadcrumb-current">{tool.name}</span>
      </div>

      <div className="page-header">
        <div>
          <h1 className="page-title">{tool.name}</h1>
          <p className="page-subtitle">{tool.key}</p>
        </div>
      </div>

      <section
        style={{
          border: "1px solid var(--color-border)",
          borderRadius: 8,
          background: "var(--color-surface)",
          padding: 16,
          marginBottom: 16,
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
          <Wrench size={16} color="var(--color-primary)" />
          <h2 style={{ fontSize: "1rem", margin: 0 }}>Description</h2>
        </div>
        <p style={{ fontSize: "0.9rem", color: "var(--color-text)", margin: 0 }}>
          {tool.description}
        </p>
      </section>

      <div style={{ marginBottom: 8, fontSize: "0.875rem", fontWeight: 600 }}>Atomic Tools</div>
      <AppTable
        columns={atomicColumns}
        rows={tool.atomicTools ?? []}
        rowKey={(atomicTool) => atomicTool.key}
        emptyText="This tool is available directly and does not expose grouped atomic tools."
      />
    </div>
  );
}

import React, { useState } from 'react';
import { X, Upload, RotateCcw, Check, AlertCircle, FileCode } from 'lucide-react';
import { DEFAULT_ONTOLOGY_YAML } from '../data/defaultOntologyData';

interface OntologyYamlEditorModalProps {
  isOpen: boolean;
  onClose: () => void;
  yamlContent: string;
  onApplyYaml: (newYaml: string) => boolean;
}

export const OntologyYamlEditorModal: React.FC<OntologyYamlEditorModalProps> = ({
  isOpen,
  onClose,
  yamlContent,
  onApplyYaml,
}) => {
  const [editorValue, setEditorValue] = useState(yamlContent);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  React.useEffect(() => {
    if (isOpen) {
      setEditorValue(yamlContent);
      setError(null);
      setSuccess(false);
    }
  }, [isOpen, yamlContent]);

  if (!isOpen) return null;

  const handleApply = () => {
    setError(null);
    try {
      const ok = onApplyYaml(editorValue);
      if (ok) {
        setSuccess(true);
        setTimeout(() => {
          setSuccess(false);
          onClose();
        }, 600);
      }
    } catch (err: any) {
      setError(err.message || 'Failed to parse YAML content');
    }
  };

  const handleReset = () => {
    setEditorValue(DEFAULT_ONTOLOGY_YAML);
    setError(null);
  };

  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = evt => {
      const text = evt.target?.result as string;
      if (text) {
        setEditorValue(text);
        setError(null);
      }
    };
    reader.readAsText(file);
  };

  return (
    <div className="ontology-modal-overlay fixed inset-0 z-50 flex items-center justify-center p-6 bg-black/70 backdrop-blur-sm animate-in fade-in duration-150">
      <div className="ontology-modal-content-lg w-full max-w-4xl h-[85vh] flex flex-col rounded-2xl bg-[#0f121d] border border-[#262e45] shadow-2xl overflow-hidden text-[#e2e8f0]">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-[#23293d] bg-[#141827]">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-xl bg-[#6366f1]/15 text-[#818cf8] border border-[#6366f1]/30">
              <FileCode size={18} />
            </div>
            <div>
              <h3 className="text-base font-bold text-white leading-tight">
                Ontology YAML Schema Editor
              </h3>
              <p className="text-xs text-[#64748b]">
                Modify nodes, domains, capabilities, and dependencies or upload local files.
              </p>
            </div>
          </div>

          <button onClick={onClose} className="p-1.5 rounded-lg hover:bg-[#20273c] text-[#94a3b8] hover:text-white">
            <X size={18} />
          </button>
        </div>

        {/* Toolbar */}
        <div className="flex items-center justify-between px-6 py-2.5 bg-[#121624] border-b border-[#20263c] text-xs">
          <div className="flex items-center gap-2">
            <label className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[#1a2033] hover:bg-[#252d47] text-[#cbd5e1] border border-[#2e3752] cursor-pointer transition-colors">
              <Upload size={13} />
              <span>Upload YAML file</span>
              <input type="file" accept=".yaml,.yml,.json" onChange={handleFileUpload} className="hidden" />
            </label>

            <button
              onClick={handleReset}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[#1a2033] hover:bg-[#252d47] text-[#94a3b8] hover:text-white border border-[#2e3752] transition-colors"
            >
              <RotateCcw size={13} />
              <span>Reset to Default</span>
            </button>
          </div>

          {error && (
            <div className="flex items-center gap-1.5 text-xs text-rose-400 font-medium">
              <AlertCircle size={14} />
              <span>{error}</span>
            </div>
          )}
        </div>

        {/* Editor Area */}
        <div className="flex-1 p-4 bg-[#090b12] overflow-hidden">
          <textarea
            value={editorValue}
            onChange={e => {
              setEditorValue(e.target.value);
              setError(null);
            }}
            spellCheck={false}
            className="w-full h-full p-4 font-mono text-xs leading-relaxed bg-[#0b0e17] text-[#e2e8f0] border border-[#20263a] rounded-xl focus:outline-none focus:border-[#6366f1] resize-none custom-scrollbar"
          />
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end gap-3 px-6 py-4 bg-[#141827] border-t border-[#23293d]">
          <button
            onClick={onClose}
            className="px-4 py-2 text-xs font-medium text-[#94a3b8] hover:text-white transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={handleApply}
            className="flex items-center gap-2 px-5 py-2 rounded-xl bg-[#6366f1] hover:bg-[#4f46e5] text-white text-xs font-semibold shadow-lg shadow-indigo-500/20 transition-all active:scale-[0.98]"
          >
            {success ? <Check size={14} /> : null}
            <span>{success ? 'Applied Successfully!' : 'Apply & Re-render Graph'}</span>
          </button>
        </div>
      </div>
    </div>
  );
};

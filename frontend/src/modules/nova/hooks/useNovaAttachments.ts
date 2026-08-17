import { useState, useEffect, useCallback } from 'react';
import { getAuthKey } from '@/lib/auth';

export interface NovaAttachmentRecord {
  file_id: string;
  session_id: number;
  filename: string;
  mime_type: string;
  size_bytes: number;
  status: 'processing' | 'ready' | 'failed' | 'purged';
  delivery_mode?: 'inline' | 'tool_fetch' | 'multimodal_native';
  extracted_token_count?: number;
  preview_text?: string;
  extraction_error?: string;
  promoted_object_id?: string;
  created_at?: string;
}

export function useNovaAttachments(sessionId: number | null) {
  const [attachments, setAttachments] = useState<NovaAttachmentRecord[]>([]);
  const [isUploading, setIsUploading] = useState(false);

  const getHeaders = useCallback(() => {
    const match = window.location.pathname.match(/^\/w\/([^/]+)/);
    const workspaceSlug = match ? match[1] : null;
    const authkey = getAuthKey();
    const headers: Record<string, string> = {};
    if (authkey) {
      headers.authkey = authkey;
      headers['Authorization'] = `Bearer ${authkey}`;
    }
    if (workspaceSlug) headers['X-Workspace-Slug'] = workspaceSlug;
    return headers;
  }, []);

  const fetchAttachments = useCallback(async () => {
    if (!sessionId) {
      setAttachments([]);
      return;
    }
    try {
      const baseUrl = (import.meta.env.VITE_API_BASE_URL || '/api/v1').replace(/\/$/, '');
      const res = await fetch(`${baseUrl}/nova/sessions/${sessionId}/attachments`, {
        headers: getHeaders(),
      });
      if (res.ok) {
        const data = await res.json();
        setAttachments(Array.isArray(data) ? data : []);
      }
    } catch (e) {
      console.error('Failed to fetch Nova attachments:', e);
    }
  }, [sessionId, getHeaders]);

  useEffect(() => {
    fetchAttachments();
  }, [fetchAttachments]);

  const uploadFiles = async (files: FileList | File[]) => {
    if (!sessionId || !files.length) return;
    setIsUploading(true);
    try {
      const baseUrl = (import.meta.env.VITE_API_BASE_URL || '/api/v1').replace(/\/$/, '');
      const formData = new FormData();
      Array.from(files).forEach((file) => formData.append('files', file));

      const res = await fetch(`${baseUrl}/nova/sessions/${sessionId}/attachments`, {
        method: 'POST',
        headers: getHeaders(),
        body: formData,
      });

      if (res.ok) {
        await fetchAttachments();
      } else {
        const err = await res.json();
        alert(`Upload failed: ${err.detail || 'Unknown error'}`);
      }
    } catch (e) {
      console.error('Error uploading attachments:', e);
      alert('Upload failed. Please check network connection.');
    } finally {
      setIsUploading(false);
    }
  };

  const removeAttachment = async (fileId: string) => {
    if (!sessionId) return;
    try {
      const baseUrl = (import.meta.env.VITE_API_BASE_URL || '/api/v1').replace(/\/$/, '');
      const res = await fetch(`${baseUrl}/nova/sessions/${sessionId}/attachments/${fileId}`, {
        method: 'DELETE',
        headers: getHeaders(),
      });
      if (res.ok) {
        setAttachments((prev) => prev.filter((item) => item.file_id !== fileId));
      }
    } catch (e) {
      console.error('Error deleting attachment:', e);
    }
  };

  const promoteAttachment = async (fileId: string, targetCatalogPath: string) => {
    try {
      const baseUrl = (import.meta.env.VITE_API_BASE_URL || '/api/v1').replace(/\/$/, '');
      const headers = { ...getHeaders(), 'Content-Type': 'application/json' };
      const res = await fetch(`${baseUrl}/nova/attachments/${fileId}/promote`, {
        method: 'POST',
        headers,
        body: JSON.stringify({ target_catalog_path: targetCatalogPath }),
      });
      if (res.ok) {
        await fetchAttachments();
        return true;
      }
    } catch (e) {
      console.error('Error promoting attachment:', e);
    }
    return false;
  };

  return {
    attachments,
    isUploading,
    uploadFiles,
    removeAttachment,
    promoteAttachment,
    refetchAttachments: fetchAttachments,
  };
}

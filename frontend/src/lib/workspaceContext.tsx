/**
 * WorkspaceContext — provides the active workspace slug + metadata
 * derived from the /w/:workspaceSlug URL prefix.
 */
import { createContext, useContext } from "react";

export interface WorkspaceInfo {
  id: string;
  name: string;
  slug: string;
  status: string;
  current_user_role: string;
  is_account_admin: boolean;
}

export const WorkspaceContext = createContext<WorkspaceInfo | null>(null);

export function useWorkspaceContext(): WorkspaceInfo {
  const ctx = useContext(WorkspaceContext);
  if (!ctx) throw new Error("useWorkspaceContext called outside WorkspaceProvider");
  return ctx;
}

/** Message the portal sends into an embedded app. The token stays out of the iframe URL. */
export const COMPASSX_USER_CONTEXT = 'compassx.user-context';
export const COMPASSX_USER_CONTEXT_REQUEST = 'compassx.user-context.request';

export interface CompassxUserContextMessage {
  type: typeof COMPASSX_USER_CONTEXT;
  accessToken: string;
  workspaceId: string;
  workspaceSlug: string;
}

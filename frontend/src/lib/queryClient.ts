import { QueryClient } from "@tanstack/react-query";

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 0,
      gcTime: 0,
      refetchOnWindowFocus: true,
    },
  },
});

export function purgeAllClientState(): void {
  try {
    // 1. Clear TanStack Query cache in memory
    queryClient.clear();
    queryClient.resetQueries();

    // 2. Clear localStorage auth items
    localStorage.removeItem("um_access_token");
    localStorage.removeItem("um_refresh_token");
    localStorage.removeItem("um_principal_info");

    // 3. Clear sessionStorage
    sessionStorage.clear();
  } catch (e) {
    console.error("Error purging client state", e);
  }
}

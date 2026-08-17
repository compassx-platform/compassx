/** React hooks for asset-related data fetching */

import { useQuery } from '@tanstack/react-query';
import api from '@/lib/api';
import type { AssetType, Asset, PaginatedResponse } from '@/types';

export function useAssetTypes() {
  return useQuery({
    queryKey: ['asset-types'],
    queryFn: async () => {
      const { data } = await api.get<PaginatedResponse<AssetType>>('/proxy/asset-types');
      return data.items || [];
    },
    staleTime: 5 * 60 * 1000,
  });
}

export function useAssets(assetTypeId?: number) {
  return useQuery({
    queryKey: ['assets', assetTypeId],
    queryFn: async () => {
      const params: Record<string, string> = {};
      if (assetTypeId) params.asset_type_id = String(assetTypeId);
      const { data } = await api.get<PaginatedResponse<Asset>>('/proxy/assets', { params });
      return data.items || [];
    },
    enabled: !!assetTypeId,
    staleTime: 5 * 60 * 1000,
  });
}

export function useAllAssets() {
  return useQuery({
    queryKey: ['assets', 'all'],
    queryFn: async () => {
      const { data } = await api.get<PaginatedResponse<Asset>>('/proxy/assets', {
        params: { size: 1000 },
      });
      return data.items || [];
    },
    staleTime: 5 * 60 * 1000,
  });
}

export function useChildAssets(parentAssetId?: number) {
  return useQuery({
    queryKey: ['child-assets', parentAssetId],
    queryFn: async () => {
      const { data } = await api.post<PaginatedResponse<{
        asset_id: number;
        asset_name: string;
        asset_type: string;
        ancestor_asset_id: number;
      }>>('/proxy/child-assets', {
        ancestor_asset_ids: parentAssetId ? [parentAssetId] : [],
      });
      return data.items || [];
    },
    enabled: !!parentAssetId,
    staleTime: 5 * 60 * 1000,
  });
}

/**
 * Fetch all assets and filter by asset type name.
 * Used by async_select fields with data_source.filter_by_type_name.
 */
export function useAssetsByTypeName(typeName?: string) {
  return useQuery({
    queryKey: ['assets', 'by-type-name', typeName],
    queryFn: async () => {
      const { data } = await api.get<PaginatedResponse<Asset>>('/proxy/assets', {
        params: { size: 1000 },
      });
      const items = data.items || [];
      if (typeName) {
        return items.filter((a) => a.asset_type_asset?.name === typeName);
      }
      return items;
    },
    enabled: !!typeName,
    staleTime: 5 * 60 * 1000,
  });
}
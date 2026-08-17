/** React hooks for form schemas */

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import api from '@/lib/api';
import type { FormSchema } from '@/types';

export function useForms() {
  return useQuery({
    queryKey: ['forms'],
    queryFn: async () => {
      const { data } = await api.get<{id: number, form_id: string, entity_name: string, schema: FormSchema}[]>('/forms');
      return data;
    },
    staleTime: 5 * 60 * 1000,
  });
}

export function useFormSchema(formId: string) {
  return useQuery({
    queryKey: ['form', formId],
    queryFn: async () => {
      const { data } = await api.get<{ schema: FormSchema }>(`/forms/${formId}`);
      return data.schema;
    },
    enabled: Boolean(formId),
    staleTime: 10 * 60 * 1000,
  });
}

export function useCreateForm() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (payload: { form_id: string; entity_name: string; schema: FormSchema }) => {
      const { data } = await api.post('/forms', payload);
      return data;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['forms'] }),
  });
}

export function useUpdateForm() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ form_id, payload }: { form_id: string; payload: { entity_name?: string; schema?: FormSchema } }) => {
      const { data } = await api.put(`/forms/${form_id}`, payload);
      return data;
    },
    onSuccess: (_, { form_id }) => {
      qc.invalidateQueries({ queryKey: ['forms'] });
      qc.invalidateQueries({ queryKey: ['form', form_id] });
    },
  });
}

export function useDeleteForm() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (form_id: string) => {
      await api.delete(`/forms/${form_id}`);
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['forms'] }),
  });
}

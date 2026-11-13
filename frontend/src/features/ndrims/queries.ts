import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ApiError, api, type Schemas, unwrap } from '@/api/client'
import type { NdrimsPayload } from './bookmarklet'

export type MyCourses = Schemas['MyCoursesOut']
export type OfferingGroup = Schemas['OfferingGroupOut']

/** 내 강좌(수강 기록으로 들어갈 수 있는 강좌)와 아직 열리지 않은 수업 */
export const useMyCourses = () =>
  useQuery({ queryKey: ['me', 'courses'], queryFn: () => unwrap(api.GET('/api/v1/me/courses')) })

/** 엔드림스에서 받은 기록을 저장한다. 관리자가 보낸 개설 목록도 함께 저장한다. */
export function useImportNdrims(isAdmin: boolean) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (p: NdrimsPayload) => {
      // 둘은 따로 저장한다. 개설 목록이 실패해도 내 수강 기록은 저장되게
      const [catalog, mine] = await Promise.allSettled([
        isAdmin && p.catalog.length
          ? unwrap(
              api.POST('/api/v1/admin/catalog/import', {
                body: { rows: p.catalog as Schemas['OfferingIn'][] },
              }),
            )
          : Promise.resolve(null),
        p.records.length
          ? unwrap(api.POST('/api/v1/me/ndrims/import', { body: { records: p.records } }))
          : Promise.resolve(null),
      ])
      if (mine.status === 'rejected') throw mine.reason
      if (catalog.status === 'rejected' && !mine.value) throw catalog.reason
      return {
        catalog: catalog.status === 'fulfilled' ? catalog.value : null,
        catalogError: catalog.status === 'rejected' ? (catalog.reason as Error) : null,
        mine: mine.value,
      }
    },
    onSuccess: () => qc.invalidateQueries(),
  })
}

export const useTerms = () =>
  useQuery({
    queryKey: ['catalog', 'terms'],
    queryFn: () => unwrap(api.GET('/api/v1/catalog/terms')),
  })

export const useFilters = (year?: string, sem_cd?: string) =>
  useQuery({
    queryKey: ['catalog', 'filters', year, sem_cd],
    enabled: !!year && !!sem_cd,
    queryFn: () =>
      unwrap(
        api.GET('/api/v1/catalog/filters', { params: { query: { year: year!, sem_cd: sem_cd! } } }),
      ),
  })

export type SearchQuery = {
  year: string
  sem_cd: string
  colg?: string
  dpt?: string
  cpdiv?: string
  q?: string
  prof?: string
  offset?: number
}

export const useCatalogSearch = (q: SearchQuery | null) =>
  useQuery({
    queryKey: ['catalog', 'search', q],
    enabled: !!q,
    placeholderData: keepPreviousData,
    queryFn: () =>
      unwrap(
        api.GET('/api/v1/catalog/search', {
          params: {
            query: {
              ...q!,
              colg: q!.colg || undefined,
              dpt: q!.dpt || undefined,
              cpdiv: q!.cpdiv || undefined,
            },
          },
        }),
      ),
  })

/** 수강 기록이 없어 막힌 경우(403) */
export const isForbidden = (e: Error | null) => e instanceof ApiError && e.status === 403

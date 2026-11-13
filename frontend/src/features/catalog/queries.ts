import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { api, type Schemas, unwrap } from '@/api/client'

export type OfferingGroup = Schemas['OfferingGroupOut']

/** 개설 목록(엔드림스 종합강의시간표) 학기·필터·검색 */
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

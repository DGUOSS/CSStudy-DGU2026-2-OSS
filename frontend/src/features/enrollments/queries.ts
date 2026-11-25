import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ApiError, api, type Schemas, unwrap } from '@/api/client'
import type { NdrimsPayload } from './bookmarklet'

export type MyCourses = Schemas['MyCoursesOut']

/** 내 강좌(수강 기록으로 들어갈 수 있는 강좌)와 아직 열리지 않은 수업 */
export const useMyCourses = () =>
  useQuery({ queryKey: ['me', 'courses'], queryFn: () => unwrap(api.GET('/api/v1/me/courses')) })

/** 엔드림스에서 받은 기록을 저장한다. 관리자가 보낸 개설 목록도 함께 저장한다. */
export function useImportNdrims(isAdmin: boolean) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (p: NdrimsPayload) => {
      // 학기 여러 개를 합치면 서버의 30,000행 제한을 넘을 수 있어 순차 저장한다.
      const importCatalog = async () => {
        if (!isAdmin || !p.catalog.length) return null
        const total: Schemas['CatalogImportOut'] = {
          terms: [], added: 0, updated: 0, professors_linked: 0, records_linked: 0,
        }
        let saved = 0
        for (let offset = 0; offset < p.catalog.length; offset += 5000) {
          try {
            const result = await unwrap(api.POST('/api/v1/admin/catalog/import', {
              body: { rows: p.catalog.slice(offset, offset + 5000) as Schemas['OfferingIn'][] },
            }))
            total.terms = [...new Set([...total.terms, ...result.terms])]
            total.added += result.added
            total.updated += result.updated
            total.professors_linked += result.professors_linked
            total.records_linked += result.records_linked
            saved += Math.min(5000, p.catalog.length - offset)
          } catch (e) {
            throw new Error(`${p.catalog.length}건 중 ${saved}건 저장 후 중단되었습니다. 다시 가져오면 중복 없이 갱신됩니다. ${e instanceof Error ? e.message : ''}`)
          }
        }
        return total
      }
      // 둘은 따로 저장한다. 개설 목록이 실패해도 내 수강 기록은 저장되게
      const adminSave = async () => {
        const catalog = await importCatalog()
        // 계획서 판정은 개설 목록 행에 붙으므로 개설 목록을 먼저 저장한다
        const syllabi = p.syllabi?.length
          ? await unwrap(api.POST('/api/v1/admin/catalog/syllabi', { body: { rows: p.syllabi } }))
          : null
        return { catalog, syllabi }
      }
      const [admin, mine] = await Promise.allSettled([
        isAdmin && (p.catalog.length || p.syllabi?.length) ? adminSave() : Promise.resolve(null),
        p.records.length
          ? unwrap(api.POST('/api/v1/me/ndrims/import', { body: { records: p.records } }))
          : Promise.resolve(null),
      ])
      if (mine.status === 'rejected') throw mine.reason
      if (admin.status === 'rejected' && !mine.value) throw admin.reason
      return {
        catalog: admin.status === 'fulfilled' ? (admin.value?.catalog ?? null) : null,
        syllabi: admin.status === 'fulfilled' ? (admin.value?.syllabi ?? null) : null,
        catalogError: admin.status === 'rejected' ? (admin.reason as Error) : null,
        mine: mine.value,
      }
    },
    onSuccess: () => qc.invalidateQueries(),
  })
}

/** 수강 기록이 없어 막힌 경우(403) */
export const isForbidden = (e: Error | null) => e instanceof ApiError && e.status === 403

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api, type Schemas, unwrap } from '@/api/client'

export type PaperSummary = Schemas['PaperSummary']
export type Paper = Schemas['PaperOut']
export type Take = Schemas['TakeOut']
export type Scan = Schemas['ScanOut']
export type Result = Schemas['ResultOut']

export const usePapers = (courseId: number) =>
  useQuery({
    queryKey: ['courses', courseId, 'papers'],
    queryFn: () =>
      unwrap(
        api.GET('/api/v1/courses/{course_id}/papers', {
          params: { path: { course_id: courseId } },
        }),
      ),
  })

export const usePaper = (paperId: number) =>
  useQuery({
    queryKey: ['papers', paperId],
    queryFn: () =>
      unwrap(api.GET('/api/v1/papers/{paper_id}', { params: { path: { paper_id: paperId } } })),
  })

export const useSheet = (paperId: number) =>
  useQuery({
    queryKey: ['papers', paperId, 'sheet'],
    queryFn: () =>
      unwrap(
        api.GET('/api/v1/papers/{paper_id}/sheet', { params: { path: { paper_id: paperId } } }),
      ),
  })

export const useMine = (paperId: number) =>
  useQuery({
    queryKey: ['papers', paperId, 'mine'],
    queryFn: () =>
      unwrap(
        api.GET('/api/v1/papers/{paper_id}/mine', { params: { path: { paper_id: paperId } } }),
      ),
  })

export const useRanking = (paperId: number) =>
  useQuery({
    queryKey: ['papers', paperId, 'ranking'],
    queryFn: () =>
      unwrap(
        api.GET('/api/v1/papers/{paper_id}/ranking', { params: { path: { paper_id: paperId } } }),
      ),
  })

export const useTakeResult = (takeId: number | null) =>
  useQuery({
    queryKey: ['takes', takeId, 'result'],
    enabled: takeId != null,
    queryFn: () =>
      unwrap(api.GET('/api/v1/takes/{take_id}/result', { params: { path: { take_id: takeId! } } })),
  })

export function useCreatePaper(courseId: number) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: Schemas['PaperIn']) =>
      unwrap(
        api.POST('/api/v1/courses/{course_id}/papers', {
          params: { path: { course_id: courseId } },
          body,
        }),
      ),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['courses', courseId, 'papers'] }),
  })
}

export function useStartTake(paperId: number) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: () =>
      unwrap(
        api.POST('/api/v1/papers/{paper_id}/takes', { params: { path: { paper_id: paperId } } }),
      ),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['papers', paperId, 'mine'] }),
  })
}

export function useScan(takeId: number) {
  return useMutation({
    mutationFn: (files: File[]) => {
      const form = new FormData()
      for (const f of files) form.append('files', f)
      return unwrap(
        api.POST('/api/v1/takes/{take_id}/scan', {
          params: { path: { take_id: takeId } },
          // multipart는 openapi-fetch가 타입으로 표현하지 못해서 FormData를 그대로 보낸다
          body: form as never,
          bodySerializer: (b) => b as unknown as FormData,
        }),
      )
    },
  })
}

export function useSubmit(takeId: number, paperId: number) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: Schemas['SubmitIn']) =>
      unwrap(
        api.POST('/api/v1/takes/{take_id}/submit', { params: { path: { take_id: takeId } }, body }),
      ),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['papers', paperId] })
      qc.invalidateQueries({ queryKey: ['courses'] })
    },
  })
}

function useTakeAction(paperId: number, action: 'pause' | 'resume' | 'abandon' | 'restart') {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (takeId: number) =>
      unwrap(
        api.POST(`/api/v1/takes/{take_id}/${action}`, { params: { path: { take_id: takeId } } }),
      ),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['papers', paperId, 'mine'] })
      qc.invalidateQueries({ queryKey: ['courses'] })
    },
  })
}
export const usePause = (paperId: number) => useTakeAction(paperId, 'pause')
export const useResume = (paperId: number) => useTakeAction(paperId, 'resume')
export const useAbandon = (paperId: number) => useTakeAction(paperId, 'abandon')
export const useRestart = (paperId: number) => useTakeAction(paperId, 'restart')

export const mmss = (sec: number) => {
  const s = Math.max(0, Math.floor(sec))
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`
}

import { api, unwrap } from '@/api/client'

/** 강좌 열기 요청에 교안 PDF를 붙인다(요청한 사람 또는 관리자) */
export function uploadRequestFiles(requestId: number, files: File[]) {
  const form = new FormData()
  for (const f of files) form.append('files', f)
  return unwrap(
    api.POST('/api/v1/course-requests/{request_id}/files', {
      params: { path: { request_id: requestId } },
      // multipart는 openapi-fetch가 타입으로 표현하지 못해서 FormData를 그대로 보낸다
      body: form as never,
      bodySerializer: (b) => b as unknown as FormData,
    }),
  )
}

import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Paperclip } from 'lucide-react'
import { useRef } from 'react'
import { api, unwrap } from '@/api/client'
import { ErrorText } from '@/components/States'
import { Button } from '@/components/ui/button'

/** 대기 중인 강좌 열기 요청에 교안 PDF를 붙인다(요청한 사람 또는 관리자). 교안이 있어야 승인된다. */
export function AttachFiles({ requestId }: { requestId: number }) {
  const qc = useQueryClient()
  const ref = useRef<HTMLInputElement>(null)
  const attach = useMutation({
    mutationFn: (files: FileList) => {
      const form = new FormData()
      for (const f of Array.from(files)) form.append('files', f)
      return unwrap(
        api.POST('/api/v1/course-requests/{request_id}/files', {
          params: { path: { request_id: requestId } },
          // multipart는 openapi-fetch가 타입으로 표현하지 못해서 FormData를 그대로 보낸다
          body: form as never,
          bodySerializer: (b) => b as unknown as FormData,
        }),
      )
    },
    onSuccess: () => {
      if (ref.current) ref.current.value = ''
      qc.invalidateQueries({ queryKey: ['course-requests'] })
    },
  })
  return (
    <div className="flex flex-col gap-1">
      <input
        ref={ref}
        type="file"
        accept="application/pdf,.pdf"
        multiple
        className="hidden"
        onChange={(e) => e.target.files?.length && attach.mutate(e.target.files)}
      />
      <Button
        size="sm"
        variant="outline"
        disabled={attach.isPending}
        onClick={() => ref.current?.click()}
      >
        <Paperclip />
        {attach.isPending ? '올리는 중…' : '교안 PDF 붙이기'}
      </Button>
      <ErrorText error={attach.error} />
    </div>
  )
}

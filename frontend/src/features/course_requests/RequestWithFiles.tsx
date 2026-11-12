import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { ErrorText } from '@/components/States'
import { Button } from '@/components/ui/button'
import { uploadRequestFiles } from './upload'

/**
 * '열어 달라고 요청' 버튼. 누르면 교안 PDF를 같이 올릴 수 있는 칸이 열린다(선택).
 * create는 요청을 만들고 요청 번호를 돌려준다.
 */
export function RequestWithFiles({
  label,
  create,
  disabled,
  title,
}: {
  label: string
  create: () => Promise<number>
  disabled?: boolean
  title?: string
}) {
  const qc = useQueryClient()
  const [open, setOpen] = useState(false)
  const [files, setFiles] = useState<File[]>([])
  const send = useMutation({
    mutationFn: async () => {
      const id = await create()
      if (files.length) await uploadRequestFiles(id, files)
    },
    onSuccess: () => {
      setOpen(false)
      setFiles([])
      qc.invalidateQueries()
    },
  })

  if (!open)
    return (
      <Button
        size="sm"
        variant="outline"
        disabled={disabled}
        title={title}
        onClick={() => setOpen(true)}
      >
        {label}
      </Button>
    )

  return (
    <div className="flex w-full max-w-sm flex-col gap-2 rounded-lg border bg-muted/30 p-3 text-sm">
      <p className="text-muted-foreground">
        교안 PDF가 있으면 같이 올려 주세요(선택). 교안이 붙어야 관리자가 강좌를 열 수 있고, 나중에
        &lsquo;내 요청&rsquo;에서 붙여도 됩니다.
      </p>
      <input
        type="file"
        accept="application/pdf,.pdf"
        multiple
        className="text-xs"
        onChange={(e) => setFiles(Array.from(e.target.files ?? []))}
      />
      <div className="flex gap-2">
        <Button size="sm" disabled={send.isPending} onClick={() => send.mutate()}>
          {send.isPending
            ? '보내는 중…'
            : files.length
              ? `교안 ${files.length}개와 함께 요청`
              : '교안 없이 요청'}
        </Button>
        <Button size="sm" variant="ghost" disabled={send.isPending} onClick={() => setOpen(false)}>
          취소
        </Button>
      </div>
      <ErrorText error={send.error} />
    </div>
  )
}

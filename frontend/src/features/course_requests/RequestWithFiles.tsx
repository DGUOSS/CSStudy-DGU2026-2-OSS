import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Send } from 'lucide-react'
import { useRef, useState } from 'react'
import { PdfPicker } from '@/components/PdfPicker'
import { ErrorText } from '@/components/States'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { uploadRequestFiles } from './upload'

/**
 * '열어 달라고 요청' 버튼. 누르면 교안 PDF(선택)와 메모(선택)를 넣는 칸이 열린다.
 * create는 요청을 만들고 요청 번호를 돌려준다.
 */
export function RequestWithFiles({
  label,
  create,
  disabled,
  title,
}: {
  label: string
  create: (note: string) => Promise<number>
  disabled?: boolean
  title?: string
}) {
  const qc = useQueryClient()
  const [open, setOpen] = useState(false)
  const [files, setFiles] = useState<File[]>([])
  const [note, setNote] = useState('')
  // 요청은 만들어졌는데 교안 올리기가 실패한 경우, 다시 누르면 교안만 다시 올린다
  const made = useRef<number | null>(null)
  const send = useMutation({
    mutationFn: async () => {
      made.current ??= await create(note)
      if (files.length) await uploadRequestFiles(made.current, files)
    },
    onSuccess: () => {
      made.current = null
      setOpen(false)
      setFiles([])
      setNote('')
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
    <div className="flex w-full max-w-sm flex-col gap-3 rounded-lg border bg-muted/30 p-3 text-sm">
      <div>
        <div className="font-medium">교안 PDF (선택)</div>
        <p className="text-xs text-muted-foreground">
          교안이 붙어야 관리자가 강좌를 열 수 있습니다. 지금 없으면 나중에 &lsquo;내 요청&rsquo;에서
          붙여도 됩니다.
        </p>
      </div>
      <PdfPicker files={files} onChange={setFiles} />
      <Textarea
        value={note}
        onChange={(e) => setNote(e.target.value)}
        placeholder="관리자에게 남길 말 (선택)"
        className="h-16 text-sm"
      />
      <div className="flex gap-2">
        <Button size="sm" disabled={send.isPending} onClick={() => send.mutate()}>
          <Send />
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

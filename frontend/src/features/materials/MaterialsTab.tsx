import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { FileText, Upload } from 'lucide-react'
import { type FormEvent, useRef, useState } from 'react'
import { api, unwrap } from '@/api/client'
import { Empty, ErrorText, Loading } from '@/components/States'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { cn } from '@/lib/utils'
import { resultText } from './resultText'

const KIND_LABEL: Record<string, string> = {
  lecture: '교안',
  exam: '족보',
  note: '시험 정보',
}
const EMPTY_TEXT: Record<string, string> = {
  lecture: '아직 올라온 교안이 없습니다.',
  exam: '아직 올라온 족보(기출)가 없습니다.',
  note: '아직 올라온 시험 정보 자료가 없습니다.',
}
type Kind = 'lecture' | 'exam' | 'note'

export function MaterialsTab({ courseId }: { courseId: number }) {
  const materials = useQuery({
    queryKey: ['courses', courseId, 'materials'],
    queryFn: () =>
      unwrap(
        api.GET('/api/v1/courses/{course_id}/materials', {
          params: { path: { course_id: courseId } },
        }),
      ),
  })

  const [kind, setKind] = useState<Kind>('lecture')
  const shown = materials.data?.filter((m) => m.kind === kind) ?? []

  return (
    <div className="flex flex-col gap-5">
      <div className="flex gap-1 rounded-lg bg-muted p-1">
        {(Object.keys(KIND_LABEL) as Kind[]).map((k) => (
          <button
            key={k}
            type="button"
            onClick={() => setKind(k)}
            className={cn(
              'flex-1 cursor-pointer rounded-md px-3 py-1.5 text-sm font-medium',
              kind === k ? 'bg-card shadow-sm' : 'text-muted-foreground hover:text-foreground',
            )}
          >
            {KIND_LABEL[k]}
            {materials.data && (
              <span className="ml-1 text-xs text-muted-foreground">
                {materials.data.filter((m) => m.kind === k).length}
              </span>
            )}
          </button>
        ))}
      </div>
      {materials.isPending ? (
        <Loading />
      ) : shown.length === 0 ? (
        <Empty>{EMPTY_TEXT[kind]}</Empty>
      ) : (
        <ul className="flex flex-col divide-y rounded-xl border bg-card">
          {shown.map((m) => (
            <li key={m.id} className="flex items-center gap-3 px-4 py-3">
              <FileText className="size-4 shrink-0 text-muted-foreground" />
              <div className="min-w-0 flex-1">
                <div className="truncate text-sm font-medium">
                  {m.title}
                  {(m.version ?? 1) > 1 && (
                    <span className="ml-1.5 text-xs text-muted-foreground">{m.version}판</span>
                  )}
                </div>
                <div className="text-xs text-muted-foreground">
                  {m.filename} · {m.page_count}쪽{m.uploader_name && ` · ${m.uploader_name}`}
                </div>
              </div>
            </li>
          ))}
        </ul>
      )}
      <ErrorText error={materials.error} />
      <UploadForm courseId={courseId} kind={kind} />
    </div>
  )
}

/** kind를 주면 그 종류로만 올린다(자료 탭). 안 주면 종류를 고른다(관리 화면). */
export function UploadForm({ courseId, kind: fixedKind }: { courseId: number; kind?: Kind }) {
  const qc = useQueryClient()
  const fileRef = useRef<HTMLInputElement>(null)
  const [pickedKind, setKind] = useState<Kind>('lecture')
  const kind = fixedKind ?? pickedKind

  const upload = useMutation({
    mutationFn: (file: File) => {
      const form = new FormData()
      form.append('file', file)
      form.append('kind', kind)
      return unwrap(
        api.POST('/api/v1/courses/{course_id}/materials', {
          params: { path: { course_id: courseId } },
          // multipart는 openapi-fetch가 타입으로 표현하지 못해서 FormData를 그대로 보낸다
          body: form as never,
          bodySerializer: (b) => b as unknown as FormData,
        }),
      )
    },
    onSuccess: () => {
      if (fileRef.current) fileRef.current.value = ''
      qc.invalidateQueries({ queryKey: ['courses', courseId] })
      qc.invalidateQueries({ queryKey: ['subjects'] })
    },
  })

  const submit = (e: FormEvent) => {
    e.preventDefault()
    const file = fileRef.current?.files?.[0]
    if (file) upload.mutate(file)
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">
          {fixedKind ? `${KIND_LABEL[fixedKind]} 올리기` : '자료 올리기'}
        </CardTitle>
      </CardHeader>
      <CardContent>
        <form onSubmit={submit} className="grid gap-4">
          <p className="text-sm text-muted-foreground">
            이름은 자동으로 붙습니다(예: 과목명 족보 2). 새 판을 올리면 옛 판의 이름을 이어받습니다.
          </p>
          {!fixedKind && (
            <div className="grid gap-2">
              <Label>종류</Label>
              <div className="flex gap-2">
                {(Object.keys(KIND_LABEL) as Kind[]).map((k) => (
                  <Button
                    key={k}
                    type="button"
                    size="sm"
                    variant={kind === k ? 'default' : 'outline'}
                    onClick={() => setKind(k)}
                  >
                    {KIND_LABEL[k]}
                  </Button>
                ))}
              </div>
            </div>
          )}
          <div className="grid gap-2">
            <Label htmlFor="file">PDF 파일</Label>
            <Input id="file" ref={fileRef} type="file" accept="application/pdf,.pdf" required />
          </div>
          <ErrorText error={upload.error} />
          <div className="flex items-center gap-3">
            <Button type="submit" disabled={upload.isPending}>
              <Upload />
              {upload.isPending ? '올리는 중…' : '올리기'}
            </Button>
            {upload.data && (
              <span className="text-sm text-muted-foreground">{resultText(upload.data)}</span>
            )}
          </div>
        </form>
      </CardContent>
    </Card>
  )
}

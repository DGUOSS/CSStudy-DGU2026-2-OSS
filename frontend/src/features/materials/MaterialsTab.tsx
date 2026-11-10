import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { FileText, Upload } from 'lucide-react'
import { type FormEvent, useRef, useState } from 'react'
import { api, type Schemas, unwrap } from '@/api/client'
import { Empty, ErrorText, Loading } from '@/components/States'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'

const KIND_LABEL: Record<string, string> = { lecture: '교안', exam: '기출·족보', note: '시험 정보' }
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

  return (
    <div className="flex flex-col gap-5">
      {materials.isPending ? (
        <Loading />
      ) : materials.data?.length === 0 ? (
        <Empty>아직 자료가 없습니다. 교안이나 기출을 올려 주세요.</Empty>
      ) : (
        <ul className="flex flex-col divide-y rounded-xl border bg-card">
          {materials.data?.map((m) => (
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
              <Badge variant="outline">{KIND_LABEL[m.kind] ?? m.kind}</Badge>
            </li>
          ))}
        </ul>
      )}
      <ErrorText error={materials.error} />
      <UploadForm courseId={courseId} />
    </div>
  )
}

/** 판 관리 결과 안내 (쪽 내용 비교로 중복·새 판을 판단한다) */
function resultText(r: Schemas['UploadOut']): string {
  if (r.action === 'duplicate') return '이미 같은 내용의 자료가 있어 새로 올리지 않았습니다.'
  const pages = `같은 쪽 ${r.pages_same}, 수정된 쪽 ${r.pages_modified}, 새 쪽 ${r.pages_new}`
  const moved = r.relinked_problems ? ` 문제 ${r.relinked_problems}개의 근거를 새 자료로 옮겼습니다.` : ''
  if (r.action === 'updated')
    return `기존 자료 ${(r.replaced_ids ?? []).length}개를 새 판으로 바꿨습니다 (${pages}).${moved}`
  return `새 자료로 올렸습니다 (${pages}).${moved}`
}

function UploadForm({ courseId }: { courseId: number }) {
  const qc = useQueryClient()
  const fileRef = useRef<HTMLInputElement>(null)
  const [title, setTitle] = useState('')
  const [kind, setKind] = useState<Kind>('lecture')

  const upload = useMutation({
    mutationFn: (file: File) => {
      const form = new FormData()
      form.append('file', file)
      form.append('kind', kind)
      form.append('title', title)
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
      setTitle('')
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
        <CardTitle className="text-base">자료 올리기</CardTitle>
      </CardHeader>
      <CardContent>
        <form onSubmit={submit} className="grid gap-4">
          <div className="grid gap-2">
            <Label htmlFor="title">제목</Label>
            <Input
              id="title"
              placeholder="예: 10주차 포인터"
              required
              value={title}
              onChange={(e) => setTitle(e.target.value)}
            />
          </div>
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

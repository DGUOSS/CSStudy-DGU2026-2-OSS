import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { FileText, Upload } from 'lucide-react'
import { type FormEvent, useRef, useState } from 'react'
import { api, unwrap } from '@/api/client'
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
                <div className="truncate text-sm font-medium">{m.title}</div>
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
            {upload.isSuccess && (
              <span className="text-sm text-muted-foreground">
                올렸습니다. 이 자료로 문제를 만드는 기능은 준비 중입니다.
              </span>
            )}
          </div>
        </form>
      </CardContent>
    </Card>
  )
}

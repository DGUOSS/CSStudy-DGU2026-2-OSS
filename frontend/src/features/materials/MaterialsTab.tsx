import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { FileText, Upload } from 'lucide-react'
import { type FormEvent, useRef, useState } from 'react'
import { api, type Schemas, unwrap } from '@/api/client'
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
  const upload = useUpload(courseId, kind)

  return (
    <div className="flex flex-col gap-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div
          role="radiogroup"
          aria-label="자료 종류"
          className="inline-flex rounded-full border border-home-line bg-white p-1"
        >
          {(Object.keys(KIND_LABEL) as Kind[]).map((k) => (
            <button
              key={k}
              type="button"
              role="radio"
              aria-checked={kind === k}
              onClick={() => {
                setKind(k)
                upload.reset()
              }}
              className={cn(
                'h-10 cursor-pointer rounded-full px-4 text-sm font-bold',
                kind === k ? 'bg-navy-tint text-navy' : 'text-ink-2 hover:text-navy',
              )}
            >
              {KIND_LABEL[k]}
              {materials.data && <span className="ml-1">{materials.data.filter((m) => m.kind === k).length}</span>}
            </button>
          ))}
        </div>
        <UploadButton upload={upload} label={`${KIND_LABEL[kind]} PDF 올리기`} />
      </div>

      {upload.data && (
        <div role="status" className="rounded-2xl bg-navy-tint px-5 py-4 text-sm font-bold text-navy">
          {resultText(upload.data)}
        </div>
      )}
      <ErrorText error={upload.error} />

      {materials.isPending ? (
        <Loading />
      ) : shown.length === 0 ? (
        <Empty>{EMPTY_TEXT[kind]}</Empty>
      ) : (
        <MaterialList items={shown} />
      )}
      <ErrorText error={materials.error} />
      <p className="text-[13px] text-ink-2">
        PDF만 30MB까지 올릴 수 있어요. 이름은 자동으로 붙고(예: 과목명 족보 2), 새 판을 올리면 옛 판의 이름을
        이어받아요. 원본 파일은 저장하지 않고 쪽별 글만 저장해요.
      </p>
    </div>
  )
}

type Material = Schemas['MaterialOut']

function MaterialList({ items }: { items: Material[] }) {
  return (
    <ul className="overflow-hidden rounded-2xl border border-home-line bg-white">
      {items.map((m) => (
        <li key={m.id} className="flex items-center gap-3.5 border-b border-home-line px-5 py-3.5 last:border-0">
          <span className="flex size-11 shrink-0 items-center justify-center rounded-xl bg-tone-blue text-navy">
            <FileText size={20} aria-hidden="true" />
          </span>
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-[15px] font-bold">{m.title}</span>
              {(m.version ?? 1) > 1 && (
                <span className="rounded-full bg-gold-soft px-2 py-0.5 text-xs font-bold text-[#6b4a0c]">
                  새 판 v{m.version}
                </span>
              )}
            </div>
            <div className="truncate text-[13px] text-ink-2">
              {m.filename} · {m.page_count}쪽{m.uploader_name && ` · ${m.uploader_name}`} ·{' '}
              {new Date(m.created_at).toLocaleDateString('ko-KR', { month: 'long', day: 'numeric' })}
            </div>
          </div>
        </li>
      ))}
    </ul>
  )
}

/** 파일을 고르면 바로 올라가는 버튼 */
function UploadButton({ upload, label, small = false }: { upload: ReturnType<typeof useUpload>; label: string; small?: boolean }) {
  const fileRef = useRef<HTMLInputElement>(null)
  return (
    <label
      className={cn(
        'inline-flex shrink-0 cursor-pointer items-center gap-2 rounded-full font-bold focus-within:ring-2 focus-within:ring-navy/40',
        small
          ? 'h-10 border border-home-line bg-white px-4 text-sm text-navy hover:bg-navy-tint'
          : 'h-11 bg-navy px-5 text-[15px] text-white hover:bg-navy-deep',
        upload.isPending && 'pointer-events-none opacity-60',
      )}
    >
      <Upload size={16} aria-hidden="true" />
      {upload.isPending ? '올리는 중…' : label}
      <input
        ref={fileRef}
        type="file"
        accept="application/pdf,.pdf"
        className="sr-only"
        onChange={(e) => {
          const file = e.target.files?.[0]
          if (!file) return
          upload.mutate(file, {
            onSettled: () => {
              // 같은 파일을 다시 골라도 onChange가 오게 비운다
              if (fileRef.current) fileRef.current.value = ''
            },
          })
        }}
      />
    </label>
  )
}

/** 시험·평가 화면에서 쓰는 '시험 정보' 자료 칸: 목록 + 바로 올리기 (자료 화면의 '시험 정보'와 같은 데이터) */
export function ExamNotesPanel({ courseId }: { courseId: number }) {
  const materials = useQuery({
    queryKey: ['courses', courseId, 'materials'],
    queryFn: () =>
      unwrap(api.GET('/api/v1/courses/{course_id}/materials', { params: { path: { course_id: courseId } } })),
  })
  const upload = useUpload(courseId, 'note')
  const notes = materials.data?.filter((m) => m.kind === 'note') ?? []
  return (
    <section className="flex flex-col gap-3" aria-labelledby="exam-notes">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 id="exam-notes" className="text-lg font-bold">
            시험 정보 자료 <span className="text-[15px] font-normal text-ink-2">{notes.length}</span>
          </h2>
          <p className="text-[13px] text-ink-2">시험 범위·일정 공지 PDF를 올리면 모두가 같이 봐요.</p>
        </div>
        <UploadButton upload={upload} label="PDF 올리기" small />
      </div>
      {upload.data && (
        <div role="status" className="rounded-2xl bg-navy-tint px-5 py-3 text-sm font-bold text-navy">
          {resultText(upload.data)}
        </div>
      )}
      <ErrorText error={upload.error ?? materials.error} />
      {materials.isPending ? <Loading /> : notes.length === 0 ? <Empty>{EMPTY_TEXT.note}</Empty> : <MaterialList items={notes} />}
    </section>
  )
}

/** 자료 올리기 요청. 올리면 강좌 데이터(자료·챕터·문제 근거)를 다시 받는다. */
function useUpload(courseId: number, kind: Kind) {
  const qc = useQueryClient()
  return useMutation({
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
      qc.invalidateQueries({ queryKey: ['courses', courseId] })
      qc.invalidateQueries({ queryKey: ['subjects'] })
    },
  })
}

/** kind를 주면 그 종류로만 올린다(자료 탭). 안 주면 종류를 고른다(관리 화면). */
export function UploadForm({ courseId, kind: fixedKind }: { courseId: number; kind?: Kind }) {
  const fileRef = useRef<HTMLInputElement>(null)
  const [pickedKind, setKind] = useState<Kind>('lecture')
  const kind = fixedKind ?? pickedKind

  const upload = useUpload(courseId, kind)

  const submit = (e: FormEvent) => {
    e.preventDefault()
    const file = fileRef.current?.files?.[0]
    if (file)
      upload.mutate(file, {
        onSuccess: () => {
          if (fileRef.current) fileRef.current.value = ''
        },
      })
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

import { useMutation, useQueryClient } from '@tanstack/react-query'
import { ChevronLeft, Send } from 'lucide-react'
import { type FormEvent, useRef, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router'
import { api, unwrap } from '@/api/client'
import { ErrorText } from '@/components/States'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'

/** 없는 과목·강좌 추가 요청. 관리자가 승인하면 강좌가 생긴다. */
export function RequestCoursePage() {
  const [params] = useSearchParams()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const fileRef = useRef<HTMLInputElement>(null)
  const [subjectName, setSubjectName] = useState(params.get('subject') ?? '')
  const [subjectCode, setSubjectCode] = useState('')
  const [professorName, setProfessorName] = useState('')
  const [semester, setSemester] = useState('')
  const [note, setNote] = useState('')
  const [withMaterial, setWithMaterial] = useState(true)
  const [picked, setPicked] = useState<File[]>([])

  const send = useMutation({
    mutationFn: () => {
      const form = new FormData()
      form.append('subject_name', subjectName)
      form.append('professor_name', professorName)
      if (subjectCode) form.append('subject_code', subjectCode)
      if (semester) form.append('semester', semester)
      if (note) form.append('note', note)
      // 여러 파일을 함께 보낸다. 제목은 승인할 때 '과목명 교안 번호' 규칙으로 자동으로 붙는다.
      if (withMaterial) for (const f of picked) form.append('files', f)
      return unwrap(
        api.POST('/api/v1/course-requests', {
          // multipart는 openapi-fetch가 타입으로 표현하지 못해서 FormData를 그대로 보낸다
          body: form as never,
          bodySerializer: (b) => b as unknown as FormData,
        }),
      )
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['course-requests'] })
      navigate('/requests')
    },
  })

  const submit = (e: FormEvent) => {
    e.preventDefault()
    send.mutate()
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <Link to="/" className="mb-2 inline-flex items-center text-sm text-muted-foreground">
          <ChevronLeft className="size-4" />
          과목 목록
        </Link>
        <h1 className="text-2xl font-bold">과목·강좌 추가 요청</h1>
        <p className="text-sm text-muted-foreground">
          찾는 과목이나 교수님 강좌가 없으면 요청해 주세요. 관리자가 확인한 뒤 열립니다.
        </p>
      </div>
      <Card>
        <CardHeader>
          <CardTitle className="text-base">요청 내용</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={submit} className="grid gap-4">
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="grid gap-2">
                <Label htmlFor="subject">과목명</Label>
                <Input
                  id="subject"
                  required
                  placeholder="예: 자료구조"
                  value={subjectName}
                  onChange={(e) => setSubjectName(e.target.value)}
                />
              </div>
              <div className="grid gap-2">
                <Label htmlFor="code">학수번호 (선택)</Label>
                <Input
                  id="code"
                  placeholder="예: CSC2004"
                  value={subjectCode}
                  onChange={(e) => setSubjectCode(e.target.value)}
                />
              </div>
              <div className="grid gap-2">
                <Label htmlFor="prof">교수님 이름</Label>
                <Input
                  id="prof"
                  required
                  placeholder="예: 홍길동"
                  value={professorName}
                  onChange={(e) => setProfessorName(e.target.value)}
                />
              </div>
              <div className="grid gap-2">
                <Label htmlFor="semester">학기 (선택)</Label>
                <Input
                  id="semester"
                  placeholder="예: 2026-2"
                  value={semester}
                  onChange={(e) => setSemester(e.target.value)}
                />
              </div>
            </div>

            <div className="grid gap-2">
              <Label>교안</Label>
              <div className="flex gap-2">
                <Button
                  type="button"
                  size="sm"
                  variant={withMaterial ? 'default' : 'outline'}
                  onClick={() => setWithMaterial(true)}
                >
                  교안 올리기
                </Button>
                <Button
                  type="button"
                  size="sm"
                  variant={withMaterial ? 'outline' : 'default'}
                  onClick={() => setWithMaterial(false)}
                >
                  교안 없음
                </Button>
              </div>
              {withMaterial ? (
                <div className="grid gap-2">
                  <Input
                    ref={fileRef}
                    type="file"
                    accept="application/pdf,.pdf"
                    multiple
                    required
                    aria-label="교안 PDF"
                    onChange={(e) => setPicked(Array.from(e.target.files ?? []))}
                  />
                  <p className="text-xs text-muted-foreground">
                    PDF를 여러 개 한 번에 고를 수 있습니다. 자료 이름은 &apos;과목명 교안 번호&apos;로
                    자동으로 붙습니다.
                  </p>
                  {picked.length > 0 && (
                    <ul className="list-disc pl-5 text-sm text-muted-foreground">
                      {picked.map((f) => (
                        <li key={f.name}>{f.name}</li>
                      ))}
                    </ul>
                  )}
                </div>
              ) : (
                <p className="text-sm text-muted-foreground">
                  교안 없이 강좌만 열립니다. 교안은 나중에 강좌 페이지에서 누구나 올릴 수 있습니다.
                </p>
              )}
            </div>

            <div className="grid gap-2">
              <Label htmlFor="note">메모 (선택)</Label>
              <Textarea
                id="note"
                placeholder="관리자에게 전할 내용"
                value={note}
                onChange={(e) => setNote(e.target.value)}
              />
            </div>
            <ErrorText error={send.error} />
            <div>
              <Button type="submit" disabled={send.isPending}>
                <Send />
                {send.isPending ? '보내는 중…' : '요청 보내기'}
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  )
}

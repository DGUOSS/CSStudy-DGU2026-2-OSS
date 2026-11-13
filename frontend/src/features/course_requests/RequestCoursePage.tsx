import { useMutation, useQueryClient } from '@tanstack/react-query'
import { ChevronLeft, Send } from 'lucide-react'
import { type FormEvent, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router'
import { api, unwrap } from '@/api/client'
import { PdfPicker } from '@/components/PdfPicker'
import { ErrorText } from '@/components/States'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'

/**
 * 직접 요청: 수강 기록이나 강좌 찾기에서 찾을 수 없는 강좌(교양·학점교류, 교수 정보가 없는 수업 등).
 * 관리자가 교안을 확인하고 승인하면 강좌가 열리고, 맞는 수강 기록이 있으면 자동으로 이어진다.
 * 주소의 ?subject=&code=&prof=&semester= 로 미리 채울 수 있다.
 */
export function RequestCoursePage() {
  const [params] = useSearchParams()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const [subjectName, setSubjectName] = useState(params.get('subject') ?? '')
  const [subjectCode, setSubjectCode] = useState(params.get('code') ?? '')
  const [professorName, setProfessorName] = useState(params.get('prof') ?? '')
  const [semester, setSemester] = useState(params.get('semester') ?? '')
  const [note, setNote] = useState('')
  const [files, setFiles] = useState<File[]>([])

  const send = useMutation({
    mutationFn: () => {
      const form = new FormData()
      form.append('subject_name', subjectName)
      form.append('professor_name', professorName)
      if (subjectCode) form.append('subject_code', subjectCode)
      if (semester) form.append('semester', semester)
      if (note) form.append('note', note)
      for (const f of files) form.append('files', f)
      return unwrap(
        api.POST('/api/v1/course-requests', {
          // multipart는 openapi-fetch가 타입으로 표현하지 못해서 FormData를 그대로 보낸다
          body: form as never,
          bodySerializer: (b) => b as unknown as FormData,
        }),
      )
    },
    onSuccess: () => {
      qc.invalidateQueries()
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
        <Link to="/requests" className="mb-2 inline-flex items-center text-sm text-muted-foreground">
          <ChevronLeft className="size-4" />내 요청
        </Link>
        <h1 className="text-2xl font-bold">강좌 직접 요청</h1>
        <p className="text-sm text-muted-foreground">
          내 강좌나 강좌 찾기에서 찾을 수 없는 강좌를 요청합니다. 관리자가 교안을 확인한 뒤 엽니다.
          들어가려면 그 수업의 수강 기록이 있어야 합니다.
        </p>
      </div>
      <Card>
        <CardHeader>
          <CardTitle className="text-base">요청 내용</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={submit} className="grid gap-5">
            <div className="grid gap-4 sm:grid-cols-2">
              <Field id="subject" label="과목명">
                <Input
                  id="subject"
                  required
                  placeholder="예: 자료구조"
                  value={subjectName}
                  onChange={(e) => setSubjectName(e.target.value)}
                />
              </Field>
              <Field id="code" label="학수번호 (선택)">
                <Input
                  id="code"
                  placeholder="예: CSC2004"
                  value={subjectCode}
                  onChange={(e) => setSubjectCode(e.target.value)}
                />
              </Field>
              <Field id="prof" label="교수님 이름">
                <Input
                  id="prof"
                  required
                  placeholder="예: 홍길동"
                  value={professorName}
                  onChange={(e) => setProfessorName(e.target.value)}
                />
              </Field>
              <Field id="semester" label="학기 (선택)">
                <Input
                  id="semester"
                  placeholder="예: 2026 2학기"
                  value={semester}
                  onChange={(e) => setSemester(e.target.value)}
                />
              </Field>
            </div>
            <div className="grid gap-2">
              <Label>교안 PDF (선택)</Label>
              <PdfPicker files={files} onChange={setFiles} />
              <p className="text-xs text-muted-foreground">
                교안이 붙어야 승인할 수 있습니다. 지금 없으면 나중에 &lsquo;내 요청&rsquo;에서 붙여도
                됩니다. 자료 이름은 &apos;과목명 교안 번호&apos;로 자동으로 붙습니다.
              </p>
            </div>
            <Field id="note" label="메모 (선택)">
              <Textarea
                id="note"
                placeholder="관리자에게 전할 내용"
                value={note}
                onChange={(e) => setNote(e.target.value)}
              />
            </Field>
            <ErrorText error={send.error} />
            <div>
              <Button type="submit" disabled={send.isPending}>
                <Send />
                {send.isPending
                  ? '보내는 중…'
                  : files.length
                    ? `교안 ${files.length}개와 함께 요청`
                    : '교안 없이 요청'}
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  )
}

function Field({ id, label, children }: { id: string; label: string; children: React.ReactNode }) {
  return (
    <div className="grid gap-2">
      <Label htmlFor={id}>{label}</Label>
      {children}
    </div>
  )
}

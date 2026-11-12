import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'
import { Link } from 'react-router'
import { api, type Schemas, unwrap } from '@/api/client'
import { Empty, ErrorText, Loading } from '@/components/States'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { AdminNav } from './AdminNav'

type Probe = Schemas['ProbeReviewOut']
type Review = Schemas['ProbeReviewUpdate']
type Candidate = Schemas['ProbeCandidateOut']

export function AdminMisconceptionProbesPage() {
  const [filter, setFilter] = useState<'draft' | 'approved'>('draft')
  const probes = useQuery({
    queryKey: ['admin', 'misconception-probes'],
    queryFn: () => unwrap(api.GET('/api/v1/admin/misconception-probes')),
  })
  const shown = probes.data?.filter((probe) => probe.status === filter) ?? []
  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-bold">오개념 확인 문제 검토</h1>
        <p className="text-sm text-muted-foreground">
          학생이 고른 오답에 연결된 가설과 확인 문제를 검토합니다. 교안 근거를 확인한 뒤 승인하세요.
        </p>
      </div>
      <AdminNav />
      <CreateProbeCard />
      <div className="flex gap-2">
        <Button variant={filter === 'draft' ? 'default' : 'outline'} onClick={() => setFilter('draft')}>
          검토 대기 ({probes.data?.filter((probe) => probe.status === 'draft').length ?? 0})
        </Button>
        <Button variant={filter === 'approved' ? 'default' : 'outline'} onClick={() => setFilter('approved')}>
          승인됨 ({probes.data?.filter((probe) => probe.status === 'approved').length ?? 0})
        </Button>
      </div>
      {probes.isPending ? <Loading /> : shown.length === 0 ? <Empty>해당 확인 문제가 없습니다.</Empty> : null}
      <ErrorText error={probes.error} />
      {shown.map((probe) => <ProbeCard key={probe.id} probe={probe} />)}
    </div>
  )
}

function CreateProbeCard() {
  const qc = useQueryClient()
  const candidates = useQuery({
    queryKey: ['admin', 'misconception-probe-candidates'],
    queryFn: () => unwrap(api.GET('/api/v1/admin/misconception-probes/candidates')),
  })
  const [candidateId, setCandidateId] = useState(0)
  const [wrongChoice, setWrongChoice] = useState(-1)
  const [hypothesis, setHypothesis] = useState('')
  const [question, setQuestion] = useState('')
  const [choicesText, setChoicesText] = useState('')
  const [answerIndex, setAnswerIndex] = useState(0)
  const [explanation, setExplanation] = useState('')
  const [evidence, setEvidence] = useState('')
  const [materialId, setMaterialId] = useState(0)
  const [page, setPage] = useState(1)
  const selected = candidates.data?.find((candidate) => candidate.problem_id === candidateId)
  const available = (candidate: Candidate) => candidate.choices.map((choice, index) => ({ choice, index }))
    .filter(({ index }) => index !== candidate.answer_index && !candidate.existing_wrong_choice_indices.includes(index))
  const chooseCandidate = (candidate: Candidate | undefined) => {
    setCandidateId(candidate?.problem_id ?? 0)
    setWrongChoice(candidate ? (available(candidate)[0]?.index ?? -1) : -1)
    setEvidence(candidate?.evidence ?? '')
    setMaterialId(candidate?.source_material_id ?? 0)
    setPage(candidate?.source_page ?? 1)
  }
  const create = useMutation({
    mutationFn: (body: Schemas['ProbeCreate']) => unwrap(api.POST('/api/v1/admin/misconception-probes', { body })),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['admin', 'misconception-probes'] })
      qc.invalidateQueries({ queryKey: ['admin', 'misconception-probe-candidates'] })
      chooseCandidate(undefined)
      setHypothesis('')
      setQuestion('')
      setChoicesText('')
      setExplanation('')
    },
  })
  const submit = (event: FormEvent) => {
    event.preventDefault()
    if (!selected || wrongChoice < 0) return
    create.mutate({
      problem_id: selected.problem_id,
      wrong_choice_index: wrongChoice,
      hypothesis,
      question,
      choices: choicesText.split('\n').map((choice) => choice.trim()).filter(Boolean),
      answer_index: answerIndex,
      explanation,
      evidence,
      source_material_id: materialId,
      source_page: page,
    })
  }
  return (
    <Card>
      <CardHeader><CardTitle className="text-base">새 확인 문제 초안 만들기</CardTitle></CardHeader>
      <CardContent>
        <form onSubmit={submit} className="grid gap-4">
          <p className="text-sm text-muted-foreground">원본 문제의 오답 하나를 선택하고, 다른 상황에서 같은 개념을 확인할 문제를 작성하세요. 저장된 초안은 검토 후 승인해야 학생에게 보입니다.</p>
          <div className="grid gap-2">
            <Label htmlFor="new-probe-problem">원본 문제</Label>
            <select id="new-probe-problem" className="h-9 w-full rounded-md border bg-background px-3 text-sm" value={candidateId} onChange={(event) => chooseCandidate(candidates.data?.find((candidate) => candidate.problem_id === Number(event.target.value)))} required>
              <option value={0}>문제를 선택하세요</option>
              {candidates.data?.filter((candidate) => available(candidate).length > 0).map((candidate) => <option key={candidate.problem_id} value={candidate.problem_id}>{candidate.course_name} · {candidate.chapter_title} · {candidate.question.slice(0, 80)}</option>)}
            </select>
            <ErrorText error={candidates.error} />
          </div>
          {selected && <>
            <div className="rounded-md bg-muted p-3 text-sm">
              <p className="font-medium">{selected.question}</p>
              <p className="mt-1 text-muted-foreground">정답: {selected.choices[selected.answer_index]}</p>
              <p className="mt-1 text-muted-foreground">원본 근거: {selected.source_material_title ?? '교안 없음'} {selected.source_page ? `${selected.source_page}쪽` : ''}</p>
            </div>
            <div className="grid gap-2"><Label htmlFor="new-probe-wrong">확인할 오답</Label><select id="new-probe-wrong" className="h-9 rounded-md border bg-background px-3 text-sm" value={wrongChoice} onChange={(event) => setWrongChoice(Number(event.target.value))} required>{available(selected).map(({ choice, index }) => <option key={index} value={index}>{index + 1}번 · {choice}</option>)}</select></div>
            <div className="grid gap-2"><Label htmlFor="new-probe-hypothesis">추정 오개념</Label><Textarea id="new-probe-hypothesis" value={hypothesis} onChange={(event) => setHypothesis(event.target.value)} required /></div>
            <div className="grid gap-2"><Label htmlFor="new-probe-question">확인 문제</Label><Textarea id="new-probe-question" value={question} onChange={(event) => setQuestion(event.target.value)} required /></div>
            <div className="grid gap-2"><Label htmlFor="new-probe-choices">보기 (한 줄에 하나씩)</Label><Textarea id="new-probe-choices" value={choicesText} onChange={(event) => setChoicesText(event.target.value)} rows={3} required /></div>
            <div className="grid gap-2"><Label htmlFor="new-probe-answer">정답 보기 번호 (1부터)</Label><Input id="new-probe-answer" type="number" min={1} max={Math.max(2, choicesText.split('\n').filter(Boolean).length)} value={answerIndex + 1} onChange={(event) => setAnswerIndex(Number(event.target.value) - 1)} required /></div>
            <div className="grid gap-2"><Label htmlFor="new-probe-explanation">해설</Label><Textarea id="new-probe-explanation" value={explanation} onChange={(event) => setExplanation(event.target.value)} required /></div>
            <div className="grid gap-2"><Label htmlFor="new-probe-evidence">교안 근거 문장</Label><Textarea id="new-probe-evidence" value={evidence} onChange={(event) => setEvidence(event.target.value)} required /></div>
            <div className="flex flex-wrap gap-4">
              <div className="grid gap-2"><Label htmlFor="new-probe-material">교안 ID</Label><Input id="new-probe-material" type="number" min={1} value={materialId} onChange={(event) => setMaterialId(Number(event.target.value))} required /></div>
              <div className="grid gap-2"><Label htmlFor="new-probe-page">쪽 번호</Label><Input id="new-probe-page" type="number" min={1} value={page} onChange={(event) => setPage(Number(event.target.value))} required /></div>
            </div>
            <Button type="submit" className="justify-self-start" disabled={create.isPending || wrongChoice < 0}>초안 저장</Button>
            <ErrorText error={create.error} />
          </>}
        </form>
      </CardContent>
    </Card>
  )
}

function ProbeCard({ probe }: { probe: Probe }) {
  const qc = useQueryClient()
  const [form, setForm] = useState<Review>({
    hypothesis: probe.hypothesis,
    question: probe.question,
    choices: probe.choices,
    answer_index: probe.answer_index,
    explanation: probe.explanation,
    evidence: probe.evidence ?? '',
    source_material_id: probe.source_material_id ?? 0,
    source_page: probe.source_page ?? 1,
  })
  const [choiceText, setChoiceText] = useState(probe.choices.join('\n'))
  const dirty = form.hypothesis !== probe.hypothesis || form.question !== probe.question ||
    choiceText !== probe.choices.join('\n') || form.answer_index !== probe.answer_index ||
    form.explanation !== probe.explanation || form.evidence !== (probe.evidence ?? '') ||
    form.source_material_id !== (probe.source_material_id ?? 0) || form.source_page !== (probe.source_page ?? 1)
  const invalidate = () => qc.invalidateQueries({ queryKey: ['admin', 'misconception-probes'] })
  const save = useMutation({
    mutationFn: (body: Review) => unwrap(api.PUT('/api/v1/admin/misconception-probes/{probe_id}', { params: { path: { probe_id: probe.id } }, body })),
    onSuccess: invalidate,
  })
  const approve = useMutation({
    mutationFn: () => unwrap(api.POST('/api/v1/admin/misconception-probes/{probe_id}/approve', { params: { path: { probe_id: probe.id } } })),
    onSuccess: invalidate,
  })
  const withdraw = useMutation({
    mutationFn: () => unwrap(api.POST('/api/v1/admin/misconception-probes/{probe_id}/draft', { params: { path: { probe_id: probe.id } } })),
    onSuccess: invalidate,
  })
  const pending = save.isPending || approve.isPending || withdraw.isPending
  const submit = (event: FormEvent) => {
    event.preventDefault()
    save.mutate({ ...form, choices: choiceText.split('\n').map((choice) => choice.trim()).filter(Boolean) })
  }
  const update = <K extends keyof Review>(key: K, value: Review[K]) => setForm((old) => ({ ...old, [key]: value }))
  return (
    <Card>
      <CardHeader>
        <div className="flex flex-wrap items-center gap-2">
          <CardTitle className="text-base">{probe.course_name} · {probe.professor_name}</CardTitle>
          <Badge variant="outline">{probe.status === 'draft' ? '검토 대기' : '승인됨'}</Badge>
        </div>
      </CardHeader>
      <CardContent className="grid gap-5">
        <div className="rounded-md bg-muted p-4 text-sm">
          <p className="font-medium">원본 문제: {probe.problem_question}</p>
          <p className="mt-2">학생이 고른 오답: {probe.problem_choices[probe.wrong_choice_index]}</p>
          <p className="text-muted-foreground">원본 정답: {probe.problem_choices[probe.problem_answer_index]}</p>
          <Link className="mt-2 inline-block text-primary underline" to={`/courses/${probe.course_id}/chapters/${probe.chapter_id}/quiz?problemId=${probe.problem_id}`}>이 문제 체험하기</Link>
        </div>
        <form onSubmit={submit} className="grid gap-4">
          <div className="grid gap-2"><Label htmlFor={`hypothesis-${probe.id}`}>추정 오개념</Label><Textarea id={`hypothesis-${probe.id}`} value={form.hypothesis} onChange={(e) => update('hypothesis', e.target.value)} required /></div>
          <div className="grid gap-2"><Label htmlFor={`question-${probe.id}`}>확인 문제</Label><Textarea id={`question-${probe.id}`} value={form.question} onChange={(e) => update('question', e.target.value)} required /></div>
          <div className="grid gap-2"><Label htmlFor={`choices-${probe.id}`}>보기 (한 줄에 하나씩)</Label><Textarea id={`choices-${probe.id}`} value={choiceText} onChange={(e) => setChoiceText(e.target.value)} rows={4} required /></div>
          <div className="grid gap-2"><Label htmlFor={`answer-${probe.id}`}>정답 보기 번호 (1부터)</Label><Input id={`answer-${probe.id}`} type="number" min={1} max={Math.max(2, choiceText.split('\n').filter(Boolean).length)} value={form.answer_index + 1} onChange={(e) => update('answer_index', Number(e.target.value) - 1)} required /></div>
          <div className="grid gap-2"><Label htmlFor={`explanation-${probe.id}`}>해설</Label><Textarea id={`explanation-${probe.id}`} value={form.explanation} onChange={(e) => update('explanation', e.target.value)} required /></div>
          <div className="grid gap-2"><Label htmlFor={`evidence-${probe.id}`}>교안 근거 문장</Label><Textarea id={`evidence-${probe.id}`} value={form.evidence} onChange={(e) => update('evidence', e.target.value)} required /></div>
          <p className="text-sm text-muted-foreground">현재 연결된 교안: {probe.source_material_title ?? '없음'} {probe.source_page ? `· ${probe.source_page}쪽` : ''}</p>
          {probe.source_page_text && <div className="rounded-md border p-3 text-sm"><p className="mb-2 font-medium">현재 교안 쪽 본문</p><p className="max-h-48 overflow-auto whitespace-pre-wrap text-muted-foreground">{probe.source_page_text}</p></div>}
          <div className="flex flex-wrap gap-4">
            <div className="grid gap-2"><Label htmlFor={`material-${probe.id}`}>교안</Label><select id={`material-${probe.id}`} className="h-9 rounded-md border bg-background px-3 text-sm" value={form.source_material_id} onChange={(e) => update('source_material_id', Number(e.target.value))} required><option value={0}>교안 선택</option>{probe.available_materials.map((material) => <option key={material.id} value={material.id}>{material.title} ({material.page_count}쪽)</option>)}</select></div>
            <div className="grid gap-2"><Label htmlFor={`page-${probe.id}`}>쪽 번호</Label><Input id={`page-${probe.id}`} type="number" min={1} value={form.source_page} onChange={(e) => update('source_page', Number(e.target.value))} required /></div>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button type="submit" variant="outline" disabled={pending || !dirty}>수정하고 초안으로 저장</Button>
            {probe.status === 'draft' ? <Button type="button" disabled={pending || dirty} title={dirty ? '수정 내용을 먼저 저장하세요' : undefined} onClick={() => approve.mutate()}>승인</Button> : <Button type="button" variant="outline" disabled={pending} onClick={() => withdraw.mutate()}>승인 취소</Button>}
          </div>
          <ErrorText error={save.error || approve.error || withdraw.error} />
        </form>
      </CardContent>
    </Card>
  )
}

import { useQuery } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'
import { Link, useSearchParams } from 'react-router'
import { api, unwrap } from '@/api/client'
import { Empty, ErrorText, Loading } from '@/components/States'
import { Button, buttonVariants } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { AppShell } from '@/features/home/AppShell'

export function ProfessorsPage({ design = false }: { design?: boolean }) {
  const content = <ProfessorSearch design={design} />
  return design ? <AppShell>{content}</AppShell> : content
}

function ProfessorSearch({ design }: { design: boolean }) {
  const [params, setParams] = useSearchParams()
  const q = params.get('q') ?? ''
  const emp = params.get('professor') ?? ''
  const offset = Math.max(0, Number(params.get('offset')) || 0)
  const [input, setInput] = useState(q)
  const search = useQuery({
    queryKey: ['catalog', 'professors', q, offset],
    enabled: !!q,
    queryFn: () => unwrap(api.GET('/api/v1/catalog/professors', { params: { query: { q, offset, limit: 20 } } })),
  })
  const history = useQuery({
    queryKey: ['catalog', 'professor-offerings', emp],
    enabled: !!emp,
    queryFn: () => unwrap(api.GET('/api/v1/catalog/professor-offerings', { params: { query: { emp_no: emp } } })),
  })
  const submit = (e: FormEvent) => {
    e.preventDefault()
    if (input.trim()) setParams({ q: input.trim() })
  }
  return <div className="flex flex-col gap-5">
    <div>
      <h1 className="text-2xl font-bold">교수별 개설과목</h1>
      <p className="mt-1 text-sm text-muted-foreground">교수명을 검색해 최근 3개 학년도에 개설된 과목을 확인하세요.</p>
    </div>
    <Link to={design ? '/study/find' : '/find'} className={buttonVariants({ variant: 'outline', className: 'self-start' })}>강좌 찾기로 돌아가기</Link>
    <Card className="p-4">
      <form onSubmit={submit} className="flex gap-2">
        <Input aria-label="교수명" placeholder="교수명을 입력하세요" maxLength={50} value={input} onChange={e => setInput(e.target.value)} />
        <Button type="submit" disabled={!input.trim()}>검색</Button>
      </form>
    </Card>
    <p className="text-sm text-muted-foreground">수집된 종합강의시간표 기준이며, 미수집 학기는 결과에 나타나지 않을 수 있습니다. 교원번호가 없는 기록과 공동강의의 비대표 교수는 조회에서 빠질 수 있습니다. 검색 결과의 학과는 과목의 개설 학과입니다.</p>
    <ErrorText error={search.error} />
    {q && search.isFetching && <Loading />}
    {search.data && <>
      <p className="text-sm">{search.data.start_year}~{search.data.end_year}학년도 · 검색된 교수 {search.data.total}명</p>
      {!search.data.total && <Empty>수집된 최근 3년 자료에 일치하는 교수가 없습니다. 이름이나 자료 수집 여부를 확인해 주세요.</Empty>}
      <div className="grid gap-2 sm:grid-cols-2">
        {search.data.items.map(p => <button key={p.emp_no} type="button" aria-pressed={emp === p.emp_no}
          onClick={() => setParams({ q, offset: String(offset), professor: p.emp_no })}
          className={`rounded-xl border p-4 text-left ${emp === p.emp_no ? 'border-primary bg-primary/5' : 'bg-card hover:bg-muted/50'}`}>
          <span className="font-semibold">{p.name} 교수</span>
          <span className="mt-1 block text-xs text-muted-foreground">교원번호 {p.emp_no} · 개설과목 {p.subject_count}개</span>
        </button>)}
      </div>
      {search.data.total > 20 && <div className="flex gap-2">
        <Button variant="outline" disabled={offset === 0} onClick={() => setParams({ q, offset: String(Math.max(0, offset - 20)) })}>이전</Button>
        <Button variant="outline" disabled={offset + 20 >= search.data.total} onClick={() => setParams({ q, offset: String(offset + 20) })}>다음</Button>
      </div>}
    </>}
    <ErrorText error={history.error} />
    {emp && history.isFetching && <Loading />}
    {history.data && <section className="flex flex-col gap-3" aria-label="선택한 교수의 개설과목">
      <h2 className="text-xl font-bold">{history.data.name} 교수 · 개설과목 {history.data.subjects.length}개</h2>
      <p className="text-sm text-muted-foreground">{history.data.start_year}~{history.data.end_year}학년도 · 같은 학수번호는 한 과목으로 묶었습니다.</p>
      {history.data.subjects.map(s => <Card key={s.code} className="p-4">
        <h3 className="font-semibold">{s.name} <span className="text-sm font-normal text-muted-foreground">{s.code}</span></h3>
        <p className="mb-3 text-xs text-muted-foreground">{s.departments.join(' · ')}</p>
        <ul className="flex flex-col gap-2 text-sm">{s.terms.map(t => <li key={`${t.year}-${t.sem_cd}`} className="flex flex-wrap justify-between gap-2 border-t pt-2">
          <span>{t.label}</span><span className="text-muted-foreground">분반 {t.sections.map(section => section || '미표기').join(', ')}</span>
        </li>)}</ul>
      </Card>)}
    </section>}
  </div>
}

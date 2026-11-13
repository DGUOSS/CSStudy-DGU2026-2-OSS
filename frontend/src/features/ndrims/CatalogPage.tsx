import { ExternalLink, Search } from 'lucide-react'
import { type FormEvent, useState } from 'react'
import { Link } from 'react-router'
import { Empty, ErrorText, Loading } from '@/components/States'
import { Badge } from '@/components/ui/badge'
import { Button, buttonVariants } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { api, unwrap } from '@/api/client'
import { RequestWithFiles } from '@/features/course_requests/RequestWithFiles'
import {
  type OfferingGroup,
  type SearchQuery,
  useCatalogSearch,
  useFilters,
  useTerms,
} from './queries'

const PAGE = 50
const selectCls =
  'h-9 w-full rounded-md border bg-card px-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring'

/** 강좌 찾기: 엔드림스 종합강의시간표처럼 학기·대학·학과·이수구분·과목·교수로 찾고, 열기를 요청한다. */
export function CatalogPage() {
  const terms = useTerms()
  const [term, setTerm] = useState('')
  const [colg, setColg] = useState('')
  const [dpt, setDpt] = useState('')
  const [cpdiv, setCpdiv] = useState('')
  const [q, setQ] = useState('')
  const [prof, setProf] = useState('')
  const [query, setQuery] = useState<SearchQuery | null>(null)

  // 학기를 고르지 않았으면 가장 최근 학기
  const first = terms.data?.[0]
  const termKey = term || (first ? `${first.year}|${first.sem_cd}` : '')
  const [year, sem_cd] = termKey.split('|')
  const filters = useFilters(year, sem_cd)
  const departments = filters.data?.colleges.find((c) => c.name === colg)?.departments ?? []
  const result = useCatalogSearch(query)

  const submit = (e?: FormEvent, offset = 0) => {
    e?.preventDefault()
    if (year && sem_cd)
      setQuery({ year, sem_cd, colg, dpt, cpdiv, q: q.trim(), prof: prof.trim(), offset })
  }

  // 이전/다음은 보고 있는 검색 조건 그대로 쪽만 넘긴다(입력 중인 값은 [조회]를 눌러야 반영)
  const page = (offset: number) => query && setQuery({ ...query, offset })

  if (terms.isPending) return <Loading />
  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-bold">강좌 찾기</h1>
        <p className="text-sm text-muted-foreground">
          엔드림스 종합강의시간표와 같은 목록입니다. 동국스터디에 아직 없는 강좌는 열어 달라고
          요청할 수 있고, 들어가는 건 수강 기록이 있는 강좌만 가능합니다.
        </p>
      </div>
      {terms.data?.length === 0 ? (
        <Empty>
          아직 개설 목록이 없습니다. 관리자가 이번 학기 목록을 가져오면 찾을 수 있습니다.
        </Empty>
      ) : (
        <Card className="p-4">
          <form onSubmit={submit} className="grid gap-3 sm:grid-cols-3">
            <Field label="학기">
              <select className={selectCls} value={termKey} onChange={(e) => setTerm(e.target.value)}>
                {terms.data?.map((t) => (
                  <option key={`${t.year}|${t.sem_cd}`} value={`${t.year}|${t.sem_cd}`}>
                    {t.label} ({t.count})
                  </option>
                ))}
              </select>
            </Field>
            <Field label="대학">
              <select
                className={selectCls}
                value={colg}
                onChange={(e) => {
                  setColg(e.target.value)
                  setDpt('')
                }}
              >
                <option value="">전체</option>
                {filters.data?.colleges.map((c) => (
                  <option key={c.name}>{c.name}</option>
                ))}
              </select>
            </Field>
            <Field label="학과">
              <select
                className={selectCls}
                value={dpt}
                onChange={(e) => setDpt(e.target.value)}
                disabled={!colg}
              >
                <option value="">전체</option>
                {departments.map((d) => (
                  <option key={d}>{d}</option>
                ))}
              </select>
            </Field>
            <Field label="이수구분">
              <select
                className={selectCls}
                value={cpdiv}
                onChange={(e) => setCpdiv(e.target.value)}
              >
                <option value="">전체</option>
                {filters.data?.cpdivs.map((c) => (
                  <option key={c}>{c}</option>
                ))}
              </select>
            </Field>
            <Field label="과목명·학수번호">
              <Input
                value={q}
                onChange={(e) => setQ(e.target.value)}
                placeholder="예: 기초프로, CSC2001"
              />
            </Field>
            <Field label="교수명">
              <Input value={prof} onChange={(e) => setProf(e.target.value)} />
            </Field>
            <div className="sm:col-span-3">
              <Button type="submit">
                <Search />
                조회
              </Button>
            </div>
          </form>
        </Card>
      )}
      <ErrorText error={result.error} />
      {result.data && (
        <div className="flex flex-col gap-3">
          <p className="text-sm text-muted-foreground">
            강좌 {result.data.total}개 (같은 교수님 분반은 한 줄로 묶음)
          </p>
          <div className="overflow-x-auto rounded-xl border bg-card">
            <table className="w-full text-sm">
              <thead className="border-b bg-muted/50 text-left text-xs text-muted-foreground">
                <tr>
                  <th className="px-3 py-2">학수번호-분반</th>
                  <th className="px-3 py-2">과목명</th>
                  <th className="px-3 py-2">교수</th>
                  <th className="px-3 py-2">이수구분·학점</th>
                  <th className="px-3 py-2">시간</th>
                  <th className="px-3 py-2">동국스터디</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {result.data.items.map((g) => (
                  <Row key={`${g.sbj_no}-${g.emp_no ?? g.emp_nm}`} g={g} />
                ))}
              </tbody>
            </table>
          </div>
          {result.data.total > PAGE && (
            <div className="flex items-center gap-2 text-sm">
              <Button
                size="sm"
                variant="outline"
                disabled={!query?.offset}
                onClick={() => page(Math.max(0, (query?.offset ?? 0) - PAGE))}
              >
                이전
              </Button>
              <span>
                {(query?.offset ?? 0) + 1}–
                {Math.min((query?.offset ?? 0) + PAGE, result.data.total)}
              </span>
              <Button
                size="sm"
                variant="outline"
                disabled={(query?.offset ?? 0) + PAGE >= result.data.total}
                onClick={() => page((query?.offset ?? 0) + PAGE)}
              >
                다음
              </Button>
            </div>
          )}
          <Link to="/requests/new" className="text-sm text-muted-foreground hover:underline">
            찾는 강좌가 목록에 없나요? 직접 요청하기
          </Link>
        </div>
      )}
    </div>
  )
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="grid gap-1.5">
      <Label className="text-xs text-muted-foreground">{label}</Label>
      {children}
    </div>
  )
}

function Row({ g }: { g: OfferingGroup }) {
  const rates = Object.entries(g.eval_rates).filter(([, v]) => v != null)
  return (
    <tr className="align-top">
      <td className="whitespace-nowrap px-3 py-2 font-mono text-xs">
        {g.sbj_no}-{g.dvcls.join(',')}
      </td>
      <td className="px-3 py-2">
        <div className="font-medium">{g.sbj_nm}</div>
        <div className="text-xs text-muted-foreground">
          {g.dpt_nm}
          {rates.length > 0 && ` · ${rates.map(([k, v]) => `${k} ${v}%`).join(' ')}`}
          {g.plan_url && (
            <a
              href={g.plan_url}
              target="_blank"
              rel="noreferrer"
              className="ml-1 inline-flex items-center text-primary"
            >
              계획서 <ExternalLink className="ml-0.5 size-3" />
            </a>
          )}
        </div>
      </td>
      <td className="whitespace-nowrap px-3 py-2">{g.emp_nm}</td>
      <td className="whitespace-nowrap px-3 py-2 text-xs">
        {g.cpdiv_nm} {g.cdt && `· ${g.cdt}`}
      </td>
      <td className="px-3 py-2 text-xs text-muted-foreground">{g.timetable.join(' / ')}</td>
      <td className="whitespace-nowrap px-3 py-2">
        {g.status === 'open' ? (
          g.mine && g.course_id ? (
            <Link to={`/courses/${g.course_id}`} className={buttonVariants({ size: 'sm' })}>
              입장
            </Link>
          ) : (
            <Badge variant="secondary" title="수강 기록이 있어야 들어갈 수 있습니다">
              열림 · 잠김
            </Badge>
          )
        ) : g.requested_by_me ? (
          <Badge variant="outline">요청함 ({g.request_count}명)</Badge>
        ) : (
          <RequestWithFiles
            label={`열어 달라고 요청${g.request_count > 0 ? ` (${g.request_count}명)` : ''}`}
            create={async (note) =>
              (
                await unwrap(
                  api.POST('/api/v1/catalog/request', {
                    body: {
                      year: g.year,
                      sem_cd: g.sem_cd,
                      sbj_no: g.sbj_no,
                      dvcls: g.dvcls[0] ?? '',
                      note,
                    },
                  }),
                )
              ).request_id
            }
          />
        )}
      </td>
    </tr>
  )
}

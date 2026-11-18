import { ExternalLink, Search } from 'lucide-react'
import { type FormEvent, type ReactNode, useState } from 'react'
import { Link } from 'react-router'
import { api, unwrap } from '@/api/client'
import { Empty, ErrorText, Loading } from '@/components/States'
import {
  type OfferingGroup,
  type SearchQuery,
  useCatalogSearch,
  useFilters,
  useTerms,
} from '@/features/catalog/queries'
import { RequestWithFiles } from '@/features/course_requests/RequestWithFiles'
import { AppShell } from '@/features/home/AppShell'

const PAGE = 50
const fieldCls =
  'h-11 w-full rounded-xl border border-home-line bg-white px-3 text-[15px] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-navy/40 disabled:bg-home-bg disabled:text-ink-2/60'

/** 강좌 찾기(/study/find): 학기·대학·학과·이수구분·과목·교수로 개설 목록을 찾고, 아직 없는 강좌는 열어 달라고 요청한다. */
export function FindPage() {
  return (
    <AppShell>
      <FindContent />
    </AppShell>
  )
}

function FindContent() {
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
  const offset = query?.offset ?? 0

  const submit = (e?: FormEvent) => {
    e?.preventDefault()
    if (year && sem_cd)
      setQuery({ year, sem_cd, colg, dpt, cpdiv, q: q.trim(), prof: prof.trim(), offset: 0 })
  }
  // 이전/다음은 보고 있는 검색 조건 그대로 쪽만 넘긴다
  const page = (next: number) => query && setQuery({ ...query, offset: next })

  return (
    <>
      <div>
        <h1 className="text-2xl font-bold">강좌 찾기</h1>
        <p className="mt-1 text-sm text-ink-2">
          엔드림스 종합강의시간표와 같은 목록이에요. 동국스터디에 아직 없는 강좌는 열어 달라고 요청할
          수 있고, 들어가는 건 수강 기록이 있는 강좌만 가능해요.
        </p>
      </div>

      {terms.isPending ? (
        <Loading />
      ) : terms.data?.length === 0 ? (
        <Empty>아직 개설 목록이 없어요. 관리자가 이번 학기 목록을 가져오면 찾을 수 있어요.</Empty>
      ) : (
        <form
          onSubmit={submit}
          className="grid gap-4 rounded-2xl border border-home-line bg-white p-5 sm:grid-cols-3"
        >
          <Field label="학기">
            <select className={fieldCls} value={termKey} onChange={(e) => setTerm(e.target.value)}>
              {terms.data?.map((t) => (
                <option key={`${t.year}|${t.sem_cd}`} value={`${t.year}|${t.sem_cd}`}>
                  {t.label} ({t.count})
                </option>
              ))}
            </select>
          </Field>
          <Field label="대학">
            <select
              className={fieldCls}
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
              className={fieldCls}
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
            <select className={fieldCls} value={cpdiv} onChange={(e) => setCpdiv(e.target.value)}>
              <option value="">전체</option>
              {filters.data?.cpdivs.map((c) => (
                <option key={c}>{c}</option>
              ))}
            </select>
          </Field>
          <Field label="과목명·학수번호">
            <input
              className={fieldCls}
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="예: 기초프로, CSC2001"
            />
          </Field>
          <Field label="교수명">
            <input className={fieldCls} value={prof} onChange={(e) => setProf(e.target.value)} />
          </Field>
          <div className="sm:col-span-3">
            <button
              type="submit"
              className="inline-flex h-11 cursor-pointer items-center gap-2 rounded-full bg-navy px-6 text-[15px] font-bold text-white hover:bg-navy-deep"
            >
              <Search size={16} />
              조회
            </button>
          </div>
        </form>
      )}

      <ErrorText error={result.error} />
      {result.data && (
        <div className="flex flex-col gap-3">
          <p className="text-sm text-ink-2">
            강좌 {result.data.total}개 (같은 교수님 분반은 한 줄로 묶었어요)
          </p>
          {result.data.items.length === 0 ? (
            <Empty>조건에 맞는 강좌가 없어요.</Empty>
          ) : (
            <ul className="flex flex-col gap-3">
              {result.data.items.map((g) => (
                <Offering key={`${g.sbj_no}-${g.emp_no ?? g.emp_nm}`} g={g} />
              ))}
            </ul>
          )}
          {result.data.total > PAGE && (
            <div className="flex items-center gap-3 text-sm">
              <PageBtn disabled={!offset} onClick={() => page(Math.max(0, offset - PAGE))}>
                이전
              </PageBtn>
              <span className="text-ink-2">
                {offset + 1}–{Math.min(offset + PAGE, result.data.total)}
              </span>
              <PageBtn
                disabled={offset + PAGE >= result.data.total}
                onClick={() => page(offset + PAGE)}
              >
                다음
              </PageBtn>
            </div>
          )}
          <Link to="/requests/new" className="text-sm font-bold text-navy hover:underline">
            찾는 강좌가 목록에 없나요? 직접 요청하기
          </Link>
        </div>
      )}
    </>
  )
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className="grid gap-1.5">
      <span className="text-xs font-bold text-ink-2">{label}</span>
      {children}
    </label>
  )
}

function PageBtn({
  disabled,
  onClick,
  children,
}: {
  disabled: boolean
  onClick: () => void
  children: ReactNode
}) {
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={onClick}
      className="h-9 cursor-pointer rounded-full border border-home-line bg-white px-4 font-bold text-navy hover:bg-navy-tint disabled:cursor-default disabled:opacity-40"
    >
      {children}
    </button>
  )
}

function Offering({ g }: { g: OfferingGroup }) {
  const rates = Object.entries(g.eval_rates).filter(([, v]) => v != null)
  return (
    <li className="flex flex-wrap items-start gap-4 rounded-2xl border border-home-line bg-white p-5">
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <h3 className="text-lg font-bold">{g.sbj_nm}</h3>
          {g.cpdiv_nm && (
            <span className="rounded-full bg-tone-blue px-2.5 py-0.5 text-xs font-bold text-navy">
              {g.cpdiv_nm}
              {g.cdt && ` · ${g.cdt}학점`}
            </span>
          )}
        </div>
        <p className="mt-0.5 text-sm text-ink-2">
          {g.emp_nm ? `${g.emp_nm} 교수님` : '교수 미정'} · {g.sbj_no}-{g.dvcls.join(',')}
          {g.dpt_nm && ` · ${g.dpt_nm}`}
        </p>
        {g.timetable.length > 0 && (
          <p className="mt-1 text-xs text-ink-2">{g.timetable.join(' / ')}</p>
        )}
        {(rates.length > 0 || g.plan_url) && (
          <p className="mt-1 text-xs text-ink-2">
            {rates.map(([k, v]) => `${k} ${v}%`).join(' · ')}
            {g.plan_url && (
              <a
                href={g.plan_url}
                target="_blank"
                rel="noreferrer"
                className="ml-2 inline-flex items-center gap-0.5 font-bold text-navy hover:underline"
              >
                강의계획서 <ExternalLink size={12} />
              </a>
            )}
          </p>
        )}
      </div>
      <div className="shrink-0">
        <Action g={g} />
      </div>
    </li>
  )
}

const pill = 'inline-flex h-10 items-center rounded-full px-5 text-sm font-bold'

function Action({ g }: { g: OfferingGroup }) {
  if (g.status === 'open') {
    return g.mine && g.course_id ? (
      <Link
        to={`/study/courses/${g.course_id}`}
        className={`${pill} bg-navy text-white hover:bg-navy-deep`}
      >
        입장
      </Link>
    ) : (
      <span
        className={`${pill} bg-tone-gray text-ink-2`}
        title="수강 기록이 있어야 들어갈 수 있어요"
      >
        열림 · 잠김
      </span>
    )
  }
  if (g.requested_by_me)
    return (
      <span className={`${pill} bg-gold-soft text-navy`}>요청함 ({g.request_count}명)</span>
    )
  return (
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
  )
}

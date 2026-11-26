// 시험 결과 학습 리포트: 단원 숙련도(전/후), 응시자 중 내 위치, 오답 흐름 표, 개념별 상태 표.
// 데이터는 백엔드 report(build_report)가 다 계산해서 준다. 여기서는 그리기만 한다.
// (새 디자인) 단원이 3~4개뿐이라 레이더 대신 막대 두 줄, 오답 흐름은 Sankey 대신 표로 보여 준다.
import { Bar, BarChart, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import type { Schemas } from '@/api/client'
import { cn } from '@/lib/utils'

type ReportT = Schemas['ReportOut']

const pct = (x: number) => `${Math.round(x * 100)}%`

export function Section({
  title,
  hint,
  aside,
  children,
}: {
  title: string
  hint?: string
  aside?: React.ReactNode
  children: React.ReactNode
}) {
  return (
    <section className="flex min-w-0 flex-col gap-4 rounded-2xl border border-home-line bg-white p-5">
      <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
        <h3 className="text-lg font-bold">{title}</h3>
        {aside}
      </div>
      {hint && <p className="-mt-3 text-sm text-ink-2">{hint}</p>}
      {children}
    </section>
  )
}

export function ChapterChart({ chapters }: { chapters: ReportT['chapters'] }) {
  if (chapters.length === 0) return null
  return (
    <Section
      title="단원별 숙련도 변화"
      aside={
        <span className="flex gap-3 text-[13px] text-ink-2">
          <span className="inline-flex items-center gap-1.5">
            <span className="h-2 w-3 rounded bg-tone-gray" />
            시험 전
          </span>
          <span className="inline-flex items-center gap-1.5">
            <span className="h-2 w-3 rounded bg-navy" />
            시험 후
          </span>
        </span>
      }
    >
      <ul className="flex flex-col gap-3">
        {chapters.map((c) => (
          <li key={c.chapter_id} className="grid grid-cols-[minmax(0,9rem)_minmax(0,1fr)_auto] items-center gap-3">
            <span className="truncate text-sm font-bold" title={c.title}>
              {c.title}
            </span>
            <span className="flex flex-col gap-1" aria-hidden="true">
              <span className="h-2 overflow-hidden rounded-full bg-[#e6eaf2]">
                <span className="block h-full rounded-full bg-tone-gray" style={{ width: pct(c.before) }} />
              </span>
              <span className="h-2 overflow-hidden rounded-full bg-[#e6eaf2]">
                <span className="block h-full rounded-full bg-navy" style={{ width: pct(c.after) }} />
              </span>
            </span>
            <span className="text-sm tabular-nums">
              {pct(c.before)} → <b>{pct(c.after)}</b>
            </span>
          </li>
        ))}
      </ul>
    </Section>
  )
}

export function Distribution({ dist }: { dist: ReportT['distribution'] }) {
  if (dist.length === 0) return null
  const total = dist[0].total_points
  const data = dist.map((d, i) => ({ key: i, score: d.score, rank: d.rank, me: d.me }))
  return (
    <Section title="응시자 중 내 위치" hint={`응시자 ${dist.length}명, 점수 높은 순 · 진한 막대가 나`}>
      <div className="h-40 w-full">
        <ResponsiveContainer>
          <BarChart data={data} margin={{ left: -20, right: 8 }}>
            <XAxis dataKey="rank" tick={{ fontSize: 11 }} tickFormatter={(r) => `${r}등`} />
            <YAxis domain={[0, total]} allowDecimals={false} tick={{ fontSize: 11 }} />
            <Tooltip
              cursor={{ fill: 'var(--color-home-bg)' }}
              formatter={(v: number) => [`${v}/${total}점`, '점수']}
              labelFormatter={(r) => `${r}등`}
              contentStyle={{ fontSize: 12, borderRadius: 12 }}
            />
            <Bar isAnimationActive={false} dataKey="score" radius={[4, 4, 0, 0]} maxBarSize={36}>
              {data.map((d) => (
                <Cell key={d.key} fill={d.me ? 'var(--color-navy)' : 'var(--color-tone-gray)'} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </Section>
  )
}

/** 틀린 문제 → 고른 보기의 오개념 → 개념 → 교안 쪽 (빈칸은 뺀다) */
export function FlowTable({ flows, blanks }: { flows: ReportT['flows']; blanks: number[] }) {
  if (flows.length === 0 && blanks.length === 0) return null
  return (
    <Section
      title="틀린 문제는 어디서 왔나"
      aside={
        <span className="text-[13px] text-ink-2">
          문제 → 오개념 → 개념 → 교안 쪽
          {blanks.length > 0 && ` · 빈칸 ${blanks.join(', ')}번은 뺐어요`}
        </span>
      }
    >
      {flows.length === 0 ? (
        <p className="text-sm text-ink-2">답을 고르고 틀린 문제가 없어요.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[600px] text-sm">
            <thead className="text-left text-xs text-ink-2">
              <tr>
                <th scope="col" className="px-2.5 py-2 font-bold">문제</th>
                <th scope="col" className="px-2.5 py-2 font-bold">
                  고른 보기가 말해 주는 오개념 <span className="font-normal">(AI 추정)</span>
                </th>
                <th scope="col" className="px-2.5 py-2 font-bold">개념</th>
                <th scope="col" className="px-2.5 py-2 font-bold">교안</th>
              </tr>
            </thead>
            <tbody>
              {flows.map((f) => (
                <tr key={f.no} className="border-t border-home-line">
                  <td className="whitespace-nowrap px-2.5 py-3 font-bold">
                    <a href={`#q-${f.no}`} className="text-navy hover:underline">
                      {f.no}번
                    </a>
                  </td>
                  <td className="px-2.5 py-3">{f.misconception ?? <span className="text-ink-2">추정 없음</span>}</td>
                  <td className="whitespace-nowrap px-2.5 py-3">{f.concept ?? '–'}</td>
                  <td className="whitespace-nowrap px-2.5 py-3 font-bold text-navy">{f.page ?? '–'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Section>
  )
}

export function ConceptTable({ concepts }: { concepts: ReportT['concepts'] }) {
  if (concepts.length === 0) return null
  return (
    <Section title="개념별 결과" hint="약한 개념부터. 숙련도는 시험 전 → 후">
      <div className="overflow-x-auto">
        <table className="w-full min-w-[600px] text-sm">
          <thead className="text-left text-xs text-ink-2">
            <tr>
              <th scope="col" className="px-2.5 py-2 font-bold">개념</th>
              <th scope="col" className="px-2.5 py-2 text-right font-bold">맞힘</th>
              <th scope="col" className="px-2.5 py-2 text-right font-bold">숙련도</th>
              <th scope="col" className="px-2.5 py-2 font-bold">의심 오개념</th>
              <th scope="col" className="px-2.5 py-2 font-bold">다시 볼 곳</th>
              <th scope="col" className="px-2.5 py-2 font-bold">상태</th>
            </tr>
          </thead>
          <tbody>
            {concepts.map((c) => {
              const weak = c.correct < c.total
              const diff = Math.round((c.after - c.before) * 100)
              return (
                <tr key={c.name} className="border-t border-home-line align-top">
                  <td className="px-2.5 py-3">
                    <div className="font-bold">{c.name}</div>
                    <div className="text-xs text-ink-2">{c.chapter}</div>
                  </td>
                  <td className="px-2.5 py-3 text-right tabular-nums">
                    {c.correct}/{c.total}
                  </td>
                  <td className="whitespace-nowrap px-2.5 py-3 text-right tabular-nums">
                    {pct(c.before)} → <b>{pct(c.after)}</b>
                    <span
                      className={cn(
                        'ml-1 text-xs',
                        diff > 0 ? 'text-[#1f6b51]' : diff < 0 ? 'text-[#a3352f]' : 'text-ink-2',
                      )}
                    >
                      {diff > 0 ? `▲${diff}` : diff < 0 ? `▼${-diff}` : '–'}
                    </span>
                  </td>
                  <td className="px-2.5 py-3">
                    {c.labels.length === 0 ? (
                      <span className="text-ink-2">–</span>
                    ) : (
                      c.labels.map((l) => (
                        <div key={l.label}>
                          {l.label}
                          {l.count > 1 && <span className="text-ink-2"> ×{l.count}</span>}
                        </div>
                      ))
                    )}
                  </td>
                  <td className="px-2.5 py-3 text-xs">
                    {c.pages.length === 0 ? '–' : c.pages.map((p) => <div key={p}>{p}</div>)}
                  </td>
                  <td className="px-2.5 py-3">
                    <span
                      className={cn(
                        'whitespace-nowrap rounded-full px-2.5 py-1 text-xs font-bold',
                        weak ? 'bg-[#fdf0ef] text-[#a3352f]' : 'bg-[#e3f2ec] text-[#1f6b51]',
                      )}
                    >
                      {weak ? '다시 보기' : '안정'}
                    </span>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </Section>
  )
}

/** 결과 화면의 차트 묶음. 차트 라이브러리가 커서 결과를 열 때만 따로 불러온다(PaperPage에서 lazy). */
export default function ReportCharts({ report }: { report: ReportT }) {
  return (
    <>
      <div className="grid gap-4 md:grid-cols-2">
        <ChapterChart chapters={report.chapters} />
        <Distribution dist={report.distribution} />
      </div>
      <FlowTable flows={report.flows} blanks={report.blank_nos} />
      <ConceptTable concepts={report.concepts} />
    </>
  )
}

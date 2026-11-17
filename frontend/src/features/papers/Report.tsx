// 시험 결과 학습 리포트: 챕터 숙련도(전/후), 응시자 중 내 위치, 오답 흐름(Sankey), 개념별 상태 표.
// 데이터는 백엔드 report(build_report)가 다 계산해서 준다. 여기서는 그리기만 한다.
import { ResponsiveSankey } from '@nivo/sankey'
import {
  Bar,
  BarChart,
  Cell,
  Legend,
  PolarAngleAxis,
  PolarGrid,
  PolarRadiusAxis,
  Radar,
  RadarChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import type { Schemas } from '@/api/client'
import { Badge } from '@/components/ui/badge'
import { Card } from '@/components/ui/card'
import { cn } from '@/lib/utils'

type ReportT = Schemas['ReportOut']

// 오답 흐름 노드 색: 왼쪽부터 문제 → 오개념 → 개념 → 교안 쪽(이웃끼리 색맹에서도 구분되게 검사한 값).
// 노드마다 이름이 붙어 있고 열 위치도 종류를 나타내므로 색만으로 구분하지 않는다.
const KIND_COLOR: Record<string, string> = {
  problem: '#d9480f',
  misconception: '#2563eb',
  concept: '#a16207',
  page: '#7c3aed',
}
const KIND_LABEL: Record<string, string> = {
  problem: '틀린 문제',
  misconception: '의심 오개념',
  concept: '개념',
  page: '다시 볼 교안',
}
const pct = (x: number) => `${Math.round(x * 100)}%`
const nameOf = (id: string) => id.slice(id.indexOf(':') + 1)

export function Section({
  title,
  hint,
  children,
}: {
  title: string
  hint?: string
  children: React.ReactNode
}) {
  return (
    <Card className="flex flex-col gap-3 p-4">
      <div>
        <h3 className="font-semibold">{title}</h3>
        {hint && <p className="text-xs text-muted-foreground">{hint}</p>}
      </div>
      {children}
    </Card>
  )
}

export function ChapterChart({ chapters }: { chapters: ReportT['chapters'] }) {
  if (chapters.length === 0) return null
  const data = chapters.map((c) => ({
    name: c.title,
    before: Math.round(c.before * 100),
    after: Math.round(c.after * 100),
  }))
  const tip = (
    <Tooltip
      formatter={(v: number, k: string) => [`${v}%`, k === 'before' ? '시험 전' : '시험 후']}
      contentStyle={{ fontSize: 12, borderRadius: 8 }}
    />
  )
  const legend = (
    <Legend
      formatter={(k: string) => (k === 'before' ? '시험 전' : '시험 후')}
      wrapperStyle={{ fontSize: 12 }}
    />
  )
  return (
    <Section title="챕터별 숙련도" hint="이번 시험 전과 후. 숙련도는 풀이 기록으로 계산한 '알고 있을 확률'">
      <div className="h-64 w-full">
        <ResponsiveContainer>
          {data.length >= 3 ? (
            <RadarChart data={data} outerRadius="72%">
              <PolarGrid stroke="var(--border)" />
              <PolarAngleAxis dataKey="name" tick={{ fontSize: 11, fill: 'var(--muted-foreground)' }} />
              <PolarRadiusAxis domain={[0, 100]} tick={false} axisLine={false} />
              <Radar
                isAnimationActive={false}
                dataKey="before"
                stroke="var(--muted-foreground)"
                strokeDasharray="4 3"
                strokeWidth={2}
                fill="var(--muted-foreground)"
                fillOpacity={0.08}
              />
              <Radar
                isAnimationActive={false}
                dataKey="after"
                stroke="var(--primary)"
                strokeWidth={2}
                fill="var(--primary)"
                fillOpacity={0.2}
              />
              {tip}
              {legend}
            </RadarChart>
          ) : (
            <BarChart data={data} layout="vertical" margin={{ left: 8, right: 16 }} barGap={2}>
              <XAxis type="number" domain={[0, 100]} unit="%" tick={{ fontSize: 11 }} />
              <YAxis type="category" dataKey="name" width={90} tick={{ fontSize: 11 }} />
              <Bar isAnimationActive={false} dataKey="before" fill="var(--muted-foreground)" fillOpacity={0.45} radius={[0, 4, 4, 0]} />
              <Bar isAnimationActive={false} dataKey="after" fill="var(--primary)" radius={[0, 4, 4, 0]} />
              {tip}
              {legend}
            </BarChart>
          )}
        </ResponsiveContainer>
      </div>
    </Section>
  )
}

export function Distribution({ dist }: { dist: ReportT['distribution'] }) {
  if (dist.length === 0) return null
  const total = dist[0].total_points
  const data = dist.map((d, i) => ({ key: i, score: d.score, rank: d.rank, me: d.me }))
  return (
    <Section title="같은 시험지 응시자 중 내 위치" hint={`응시자 ${dist.length}명, 점수 높은 순`}>
      <div className="h-40 w-full">
        <ResponsiveContainer>
          <BarChart data={data} margin={{ left: -20, right: 8 }}>
            <XAxis dataKey="rank" tick={{ fontSize: 11 }} tickFormatter={(r) => `${r}등`} />
            <YAxis domain={[0, total]} allowDecimals={false} tick={{ fontSize: 11 }} />
            <Tooltip
              cursor={{ fill: 'var(--muted)' }}
              formatter={(v: number) => [`${v}/${total}점`, '점수']}
              labelFormatter={(r) => `${r}등`}
              contentStyle={{ fontSize: 12, borderRadius: 8 }}
            />
            <Bar isAnimationActive={false} dataKey="score" radius={[4, 4, 0, 0]} maxBarSize={36}>
              {data.map((d) => (
                <Cell
                  key={d.key}
                  fill={d.me ? 'var(--primary)' : 'var(--muted-foreground)'}
                  fillOpacity={d.me ? 1 : 0.35}
                />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
      <p className="text-xs text-muted-foreground">진한 막대가 나</p>
    </Section>
  )
}

export function WrongFlow({ report }: { report: ReportT }) {
  if (report.sankey_links.length === 0) return null
  const data = {
    nodes: report.sankey_nodes.map((n) => ({ id: n.id, kind: n.kind })),
    links: report.sankey_links,
  }
  const rows = new Set(report.sankey_nodes.map((n) => n.id)).size
  return (
    <Section
      title="오답 흐름"
      hint="틀린 문제 → 의심되는 오개념 → 개념 → 다시 볼 교안 쪽. 띠가 굵을수록 여러 문제가 몰린 약점"
    >
      <div className="flex flex-wrap gap-3 text-xs">
        {Object.entries(KIND_LABEL).map(([k, v]) => (
          <span key={k} className="flex items-center gap-1">
            <span className="size-2.5 rounded-sm" style={{ background: KIND_COLOR[k] }} />
            {v}
          </span>
        ))}
      </div>
      <div className="w-full overflow-x-auto">
        <div style={{ height: Math.max(220, rows * 22), minWidth: 640 }}>
          <ResponsiveSankey
            data={data}
            margin={{ top: 8, right: 150, bottom: 8, left: 64 }}
            align="justify"
            sort="input"
            animate={false}
            colors={(n: { kind?: string }) => KIND_COLOR[n.kind ?? 'page']}
            nodeOpacity={1}
            nodeThickness={12}
            nodeSpacing={14}
            nodeBorderWidth={0}
            nodeBorderRadius={2}
            linkOpacity={0.35}
            linkHoverOpacity={0.6}
            linkBlendMode="normal"
            enableLinkGradient
            label={(n) => nameOf(String(n.id))}
            labelPosition="outside"
            labelPadding={8}
            labelTextColor="var(--foreground)"
            theme={{ labels: { text: { fontSize: 11 } }, tooltip: { container: { fontSize: 12 } } }}
            nodeTooltip={({ node }) => (
              <div className="rounded-md border bg-card px-2 py-1 text-xs shadow">
                {KIND_LABEL[(node as unknown as { kind: string }).kind]} · {nameOf(String(node.id))} (
                {node.value}문항)
              </div>
            )}
            linkTooltip={({ link }) => (
              <div className="rounded-md border bg-card px-2 py-1 text-xs shadow">
                {nameOf(String(link.source.id))} → {nameOf(String(link.target.id))} ({link.value}
                문항)
              </div>
            )}
          />
        </div>
      </div>
    </Section>
  )
}

export function ConceptTable({ concepts }: { concepts: ReportT['concepts'] }) {
  if (concepts.length === 0) return null
  return (
    <Section title="개념별 상태" hint="약한 개념부터. 숙련도는 시험 전 → 후">
      <div className="overflow-x-auto">
        <table className="w-full min-w-[560px] text-sm">
          <thead className="text-left text-xs text-muted-foreground">
            <tr className="border-b">
              <th className="py-2 pr-3 font-medium">개념</th>
              <th className="py-2 pr-3 font-medium">맞힘</th>
              <th className="py-2 pr-3 font-medium">숙련도</th>
              <th className="py-2 pr-3 font-medium">의심 오개념</th>
              <th className="py-2 pr-3 font-medium">다시 볼 곳</th>
              <th className="py-2 font-medium">상태</th>
            </tr>
          </thead>
          <tbody>
            {concepts.map((c) => {
              const weak = c.correct < c.total
              const diff = Math.round((c.after - c.before) * 100)
              return (
                <tr key={c.name} className="border-b last:border-0 align-top">
                  <td className="py-2 pr-3">
                    <div className="font-medium">{c.name}</div>
                    <div className="text-xs text-muted-foreground">{c.chapter}</div>
                  </td>
                  <td className="py-2 pr-3 tabular-nums">
                    {c.correct}/{c.total}
                  </td>
                  <td className="py-2 pr-3 tabular-nums">
                    {pct(c.before)} → <b>{pct(c.after)}</b>
                    <span
                      className={cn(
                        'ml-1 text-xs',
                        diff > 0 ? 'text-success' : diff < 0 ? 'text-destructive' : 'text-muted-foreground',
                      )}
                    >
                      {diff > 0 ? `▲${diff}` : diff < 0 ? `▼${-diff}` : '–'}
                    </span>
                  </td>
                  <td className="py-2 pr-3">
                    {c.labels.length === 0 ? (
                      <span className="text-muted-foreground">–</span>
                    ) : (
                      c.labels.map((l) => (
                        <div key={l.label}>
                          {l.label}
                          {l.count > 1 && <span className="text-muted-foreground"> ×{l.count}</span>}
                        </div>
                      ))
                    )}
                  </td>
                  <td className="py-2 pr-3 text-xs">
                    {c.pages.length === 0 ? '–' : c.pages.map((p) => <div key={p}>{p}</div>)}
                  </td>
                  <td className="py-2">
                    <Badge
                      variant="outline"
                      className={weak ? 'border-destructive text-destructive' : 'border-success text-success'}
                    >
                      {weak ? '약점' : '양호'}
                    </Badge>
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
      <WrongFlow report={report} />
      <ConceptTable concepts={report.concepts} />
    </>
  )
}

// 시험 결과 학습 리포트: 챕터 숙련도(전/후), 응시자 중 내 위치, 오답 흐름(Sankey), 개념별 상태 표.
// 데이터는 백엔드 report(build_report)가 다 계산해서 준다. 여기서는 그리기만 한다.
import { type CustomSankeyLayerProps, ResponsiveSankey } from '@nivo/sankey'
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
  unknown: '#9ca3af', // 오개념 추정 없음
}
const LINK_GRAY = '#9ca3af'
const KIND_LABEL: Record<string, string> = {
  problem: '틀린 문제',
  misconception: '의심 오개념',
  unknown: '의심 오개념',
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

type FlowNode = { id: string; kind: string }
type FlowLink = { source: string; target: string; value: number; startColor: string; endColor: string }

// 교안 제목 앞의 과목명은 줄인다: '기초프로그래밍 교안 1 54쪽' → '교안 1 · 54쪽'
const shortName = (id: string) => nameOf(id).replace(/^\S+\s(?=(교안|족보|자료))/, '').replace(/ (\d+쪽)$/, ' · $1')

// 열 머리글과 이름표. 이름표는 바탕색 테두리를 둘러 띠 위에서도 읽히게 한다
function FlowLabels({
  nodes,
  width,
  currentNode,
}: CustomSankeyLayerProps<FlowNode, FlowLink>) {
  const cols = new Map<string, number>()
  for (const n of nodes) cols.set(n.kind === 'unknown' ? 'misconception' : n.kind, (n.x0 + n.x1) / 2)
  const near = currentNode
    ? new Set([
        currentNode.id,
        ...currentNode.sourceLinks.map((l) => l.target.id),
        ...currentNode.targetLinks.map((l) => l.source.id),
      ])
    : null
  return (
    <g>
      {[...cols].map(([k, x], i, arr) => (
        <text
          key={k}
          x={x}
          y={-14}
          textAnchor={i === 0 ? 'start' : i === arr.length - 1 ? 'end' : 'middle'}
          dx={i === 0 ? -6 : i === arr.length - 1 ? 6 : 0}
          style={{ fontSize: 11, fontWeight: 600, fill: 'var(--muted-foreground)' }}
        >
          {KIND_LABEL[k]}
        </text>
      ))}
      {nodes.map((n) => {
        const last = n.x1 >= width - 1
        const first = n.x0 <= 1
        const x = last ? n.x0 - 8 : n.x1 + 8
        return (
          <text
            key={n.id}
            x={first ? n.x0 - 8 : x}
            y={(n.y0 + n.y1) / 2}
            dominantBaseline="central"
            textAnchor={first || last ? 'end' : 'start'}
            paintOrder="stroke"
            stroke="var(--card)"
            strokeWidth={4}
            strokeLinejoin="round"
            opacity={near && !near.has(n.id) ? 0.25 : 1}
            style={{
              fontSize: 12,
              fontWeight: n.kind === 'problem' ? 600 : 500,
              fill: n.kind === 'unknown' ? 'var(--muted-foreground)' : 'var(--foreground)',
              pointerEvents: 'none',
            }}
          >
            {shortName(n.id)}
            {n.kind === 'concept' && n.value > 1 ? ` ×${n.value}` : ''}
          </text>
        )
      })}
    </g>
  )
}

export function WrongFlow({ report }: { report: ReportT }) {
  const blankNos = report.blank_nos
  if (report.sankey_links.length === 0)
    return blankNos.length > 0 ? (
      <Section title="오답 흐름">
        <p className="text-sm text-muted-foreground">
          고른 오답이 없어 흐름이 없습니다. 빈칸 {blankNos.join(', ')}번.
        </p>
      </Section>
    ) : null
  const nodes: FlowNode[] = report.sankey_nodes.map((n) => ({ id: n.id, kind: n.kind }))
  const links: FlowLink[] = report.sankey_links.map((l) => ({
    ...l,
    startColor: LINK_GRAY,
    endColor: LINK_GRAY,
  }))
  const perCol = new Map<string, number>()
  for (const n of nodes) {
    const k = n.kind === 'unknown' ? 'misconception' : n.kind
    perCol.set(k, (perCol.get(k) ?? 0) + 1)
  }
  const tallest = Math.max(...perCol.values())
  return (
    <Section
      title="오답 흐름"
      hint="틀린 문제가 어떤 오개념 → 개념 → 교안 쪽으로 이어지는지. 띠가 굵을수록 여러 문제가 몰린 곳, 항목에 마우스를 올리면 그 흐름만 보입니다"
    >
      <div className="w-full overflow-x-auto">
        <div style={{ height: tallest * 40 + 40, minWidth: 720 }}>
          <ResponsiveSankey<FlowNode, FlowLink>
            data={{ nodes, links }}
            margin={{ top: 28, right: 130, bottom: 8, left: 56 }}
            align="justify"
            sort="auto"
            animate={false}
            colors={(n) => KIND_COLOR[n.kind]}
            nodeOpacity={1}
            nodeHoverOthersOpacity={0.25}
            nodeThickness={10}
            nodeSpacing={22}
            nodeInnerPadding={0}
            nodeBorderWidth={0}
            nodeBorderRadius={3}
            linkOpacity={0.35}
            linkHoverOpacity={0.75}
            linkHoverOthersOpacity={0.08}
            linkContract={2}
            linkBlendMode="normal"
            enableLinkGradient
            enableLabels={false}
            layers={['links', 'nodes', FlowLabels]}
            nodeTooltip={({ node }) => (
              <div className="whitespace-nowrap rounded-md border bg-card px-2 py-1 text-xs shadow">
                {KIND_LABEL[node.kind]} · {nameOf(node.id)} ({node.value}문항)
              </div>
            )}
            linkTooltip={({ link }) => (
              <div className="whitespace-nowrap rounded-md border bg-card px-2 py-1 text-xs shadow">
                {nameOf(link.source.id)} → {nameOf(link.target.id)} ({link.value}문항)
              </div>
            )}
          />
        </div>
      </div>
      {blankNos.length > 0 && (
        <p className="text-xs text-muted-foreground">
          빈칸으로 둔 {blankNos.join(', ')}번은 고른 보기가 없어 흐름에서 뺐습니다. 아래 문제별 결과에서
          해설을 확인하세요.
        </p>
      )}
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

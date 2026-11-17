// 오답 흐름: 틀린 문제 → 의심 오개념 → 개념 → 다시 볼 교안 쪽.
// 세로 배치만 d3-sankey로 계산하고, 띠는 SVG로, 각 칸(칩)은 HTML로 직접 그린다(글자·아이콘·말줄임을 자유롭게).
// 띠 색 = 그 문제가 닿는 개념(범주형 팔레트, 개념 칩의 색 점과 이름이 같이 있어 색만으로 구분하지 않음).
import { sankey, type SankeyLink, type SankeyNode } from 'd3-sankey'
import { BookOpen, Brain, CircleHelp, MousePointerClick, Target } from 'lucide-react'
import { useLayoutEffect, useMemo, useRef, useState } from 'react'
import type { Schemas } from '@/api/client'
import { cn } from '@/lib/utils'

type Flow = Schemas['Flow']
type Kind = 'problem' | 'misconception' | 'unknown' | 'concept' | 'page'
type N = { id: string; kind: Kind; name: string; col: number; nos: Set<number> }
type L = { source: string; target: string; value: number; concept: string | null; nos: number[] }
type LN = SankeyNode<N, L>
type LL = SankeyLink<N, L>

// 범주형 팔레트(검증된 순서, 이웃끼리 색맹에서도 구분). 8개를 넘는 개념은 회색
const PALETTE = ['#2a78d6', '#eb6834', '#1baf7a', '#eda100', '#e87ba4', '#008300', '#6250d6', '#e34948']
const GRAY = '#a3a3a3'
const COL_W = [56, 188, 196, 136] // 열별 칩 너비
const COL_TITLE = ['틀린 문제', '의심 오개념', '개념', '다시 볼 교안']
const PX_PER_Q = 18 // 문제 하나당 띠 두께
const PAD = 16 // 같은 열 칩 사이 간격
const CHIP_MIN_H = 30
const TOP = 30 // 열 머리글 자리

const shortPage = (s: string) =>
  s.replace(/^\S+\s(?=(교안|족보|자료))/, '').replace(/ (\d+쪽)$/, ' · $1')

function build(flows: Flow[]) {
  const nodes = new Map<string, N>()
  const links = new Map<string, L>()
  const node = (kind: Kind, name: string, col: number, no: number) => {
    const id = `${kind}:${name}`
    const n = nodes.get(id) ?? { id, kind, name, col, nos: new Set<number>() }
    n.nos.add(no)
    nodes.set(id, n)
    return id
  }
  for (const f of flows) {
    const chain = [node('problem', `${f.no}번`, 0, f.no)]
    chain.push(
      f.misconception
        ? node('misconception', f.misconception, 1, f.no)
        : node('unknown', '추정 없음', 1, f.no),
    )
    if (f.concept) chain.push(node('concept', f.concept, 2, f.no))
    if (f.concept && f.page) chain.push(node('page', f.page, 3, f.no))
    for (let i = 0; i + 1 < chain.length; i++) {
      const key = `${chain[i]}→${chain[i + 1]}→${f.concept}`
      const l = links.get(key) ?? {
        source: chain[i],
        target: chain[i + 1],
        value: 0,
        concept: f.concept ?? null,
        nos: [],
      }
      l.value += 1
      l.nos.push(f.no)
      links.set(key, l)
    }
  }
  return { nodes: [...nodes.values()], links: [...links.values()] }
}

function useWidth() {
  const ref = useRef<HTMLDivElement>(null)
  const [w, setW] = useState(0)
  useLayoutEffect(() => {
    if (!ref.current) return
    const ro = new ResizeObserver(([e]) => setW(e.contentRect.width))
    ro.observe(ref.current)
    return () => ro.disconnect()
  }, [])
  return [ref, w] as const
}

export function WrongFlow({ flows, blanks }: { flows: Flow[]; blanks: number[] }) {
  const [boxRef, boxW] = useWidth()
  const W = Math.max(780, boxW)
  const [active, setActive] = useState<{ nos: Set<number>; label: string } | null>(null)

  const g = useMemo(() => {
    if (flows.length === 0) return null
    const { nodes, links } = build(flows)
    // 개념 색: 많이 틀린 개념부터 팔레트 순서대로
    const conceptCount = new Map<string, number>()
    for (const f of flows) if (f.concept) conceptCount.set(f.concept, (conceptCount.get(f.concept) ?? 0) + 1)
    const order = [...conceptCount].sort((a, b) => b[1] - a[1]).map(([c]) => c)
    const color = (c: string | null) => {
      const i = c == null ? -1 : order.indexOf(c)
      return i >= 0 && i < PALETTE.length ? PALETTE[i] : GRAY
    }
    const perCol = [0, 0, 0, 0]
    for (const n of nodes) perCol[n.col]++
    const H = flows.length * PX_PER_Q + (Math.max(...perCol) - 1) * (PAD + CHIP_MIN_H - PX_PER_Q)
    const layout = sankey<N, L>()
      .nodeId((d) => d.id)
      .nodeAlign((d) => (d as LN).col)
      .nodeWidth(1)
      .nodePadding(PAD + CHIP_MIN_H - PX_PER_Q)
      .extent([
        [0, TOP],
        [W, TOP + H],
      ])
    const res = layout({ nodes: nodes.map((n) => ({ ...n })), links: links.map((l) => ({ ...l })) })
    // 열 위치: 칩 너비를 빼고 남는 폭을 열 사이에 고르게
    const gap = (W - COL_W.reduce((a, b) => a + b, 0)) / 3
    const left = COL_W.map((_, i) => COL_W.slice(0, i).reduce((a, b) => a + b, 0) + i * gap)
    const top = (n: LN) => {
      const h = Math.max(n.y1! - n.y0!, CHIP_MIN_H)
      return { y: (n.y0! + n.y1!) / 2 - h / 2, h }
    }
    const topConcept = order[0]
    const topPages = [
      ...new Set(flows.filter((f) => f.concept === topConcept && f.page).map((f) => f.page!)),
    ]
    return { res, left, top, color, H, order, conceptCount, topConcept, topPages }
  }, [flows, W])

  if (!g) {
    return blanks.length ? (
      <p className="text-sm text-muted-foreground">
        고른 오답이 없습니다. 빈칸 {blanks.join(', ')}번.
      </p>
    ) : null
  }
  const { res, left, top, color, H } = g
  const on = (nos: Iterable<number>) => !active || [...nos].some((n) => active.nos.has(n))
  const jump = (no: number) => {
    const el = document.getElementById(`q-${no}`)
    el?.scrollIntoView({ behavior: 'smooth', block: 'center' })
    el?.animate(
      [{ boxShadow: '0 0 0 3px var(--primary)' }, { boxShadow: '0 0 0 0 transparent' }],
      { duration: 1400 },
    )
  }

  return (
    <div className="flex flex-col gap-3">
      {/* 한 줄 결론 + 마우스 올린 곳 설명 */}
      <div className="flex min-h-11 flex-wrap items-center gap-x-2 gap-y-1 rounded-lg border bg-muted/40 px-3 py-2 text-sm">
        {active ? (
          <>
            <MousePointerClick className="size-4 text-muted-foreground" />
            <b>{active.label}</b>
            <span className="text-muted-foreground">
              · {[...active.nos].sort((a, b) => a - b).join(', ')}번
            </span>
          </>
        ) : (
          <>
            <Target className="size-4" style={{ color: color(g.topConcept) }} />
            가장 많이 몰린 개념
            <b style={{ color: color(g.topConcept) }}>{g.topConcept}</b>
            <span className="text-muted-foreground">{g.conceptCount.get(g.topConcept)}문항</span>
            {g.topPages.length > 0 && (
              <>
                <span className="text-muted-foreground">→</span>
                <span className="font-medium">{g.topPages.map(shortPage).join(', ')}</span>
                <span className="text-muted-foreground">부터 다시 보기</span>
              </>
            )}
          </>
        )}
      </div>

      {boxW > 0 && boxW < 780 && (
        <p className="text-xs text-muted-foreground">← 옆으로 밀어서 끝까지 보기 →</p>
      )}
      <div ref={boxRef} className="w-full overflow-x-auto">
        <div className="relative" style={{ width: W, height: TOP + H + 8 }}>
          {/* 열 머리글 */}
          {COL_TITLE.map((t, i) => (
            <div
              key={t}
              className="absolute top-0 text-[11px] font-semibold tracking-wide text-muted-foreground"
              style={{ left: left[i], width: COL_W[i], textAlign: i === 0 ? 'left' : 'left' }}
            >
              {t}
            </div>
          ))}
          {/* 띠 */}
          <svg width={W} height={TOP + H + 8} className="absolute inset-0" aria-hidden>
            <defs>
              {res.links.map((l, i) => {
                const s = l.source as LN
                const t = l.target as LN
                return (
                  <linearGradient
                    key={i}
                    id={`wf-${i}`}
                    gradientUnits="userSpaceOnUse"
                    x1={left[s.col] + COL_W[s.col]}
                    x2={left[t.col]}
                  >
                    <stop offset="0%" stopColor={color(l.concept)} stopOpacity={s.col === 0 ? 0.55 : 0.9} />
                    <stop offset="100%" stopColor={color(l.concept)} stopOpacity={0.9} />
                  </linearGradient>
                )
              })}
            </defs>
            {res.links.map((l: LL, i) => {
              const s = l.source as LN
              const t = l.target as LN
              const x0 = left[s.col] + COL_W[s.col]
              const x1 = left[t.col]
              const mx = (x0 + x1) / 2
              const lit = on(l.nos)
              return (
                <path
                  key={i}
                  d={`M${x0},${l.y0} C${mx},${l.y0} ${mx},${l.y1} ${x1},${l.y1}`}
                  fill="none"
                  stroke={`url(#wf-${i})`}
                  strokeWidth={Math.max(2, l.width! - 2)}
                  strokeOpacity={!active ? 0.42 : lit ? 0.85 : 0.06}
                  className="cursor-pointer transition-[stroke-opacity] duration-200"
                  onMouseEnter={() =>
                    setActive({
                      nos: new Set(l.nos),
                      label: `${s.name.replace(/^/, '')} → ${t.kind === 'page' ? shortPage(t.name) : t.name}`,
                    })
                  }
                  onMouseLeave={() => setActive(null)}
                >
                  <title>
                    {s.name} → {t.name} ({l.value}문항)
                  </title>
                </path>
              )
            })}
          </svg>
          {/* 칩 */}
          {(res.nodes as LN[]).map((n) => {
            const { y, h } = top(n)
            const lit = on(n.nos)
            const count = n.nos.size
            const conceptColor = n.kind === 'concept' ? color(n.name) : undefined
            const label = n.kind === 'page' ? shortPage(n.name) : n.name
            return (
              <div
                key={n.id}
                role={n.kind === 'problem' ? 'button' : undefined}
                tabIndex={n.kind === 'problem' ? 0 : undefined}
                title={`${n.name}${count > 1 ? ` · ${count}문항` : ''}${n.kind === 'problem' ? ' · 눌러서 문제로 이동' : ''}`}
                onMouseEnter={() => setActive({ nos: n.nos, label })}
                onMouseLeave={() => setActive(null)}
                onClick={() => n.kind === 'problem' && jump([...n.nos][0])}
                onKeyDown={(e) => e.key === 'Enter' && n.kind === 'problem' && jump([...n.nos][0])}
                className={cn(
                  'absolute flex items-center gap-1.5 overflow-hidden rounded-lg border px-2.5 text-xs shadow-sm transition-[opacity,transform] duration-200',
                  lit ? 'opacity-100' : 'opacity-25',
                  active && lit && 'shadow-md',
                  n.kind === 'problem' &&
                    'cursor-pointer justify-center rounded-full border-transparent bg-foreground px-0 font-semibold text-background hover:scale-105',
                  n.kind === 'misconception' && 'bg-card',
                  n.kind === 'unknown' && 'border-dashed bg-card text-muted-foreground shadow-none',
                  n.kind === 'page' && 'bg-muted font-medium',
                )}
                style={{
                  left: left[n.col],
                  top: y,
                  width: COL_W[n.col],
                  height: h,
                  ...(conceptColor && {
                    background: `color-mix(in oklab, ${conceptColor} 12%, var(--card))`,
                    borderColor: `color-mix(in oklab, ${conceptColor} 45%, var(--card))`,
                  }),
                }}
              >
                {n.kind === 'misconception' && <Brain className="size-3.5 shrink-0 text-muted-foreground" />}
                {n.kind === 'unknown' && <CircleHelp className="size-3.5 shrink-0" />}
                {n.kind === 'concept' && (
                  <span className="size-2.5 shrink-0 rounded-full" style={{ background: conceptColor }} />
                )}
                {n.kind === 'page' && <BookOpen className="size-3.5 shrink-0 text-muted-foreground" />}
                <span className={cn('truncate', n.kind === 'concept' && 'font-semibold')}>{label}</span>
                {n.kind !== 'problem' && count > 1 && (
                  <span
                    className="ml-auto shrink-0 rounded-full bg-foreground/10 px-1.5 py-px text-[10px] font-semibold tabular-nums"
                    style={conceptColor ? { background: conceptColor, color: 'white' } : undefined}
                  >
                    ×{count}
                  </span>
                )}
              </div>
            )
          })}
        </div>
      </div>
      <p className="text-xs text-muted-foreground">
        띠 색은 개념별이고, 굵을수록 여러 문제가 몰린 길입니다. 칸에 마우스를 올리면 그 길만 보이고,
        문제 번호를 누르면 아래 해설로 갑니다.
        {blanks.length > 0 && ` 빈칸으로 둔 ${blanks.join(', ')}번은 고른 보기가 없어 뺐습니다.`}
      </p>
    </div>
  )
}

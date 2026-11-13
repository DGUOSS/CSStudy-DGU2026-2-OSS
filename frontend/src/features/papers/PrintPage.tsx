import { ChevronLeft, Printer } from 'lucide-react'
import { Link, useParams } from 'react-router'
import { ErrorText, Loading } from '@/components/States'
import { Button } from '@/components/ui/button'
import { usePaper, useSheet } from './queries'

const CIRCLED = ['①', '②', '③', '④', '⑤', '⑥', '⑦', '⑧']

/**
 * 인쇄 화면: 문제지 쪽들 + 마지막에 답안지(쪽마다 A4 한 장, 네 귀퉁이 표시는 사진 인식용).
 * 브라우저 인쇄에서 'PDF로 저장'도 된다. 답안지 크기가 바뀌면 인식이 어려우니 배율은 100%로.
 */
export function PrintPage() {
  const paperId = Number(useParams().paperId)
  const paper = usePaper(paperId)
  const sheet = useSheet(paperId)
  if (paper.isPending || sheet.isPending) return <Loading />
  if (!paper.data || !sheet.data) return <ErrorText error={paper.error ?? sheet.error} />
  const p = paper.data

  return (
    <div>
      <style>{`
        @page { size: A4; margin: 0; }
        @media print {
          html, body { background: #fff !important; }
          .paper-page { box-shadow: none !important; margin: 0 !important; }
        }
        .paper-page { width: 210mm; min-height: 297mm; background: #fff; color: #000; margin: 0 auto 16px;
          box-shadow: 0 2px 12px rgba(0,0,0,.15); break-after: page; }
        .paper-page:last-child { break-after: auto; }
        .paper-q { break-inside: avoid; }
        .paper-questions { -webkit-box-decoration-break: clone; box-decoration-break: clone; }
      `}</style>
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3 print:hidden">
        <Link
          to={`/papers/${paperId}`}
          className="inline-flex items-center text-sm text-muted-foreground"
        >
          <ChevronLeft className="size-4" />
          시험지로
        </Link>
        <div className="flex items-center gap-3">
          <span className="text-xs text-muted-foreground">
            인쇄 설정에서 용지 A4, 배율 100%(기본), 여백 없음으로 맞추세요.
          </span>
          <Button onClick={() => window.print()}>
            <Printer />
            인쇄하기
          </Button>
        </div>
      </div>

      <div className="paper-page paper-questions" style={{ padding: '16mm 16mm 14mm' }}>
        <div className="mb-4 border-b-2 border-black pb-2">
          <div className="text-xl font-bold">{p.title}</div>
          <div className="text-sm">
            시험지 #{p.id} · {p.problems.length}문항 · {p.total_points}점 · 제한 시간{' '}
            {p.time_limit_min}분 · 답은 마지막 장 답안지에 표시하세요
          </div>
        </div>
        <ol className="flex flex-col gap-4 text-[13px] leading-relaxed">
          {p.problems.map((q) => (
            <li key={q.id} className="paper-q">
              <div className="whitespace-pre-wrap">
                <b>{q.no}.</b> {q.question}{' '}
                <span className="text-[11px] text-neutral-500">
                  ({q.points}점{q.qtype !== 'mcq' && ', 서술형 — 답안지 칸에 쓰세요'})
                </span>
              </div>
              {q.qtype === 'mcq' && (
                <div className="mt-1 grid gap-0.5 pl-4">
                  {q.choices.map((c, i) => (
                    <div key={i} className="whitespace-pre-wrap">
                      {CIRCLED[i]} {c}
                    </div>
                  ))}
                </div>
              )}
            </li>
          ))}
        </ol>
      </div>

      {sheet.data.pages.map((svg, i) => (
        // 서버가 만든 SVG(제목은 서버에서 escape)
        <div key={i} className="paper-page" dangerouslySetInnerHTML={{ __html: svg }} />
      ))}
    </div>
  )
}

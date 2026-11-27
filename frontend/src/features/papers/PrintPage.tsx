import { ChevronLeft, Download, Printer } from 'lucide-react'
import { Link, useLocation, useParams } from 'react-router'
import { ErrorText, Loading } from '@/components/States'
import { usePaper, useSheet } from './queries'
import { downloadSheetPngs } from './sheetImage'

const CIRCLED = ['①', '②', '③', '④', '⑤', '⑥', '⑦', '⑧']

/**
 * 인쇄 화면: 문제지 쪽들 + 마지막에 답안지(쪽마다 A4 한 장, 네 귀퉁이 표시는 사진 인식용).
 * 브라우저 인쇄에서 'PDF로 저장'도 된다. 답안지 크기가 바뀌면 인식이 어려우니 배율은 100%로.
 */
export function PrintPage() {
  const paperId = Number(useParams().paperId)
  const paper = usePaper(paperId)
  const sheet = useSheet(paperId)
  const inStudy = useLocation().pathname.startsWith('/study/')
  if (paper.isPending || sheet.isPending) return <Loading />
  if (!paper.data || !sheet.data) return <ErrorText error={paper.error ?? sheet.error} />
  const p = paper.data

  return (
    <div className="pb-10">
      <style>{`
        @page { size: A4; margin: 0; }
        @media print {
          html, body { background: #fff !important; }
          .paper-page { border: 0 !important; margin: 0 !important; }
        }
        .paper-page { width: 210mm; min-height: 297mm; background: #fff; color: #000; margin: 0 auto 20px;
          border: 1px solid #e1e5ee; break-after: page; }
        .paper-page:last-child { break-after: auto; }
        .paper-q { break-inside: avoid; }
        .paper-questions { -webkit-box-decoration-break: clone; box-decoration-break: clone; }
      `}</style>
      {/* 화면에서만 보이는 도구 줄 (인쇄할 때는 숨김). 아래 문제지·답안지는 인쇄물이라 흑백 그대로 */}
      <div className="sticky top-0 z-10 mb-6 border-b border-home-line bg-white/95 backdrop-blur print:hidden">
        <div className="mx-auto flex max-w-[210mm] flex-wrap items-center justify-between gap-3 px-4 py-3">
          <div className="min-w-0">
            <Link
              to={inStudy ? `/study/papers/${paperId}` : `/papers/${paperId}`}
              className="inline-flex items-center text-sm text-ink-2 hover:text-navy"
            >
              <ChevronLeft className="size-4" />
              시험지로
            </Link>
            <div className="truncate text-lg font-bold">{p.title} · 인쇄</div>
          </div>
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={() => downloadSheetPngs(sheet.data!.pages, paperId)}
              title="인쇄할 수 없을 때: 그림판·태블릿에서 칠하고 쓴 뒤 그대로 올리거나 화면을 찍어 올리세요"
              className="inline-flex h-11 cursor-pointer items-center gap-2 rounded-full border border-home-line bg-white px-5 text-[15px] font-bold text-navy hover:bg-navy-tint"
            >
              <Download size={16} aria-hidden="true" />
              답안지 이미지 받기
            </button>
            <button
              type="button"
              onClick={() => window.print()}
              className="inline-flex h-11 cursor-pointer items-center gap-2 rounded-full bg-navy px-6 text-[15px] font-bold text-white hover:bg-navy-deep"
            >
              <Printer size={16} aria-hidden="true" />
              인쇄하기
            </button>
          </div>
        </div>
        <p className="mx-auto max-w-[210mm] px-4 pb-3 text-[13px] text-ink-2">
          문제지 다음에 답안지가 이어져요. 용지 A4 · 배율 100% · 여백 없음으로 인쇄하세요(답안지 크기가 바뀌면 사진
          인식이 어려워요). 프린터가 없으면 대상에서 'PDF로 저장'.
        </p>
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

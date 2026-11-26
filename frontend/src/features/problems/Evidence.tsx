import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { api, type Schemas, unwrap } from '@/api/client'

/** 정답 근거: 교안 문장과 쪽, [교안 보기]로 그 쪽 내용을 펼친다. 퀴즈와 종이 시험 결과에서 쓴다. */
export function Evidence({
  evidence,
  source,
}: {
  evidence: string | null | undefined
  source: Schemas['SourceOut'] | null | undefined
}) {
  const [showPage, setShowPage] = useState(false)
  const page = useQuery({
    queryKey: ['material-page', source?.material_id, source?.page],
    queryFn: () =>
      unwrap(
        api.GET('/api/v1/materials/{material_id}/pages/{page}', {
          params: { path: { material_id: source!.material_id, page: source!.page! } },
        }),
      ),
    enabled: showPage && !!source?.page,
  })
  if (!evidence) return null
  return (
    <>
      <blockquote className="border-l-2 border-navy pl-3 text-ink-2">
        {evidence}
        {source && (
          <div className="mt-1 text-xs">
            — {source.title}
            {source.page && (
              <>
                {' '}
                {source.page}쪽{' '}
                <button
                  type="button"
                  className="cursor-pointer font-bold text-navy underline"
                  onClick={() => setShowPage((v) => !v)}
                >
                  {showPage ? '접기' : '교안 보기'}
                </button>
              </>
            )}
          </div>
        )}
      </blockquote>
      {showPage && (
        <pre className="max-h-64 overflow-auto whitespace-pre-wrap rounded-md border bg-card p-3 text-xs">
          {page.data?.text ?? '불러오는 중…'}
        </pre>
      )}
    </>
  )
}

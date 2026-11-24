import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api, unwrap, type Schemas } from '@/api/client'
import { ErrorText, Loading } from '@/components/States'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { useAuth } from '@/features/auth/useAuth'

export function ProfessorSummary({ empNo }: { empNo: string }) {
  const { user } = useAuth()
  const qc = useQueryClient()
  const key = ['professor-summary', user?.id, empNo]
  const query = useQuery({ queryKey: key, staleTime: 0,
    queryFn: () => unwrap(api.GET('/api/v1/catalog/professor-summary', { params: { query: { emp_no: empNo } } })),
  })
  const create = useMutation({
    mutationFn: () => unwrap(api.POST('/api/v1/catalog/professor-summary', { params: { query: { emp_no: empNo } } })),
    onSuccess: data => qc.setQueryData(key, data),
  })
  const data = query.data
  const evidence = (ids: number[]) => {
    const sources = data?.sources?.filter(s => ids.includes(s.review_id)) ?? []
    return [...new Set(sources.map(s => `${s.subject} · ${s.term}`))].join(' / ') + ` (후기 ${sources.length}개)`
  }
  const claim = (item: Schemas['ProfessorSummaryClaim']) => <div>
    <p className="whitespace-pre-line text-sm leading-relaxed">{item.text}</p>
    <p className="mt-1 text-xs text-muted-foreground">근거: {evidence(item.review_ids)}</p>
  </div>
  return <Card className="flex flex-col gap-3 p-5">
    <h2 className="text-lg font-semibold">강의평 기반 수업 특징</h2>
    <ErrorText error={query.error} />
    {query.isPending && <Loading />}
    {data && <>
      <p className="text-sm">{data.start_year}~{data.end_year}학년도 · 후기 {data.stats.review_count}개 · 작성자 {data.stats.author_count}명 · {data.stats.course_count}개 강좌</p>
      <div className="flex flex-wrap gap-3 text-sm">
        <span>추천도 {data.stats.recommendation ?? '—'}/5</span>
        <span>난이도 {data.stats.difficulty ?? '—'}/5</span>
        <span>과제량 {data.stats.workload ?? '—'}/5</span>
      </div>
        {data.stats.course_count === 1 && <p className="text-sm text-muted-foreground">한 강좌의 후기만 있어 교수의 다른 수업을 대표하지 않을 수 있습니다.</p>}
      {data.status === 'insufficient' && <p className="text-sm">서로 다른 작성자의 후기 3명 이상이 필요합니다. 교원번호로 연결된 강좌의 후기만 집계합니다.</p>}
      {data.status === 'unavailable' && <p className="text-sm">현재 AI 요약이 설정되지 않았습니다. 통계는 확인할 수 있습니다.</p>}
      {data.status === 'not_generated' && <>
        <p className="text-xs text-muted-foreground">생성 시 작성자 정보 필드를 제외한 후기 내용·과목·학기가 외부 AI 서비스로 전달됩니다.</p>
        <Button className="self-start" disabled={create.isPending} onClick={() => create.mutate()}>{create.isPending ? '요약 생성 중…' : 'AI 수업 특징 요약 보기'}</Button>
      </>}
      {data.summary && <>
        {claim(data.summary.overview)}
        {data.summary.highlights.length > 0 && <div className="flex flex-col gap-3"><h3 className="font-medium">반복되는 특징</h3>{data.summary.highlights.map((c, i) => <div key={i}>{claim(c)}</div>)}</div>}
        {data.summary.differences.length > 0 && <div className="flex flex-col gap-3"><h3 className="font-medium">과목별 차이·엇갈린 의견</h3>{data.summary.differences.map((c, i) => <div key={i}>{claim(c)}</div>)}</div>}
        <p className="text-xs text-muted-foreground">분석 후기 {data.stats.sampled_count}개 · 생성 {data.generated_at ? new Date(data.generated_at).toLocaleString('ko-KR') : ''}</p>
      </>}
    </>}
    <ErrorText error={create.error} />
  </Card>
}

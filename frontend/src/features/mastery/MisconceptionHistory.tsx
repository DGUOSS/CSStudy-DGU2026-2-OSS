import { useQuery } from '@tanstack/react-query'
import { api, unwrap } from '@/api/client'
import { ErrorText, Loading } from '@/components/States'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'

export function MisconceptionHistory({ courseId }: { courseId: number }) {
  const history = useQuery({
    queryKey: ['misconception-results', courseId],
    queryFn: () => unwrap(api.GET('/api/v1/courses/{course_id}/misconception-results', {
      params: { path: { course_id: courseId } },
    })),
  })

  return (
    <section className="grid gap-3">
      <div>
        <h2 className="text-lg font-semibold">오개념 확인 기록</h2>
        <p className="text-sm text-muted-foreground">확인 문제를 푼 기록입니다. 이 답은 위 숙련도 점수에 반영되지 않습니다.</p>
      </div>
      {history.isPending && <Loading />}
      <ErrorText error={history.error} />
      {history.data?.length === 0 && <p className="text-sm text-muted-foreground">아직 확인 문제를 푼 기록이 없습니다.</p>}
      {history.data?.map((entry) => (
        <Card key={entry.id}>
          <CardHeader>
            <div className="flex flex-wrap items-center gap-2">
              <CardTitle className="text-base">{entry.result.title}</CardTitle>
              <Badge variant="outline">{entry.result.correct ? '확인 문제 정답' : '추가 복습 권장'}</Badge>
              <span className="text-xs text-muted-foreground">{new Date(entry.created_at).toLocaleString('ko-KR')}</span>
            </div>
          </CardHeader>
          <CardContent className="grid gap-2 text-sm">
            <p><span className="font-medium">처음 문제:</span> {entry.problem_question}</p>
            <p className="text-muted-foreground">고른 답: {entry.initial_choice}</p>
            <p><span className="font-medium">확인 문제:</span> {entry.probe_question}</p>
            <p className="text-muted-foreground">고른 답: {entry.probe_choice}</p>
            <p className="rounded-md bg-muted p-3">{entry.result.detail}</p>
            <p><span className="font-medium">추정한 생각:</span> {entry.result.hypothesis}</p>
            <p><span className="font-medium">해설:</span> {entry.result.explanation}</p>
            <blockquote className="border-l-2 border-primary pl-3 text-muted-foreground">
              {entry.result.evidence}
              <span className="mt-1 block text-xs">— {entry.result.source.title} {entry.result.source.page}쪽</span>
            </blockquote>
          </CardContent>
        </Card>
      ))}
    </section>
  )
}

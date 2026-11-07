import { useQuery } from '@tanstack/react-query'
import { Play } from 'lucide-react'
import { Link } from 'react-router'
import { api, unwrap } from '@/api/client'
import { Empty, ErrorText, Loading } from '@/components/States'
import { Badge } from '@/components/ui/badge'
import { Button, buttonVariants } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Progress } from '@/components/ui/progress'
import { pct, useMastery } from '@/features/mastery/queries'

export function ChaptersTab({ courseId }: { courseId: number }) {
  const chapters = useQuery({
    queryKey: ['courses', courseId, 'chapters'],
    queryFn: () =>
      unwrap(
        api.GET('/api/v1/courses/{course_id}/chapters', {
          params: { path: { course_id: courseId } },
        }),
      ),
  })
  const mastery = useMastery(courseId)

  if (chapters.isPending) return <Loading />
  if (!chapters.data) return <ErrorText error={chapters.error} />
  if (chapters.data.length === 0)
    return <Empty>아직 문제가 없습니다. 자료 탭에서 교안을 올려 주세요.</Empty>

  return (
    <div className="flex flex-col gap-3">
      <p className="text-sm text-muted-foreground">
        챕터를 골라 원하는 만큼 푸세요. 아직 안 나온 개념의 문제가 먼저 나옵니다.
      </p>
      {chapters.data.map((ch) => {
        const concepts = mastery.data?.find((m) => m.chapter_id === ch.id)?.concepts ?? []
        const tried = concepts.filter((c) => c.attempts > 0)
        const avg = tried.length ? tried.reduce((s, c) => s + c.mastery, 0) / concepts.length : 0
        return (
          <Card key={ch.id} className="flex flex-col gap-3 p-4 sm:flex-row sm:items-center">
            <div className="flex min-w-0 flex-1 flex-col gap-2">
              <div className="font-medium">{ch.title}</div>
              <div className="flex flex-wrap gap-1">
                {ch.concepts.map((name) => (
                  <Badge key={name} variant="secondary">
                    {name}
                  </Badge>
                ))}
              </div>
              <div className="flex items-center gap-2 text-xs text-muted-foreground">
                <Progress value={avg * 100} className="max-w-40" />
                <span>
                  숙련도 {pct(avg)} · 개념 {tried.length}/{concepts.length} 시도
                </span>
              </div>
            </div>
            {ch.problem_count === 0 ? (
              <Button disabled>문제 없음</Button>
            ) : (
              <Link to={`/courses/${courseId}/chapters/${ch.id}/quiz`} className={buttonVariants()}>
                <Play />
                풀기 ({ch.problem_count})
              </Link>
            )}
          </Card>
        )
      })}
    </div>
  )
}

import { Empty, ErrorText, Loading } from '@/components/States'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Progress } from '@/components/ui/progress'
import { pct, useMastery } from './queries'

export function MasteryTab({ courseId }: { courseId: number }) {
  const mastery = useMastery(courseId)
  if (mastery.isPending) return <Loading />
  if (!mastery.data) return <ErrorText error={mastery.error} />
  if (mastery.data.length === 0) return <Empty>아직 챕터가 없습니다.</Empty>

  return (
    <div className="flex flex-col gap-4">
      <p className="text-sm text-muted-foreground">
        개념별로 &lsquo;알고 있을 확률&rsquo;입니다. 문제를 풀 때마다 갱신됩니다.
      </p>
      {mastery.data.map((ch) => (
        <Card key={ch.chapter_id}>
          <CardHeader className="pb-3">
            <CardTitle className="text-base">{ch.title}</CardTitle>
          </CardHeader>
          <CardContent className="grid gap-3">
            {ch.concepts.map((c) => (
              <div key={c.concept_id} className="grid gap-1">
                <div className="flex justify-between text-sm">
                  <span>{c.name}</span>
                  <span className="text-muted-foreground">
                    {c.attempts === 0 ? '아직 안 풀었음' : `${pct(c.mastery)} · ${c.correct}/${c.attempts}`}
                  </span>
                </div>
                <Progress value={c.attempts === 0 ? 0 : c.mastery * 100} />
              </div>
            ))}
          </CardContent>
        </Card>
      ))}
    </div>
  )
}

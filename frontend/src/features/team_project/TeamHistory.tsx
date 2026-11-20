import { useQuery } from '@tanstack/react-query'
import { api, unwrap } from '@/api/client'
import { ErrorText } from '@/components/States'
import { Card } from '@/components/ui/card'
import { TeamBadge } from './TeamBadge'
import { teamSourceText } from './teamText'

/** 강좌 정보 탭: 학기별 팀 프로젝트 라벨과 근거. 같은 강좌라도 학기마다 다를 수 있다. */
export function TeamHistory({ courseId }: { courseId: number }) {
  const q = useQuery({
    queryKey: ['courses', courseId, 'team-project'],
    queryFn: () => unwrap(api.GET('/api/v1/courses/{course_id}/team-project', {
      params: { path: { course_id: courseId } },
    })),
  })
  return (
    <Card className="gap-3 p-5">
      <h2 className="font-semibold">팀 프로젝트</h2>
      <ErrorText error={q.error} />
      {q.data && q.data.terms.length === 0 && (
        <p className="text-sm text-muted-foreground">
          아직 정보가 없습니다. 강의계획서를 가져오거나 후기에서 팀 프로젝트 여부를 답하면 표시됩니다.
        </p>
      )}
      <ul className="flex flex-col gap-2">
        {q.data?.terms.map((t) => (
          <li key={`${t.year}-${t.sem_cd}`} className="flex flex-col gap-1 text-sm sm:flex-row sm:items-start sm:gap-3">
            <span className="w-28 shrink-0 font-medium">{t.term}</span>
            <TeamBadge label={t} className="self-start" />
            <span className="min-w-0 break-words text-muted-foreground">{teamSourceText(t)}</span>
          </li>
        ))}
      </ul>
      <p className="text-xs text-muted-foreground">
        강의계획서에 적힌 내용을 먼저 따르고, 계획서가 없으면 그 학기 수강생 후기의 응답으로 정합니다.
      </p>
    </Card>
  )
}

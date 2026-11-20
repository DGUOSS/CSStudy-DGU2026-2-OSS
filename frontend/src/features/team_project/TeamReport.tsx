import { Users } from 'lucide-react'
import { ErrorText } from '@/components/States'
import { Button } from '@/components/ui/button'
import { useReportTeam, useTeamProject } from './queries'

/** 강좌 화면 위쪽: 수강한 학기 중 아직 답하지 않은 학기가 있으면 한 번만 묻는다. */
export function TeamReportPrompt({ courseId }: { courseId: number }) {
  const q = useTeamProject(courseId)
  const report = useReportTeam(courseId)
  const open = q.data?.my_terms.find((t) => t.my_answer == null)
  if (!open) return null
  const answer = (v: boolean) => report.mutate({ year: open.year, sem_cd: open.sem_cd, team_project: v })
  return (
    <div className="flex flex-wrap items-center gap-2 rounded-md border bg-muted/40 px-3 py-2 text-sm">
      <Users aria-hidden="true" className="size-4 text-muted-foreground" />
      <span>{open.term}에 들은 이 수업, 팀 프로젝트가 있었나요?</span>
      <span className="flex gap-1.5">
        <Button size="sm" variant="outline" disabled={report.isPending} onClick={() => answer(true)}>있었어요</Button>
        <Button size="sm" variant="outline" disabled={report.isPending} onClick={() => answer(false)}>없었어요</Button>
      </span>
      <span className="text-xs text-muted-foreground">강의계획서와 실제가 다를 때 라벨을 고치는 데 쓰입니다.</span>
      <ErrorText error={report.error} />
    </div>
  )
}

/** 강좌 정보 탭: 학기별로 내 응답을 보고 바꾼다. */
export function MyTeamAnswers({ courseId }: { courseId: number }) {
  const q = useTeamProject(courseId)
  const report = useReportTeam(courseId)
  const mine = q.data?.my_terms ?? []
  if (mine.length === 0) return null
  return (
    <div className="flex flex-col gap-2 border-t pt-3">
      <h3 className="text-sm font-medium">내 응답</h3>
      {mine.map((t) => {
        const set = (v: boolean | null) => report.mutate({ year: t.year, sem_cd: t.sem_cd, team_project: v })
        return (
          <div key={`${t.year}-${t.sem_cd}`} className="flex flex-wrap items-center gap-2 text-sm">
            <span className="w-28 shrink-0">{t.term}</span>
            <Button size="sm" variant={t.my_answer === true ? 'default' : 'outline'} aria-pressed={t.my_answer === true}
              disabled={report.isPending} onClick={() => set(true)}>있었어요</Button>
            <Button size="sm" variant={t.my_answer === false ? 'default' : 'outline'} aria-pressed={t.my_answer === false}
              disabled={report.isPending} onClick={() => set(false)}>없었어요</Button>
            {t.my_answer != null && (
              <Button size="sm" variant="ghost" disabled={report.isPending} onClick={() => set(null)}>응답 지우기</Button>
            )}
          </div>
        )
      })}
      <ErrorText error={report.error} />
    </div>
  )
}

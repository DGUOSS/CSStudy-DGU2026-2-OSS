import { type FormEvent, useState } from 'react'
import { ErrorText } from '@/components/States'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { useAuth } from '@/features/auth/useAuth'
import { TeamBadge } from './TeamBadge'
import { MyTeamAnswers } from './TeamReport'
import { teamSourceText } from './teamText'
import { useOverrideTeam, useTeamProject } from './queries'

const SEMS = [
  { cd: 'CM160.10', label: '1학기' },
  { cd: 'CM160.11', label: '여름학기' },
  { cd: 'CM160.20', label: '2학기' },
  { cd: 'CM160.21', label: '겨울학기' },
]

/** 강좌 정보 탭: 학기별 팀 프로젝트 라벨과 근거. 같은 강좌라도 학기마다 다를 수 있다. */
export function TeamHistory({ courseId }: { courseId: number }) {
  const q = useTeamProject(courseId)
  const { user } = useAuth()
  return (
    <Card className="flex flex-col gap-3 p-5">
      <h2 className="font-semibold">팀 프로젝트</h2>
      <ErrorText error={q.error} />
      {q.data && q.data.terms.length === 0 && (
        <p className="text-sm text-muted-foreground">
          아직 정보가 없습니다. 강의계획서를 가져오거나 수강생이 응답하면 표시됩니다.
        </p>
      )}
      <ul className="flex flex-col gap-3 sm:gap-2">
        {q.data?.terms.map((t) => (
          <li key={`${t.year}-${t.sem_cd}`} className="flex flex-col gap-1 text-sm sm:flex-row sm:items-start sm:gap-3">
            <span className="w-28 shrink-0 font-medium">{t.term}</span>
            {t.label === 'unknown' ? (
              <span className="shrink-0 text-muted-foreground">아직 모름</span>
            ) : (
              <TeamBadge label={t} className="self-start" />
            )}
            <span className="min-w-0 break-words text-muted-foreground">{teamSourceText(t, false)}</span>
          </li>
        ))}
      </ul>
      <p className="text-xs text-muted-foreground">
        강의계획서를 기본으로 쓰고, 그 학기 수강생 응답이 2명 이상 모여 과반이면 실제 응답을 따릅니다. 운영진이
        확인한 학기는 운영진 판단을 따릅니다.
      </p>
      <MyTeamAnswers courseId={courseId} />
      {user?.role === 'admin' && <OverrideForm courseId={courseId} />}
    </Card>
  )
}

function OverrideForm({ courseId }: { courseId: number }) {
  const save = useOverrideTeam(courseId)
  const [year, setYear] = useState(() => String(new Date().getFullYear()))
  const [semCd, setSemCd] = useState(() => (new Date().getMonth() + 1 >= 8 ? 'CM160.20' : 'CM160.10'))
  const [value, setValue] = useState<'yes' | 'no' | 'clear'>('yes')
  const [note, setNote] = useState('')
  const submit = (e: FormEvent) => {
    e.preventDefault()
    save.mutate(
      { year, sem_cd: semCd, team_project: value === 'clear' ? null : value === 'yes', note },
      { onSuccess: () => setNote('') },
    )
  }
  const selectClass = 'rounded-md border bg-background px-3 py-2 text-sm'
  return (
    <form onSubmit={submit} className="flex flex-col gap-2 border-t pt-3">
      <h3 className="text-sm font-medium">운영진 지정</h3>
      <div className="flex flex-wrap gap-2">
        <Input aria-label="연도" className="w-24" inputMode="numeric" pattern="\d{4}" value={year}
          onChange={(e) => setYear(e.target.value)} />
        <select aria-label="학기" className={selectClass} value={semCd} onChange={(e) => setSemCd(e.target.value)}>
          {SEMS.map((s) => <option key={s.cd} value={s.cd}>{s.label}</option>)}
        </select>
        <select aria-label="팀플 여부" className={selectClass} value={value}
          onChange={(e) => setValue(e.target.value as 'yes' | 'no' | 'clear')}>
          <option value="yes">팀플 있음</option>
          <option value="no">팀플 없음</option>
          <option value="clear">지정 해제</option>
        </select>
        <Input aria-label="메모" className="min-w-48 flex-1" maxLength={300} value={note}
          onChange={(e) => setNote(e.target.value)} placeholder="근거 메모(예: 수강생 확인, 공지 변경)" />
        <Button type="submit" disabled={save.isPending || !/^\d{4}$/.test(year)}>저장</Button>
      </div>
      <p className="text-xs text-muted-foreground">
        다른 사이트의 글을 옮겨 적지 말고 확인한 판단만 적어 주세요.
      </p>
      <ErrorText error={save.error} />
    </form>
  )
}

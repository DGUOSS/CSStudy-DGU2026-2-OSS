import { useState } from 'react'
import { ErrorText } from '@/components/States'
import { useAuth } from '@/features/auth/useAuth'
import { NoticesPanel } from '@/features/department_notices/NoticesPanel'
import { AppShell } from './AppShell'
import { Calendar } from './Calendar'
import { Hero } from './Hero'
import { MyStudyGroups } from './MyStudyGroups'
import { useDeadlines, useHomeSummary } from './queries'
import { Stats } from './Stats'

/**
 * 홈 화면(/home). 데이터는 전부 기존 API(내 과목·강좌·숙련도)에서 가져온다.
 * 일정은 useDeadlines 참고.
 */
export function HomePage() {
  return (
    <AppShell>
      <HomeContent />
    </AppShell>
  )
}

function HomeContent() {
  const { user } = useAuth()
  const summary = useHomeSummary()
  const deadlines = useDeadlines()
  const [today] = useState(() => new Date())

  const eventDates = new Set(
    deadlines.data.map((d) => {
      const x = new Date(d.due)
      return `${x.getFullYear()}-${String(x.getMonth() + 1).padStart(2, '0')}-${String(x.getDate()).padStart(2, '0')}`
    }),
  )

  return (
    <>
      <Hero userName={user?.name ?? ''} subjects={summary.subjects} loading={summary.loading} />
      <ErrorText error={summary.error} />
      <div className="grid grid-cols-1 gap-8 lg:grid-cols-[minmax(0,1fr)_360px]">
        <div className="flex flex-col gap-7">
          {/* '이번 주 시험 과제' 대신 스터디 현황(왼쪽 맨 위, 첫 화면에 보이게). 일정은 오른쪽 달력에 점으로 표시 */}
          <MyStudyGroups />
          <Stats totals={summary.totals} />
        </div>
        {/* 오른쪽: 공지를 달력 위에 둔다 (다가오는 일정 목록은 뺐다) */}
        <div className="flex min-w-0 flex-col gap-6">
          <NoticesPanel />
          <Calendar today={today} eventDates={eventDates} />
        </div>
      </div>
    </>
  )
}

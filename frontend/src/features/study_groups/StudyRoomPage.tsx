import { useQuery } from '@tanstack/react-query'
import { CalendarClock, MapPin, Monitor, Users } from 'lucide-react'
import { useState } from 'react'
import { BackButton } from '@/components/BackButton'
import { Link, useNavigate, useParams } from 'react-router'
import { ApiError, api, unwrap } from '@/api/client'
import { ErrorText, Loading } from '@/components/States'
import { useAuth } from '@/features/auth/useAuth'
import { AppShell } from '@/features/home/AppShell'
import { StudyChat } from './StudyChat'
import { ManageModal } from './StudyManage'
import { btn, useParticipation } from './studyKit'
import { MODE_LABEL, peopleLabel, type Study, useMyStudy } from './useMyStudy'

/** 새 디자인: 스터디 방(/study/groups/:id). 왼쪽 채팅(화면 높이에 맞춤), 오른쪽 스터디 정보 */
export function StudyRoomPage() {
  return (
    <AppShell>
      <Room />
    </AppShell>
  )
}

function Room() {
  const groupId = Number(useParams().groupId)
  const { user } = useAuth()
  const space = useQuery({
    queryKey: ['study-space', user?.id, groupId],
    queryFn: () => unwrap(api.GET('/api/v1/study-groups/{group_id}/space', { params: { path: { group_id: groupId } } })),
    enabled: !!user,
    staleTime: 0,
    retry: false,
  })
  const sid = space.data?.subject_id
  const { mine } = useMyStudy(sid ? [sid] : [])
  const g = mine.find((x) => x.id === groupId)

  if (space.isPending) return <Loading />
  if (space.isError) {
    const locked = space.error instanceof ApiError && space.error.status === 403
    return (
      <section role="alert" className="rounded-2xl border border-home-line bg-white p-6">
        <h1 className="text-xl font-bold">{locked ? '참여 승인 후 들어올 수 있어요' : '스터디 방을 열지 못했어요'}</h1>
        <p className="mt-2 text-sm text-ink-2">{space.error.message}</p>
        <Link to="/study/groups" className={`${btn.line} mt-5`}>
          스터디로 돌아가기
        </Link>
      </section>
    )
  }
  const s = space.data

  return (
    <>
      <header>
        <BackButton fallback="/study/groups" />
        <div className="mt-1.5 flex flex-wrap items-center gap-2.5">
          <h1 className="text-2xl font-bold break-words">{s.title}</h1>
          <Link
            to={`/study/subjects/${s.subject_id}/groups`}
            className="rounded-full bg-navy-tint px-3 py-1 text-xs font-bold text-navy hover:bg-tone-blue"
          >
            {s.subject_name}
          </Link>
        </div>
      </header>
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[minmax(0,1fr)_300px]">
        {/* 채팅이 화면 아래까지 차게: 화면 높이 - 머리말 */}
        <div className="h-[calc(100svh-210px)] min-h-96 [&>section]:h-full [&>section]:max-h-none">
          <StudyChat groupId={s.id} />
        </div>
        <aside className="flex flex-col gap-4 self-start">{g ? <Info g={g} /> : <Loading />}</aside>
      </div>
    </>
  )
}

function Info({ g }: { g: Study }) {
  const [managing, setManaging] = useState(false)
  const [leaving, setLeaving] = useState(false)
  const act = useParticipation(g)
  const nav = useNavigate()
  const rows = [
    [Monitor, MODE_LABEL[g.mode] ?? g.mode],
    [CalendarClock, g.schedule],
    [MapPin, g.location],
    [Users, `${peopleLabel(g)} · 개설 ${g.owner_name}`],
  ] as const

  return (
    <section className="flex flex-col gap-4 rounded-2xl border border-home-line bg-white p-5">
      <h2 className="font-bold">스터디 정보</h2>
      <ul className="flex flex-col gap-2.5 text-sm">
        {rows.map(([Icon, text], i) => (
          <li key={i} className="flex items-start gap-2.5">
            <Icon size={16} className="mt-0.5 shrink-0 text-ink-2" aria-hidden="true" />
            <span className="min-w-0 break-words">{text}</span>
          </li>
        ))}
      </ul>
      <p className="border-t border-home-line pt-4 text-sm whitespace-pre-wrap break-words text-ink-2">{g.description}</p>
      {g.is_mine ? (
        <button type="button" className={btn.line} onClick={() => setManaging(true)}>
          신청 관리
          {!!g.pending_count && <span className="rounded-full bg-gold px-1.5 text-xs text-white">{g.pending_count}</span>}
        </button>
      ) : leaving ? (
        <div className="flex flex-col gap-2 rounded-xl bg-home-bg p-3">
          <p className="text-sm">나가면 다시 신청해서 승인받아야 해요.</p>
          <div className="flex justify-end gap-1.5">
            <button type="button" className={btn.quiet} onClick={() => setLeaving(false)}>
              취소
            </button>
            <button
              type="button"
              className={btn.primary}
              disabled={act.isPending}
              onClick={() => act.mutate('cancel', { onSuccess: () => nav('/study/groups') })}
            >
              나가기
            </button>
          </div>
          <ErrorText error={act.error} />
        </div>
      ) : (
        <button type="button" className={`${btn.quiet} self-start`} onClick={() => setLeaving(true)}>
          스터디 나가기
        </button>
      )}
      {managing && <ManageModal g={g} onClose={() => setManaging(false)} />}
    </section>
  )
}

import { useQuery } from '@tanstack/react-query'
import { Plus } from 'lucide-react'
import { useState } from 'react'
import { BackButton } from '@/components/BackButton'
import { Link, useParams } from 'react-router'
import { api, unwrap } from '@/api/client'
import { Empty, ErrorText, Loading } from '@/components/States'
import { useAuth } from '@/features/auth/useAuth'
import { useSubjects } from '@/features/courses/queries'
import { AppShell } from '@/features/home/AppShell'
import { cn } from '@/lib/utils'
import { StudyCreateModal } from './StudyCreateModal'
import { ManageModal } from './StudyManage'
import { btn, useParticipation } from './studyKit'
import { MODE_LABEL, peopleLabel, type Study } from './useMyStudy'

/** 새 디자인: 한 과목의 스터디 목록(/study/subjects/:id/groups). 한 스터디 = 한 줄, 할 일 버튼은 오른쪽 하나 */
export function StudySubjectPage() {
  return (
    <AppShell>
      <StudySubject />
    </AppShell>
  )
}

const STATES = [
  ['open', '모집 중'],
  ['closed', '모집 끝'],
  ['all', '전체'],
] as const
const PER = 10

function StudySubject() {
  const subjectId = Number(useParams().subjectId)
  const subjects = useSubjects()
  const [creating, setCreating] = useState(false)
  const subject = subjects.data?.find((s) => s.id === subjectId)
  if (subjects.isPending) return <Loading />
  if (!subject) return <Empty>과목을 찾을 수 없어요.</Empty>

  return (
    <>
      <header className="flex flex-col gap-1.5">
        <BackButton fallback="/study/groups" />
        <div className="flex flex-wrap items-start justify-between gap-4">
          <h1 className="text-2xl font-bold">{subject.name} 스터디</h1>
          <button type="button" className={cn(btn.primary, 'h-11 px-5 text-[15px]')} onClick={() => setCreating(true)}>
            <Plus size={16} aria-hidden="true" /> 스터디 만들기
          </button>
        </div>
      </header>
      <StudyList subjectId={subjectId} />
      {creating && <StudyCreateModal subjectId={subjectId} onClose={() => setCreating(false)} />}
    </>
  )
}

/**
 * 한 과목의 스터디 목록(모집 상태 탭 + 한 줄 목록 + 쪽 넘기기). 과목별 스터디 화면과 강좌 화면의 스터디(?tab=groups)가 같이 쓴다.
 * withCreate: 목록 위 줄 오른쪽에 '스터디 만들기' 버튼을 둔다(머리말에 버튼이 없는 강좌 하위 화면용).
 */
export function StudyList({ subjectId, withCreate = false }: { subjectId: number; withCreate?: boolean }) {
  const { user } = useAuth()
  const [state, setState] = useState<'open' | 'closed' | 'all'>('open')
  const [page, setPage] = useState(0)
  const [creating, setCreating] = useState(false)
  const groups = useQuery({
    queryKey: ['study-groups', user?.id, subjectId, state, page],
    queryFn: () =>
      unwrap(
        api.GET('/api/v1/subjects/{subject_id}/study-groups', {
          params: { path: { subject_id: subjectId }, query: { state, offset: page * PER, limit: PER } },
        }),
      ),
    enabled: !!user,
  })
  const myWeak = groups.data?.my_weak ?? []

  return (
    <section className="flex flex-col gap-3" aria-label="스터디 목록">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div role="radiogroup" aria-label="모집 상태" className="flex rounded-full bg-white p-1 ring-1 ring-home-line">
          {STATES.map(([v, label]) => (
            <button
              key={v}
              type="button"
              role="radio"
              aria-checked={state === v}
              onClick={() => {
                setState(v)
                setPage(0)
              }}
              className={cn(
                'h-8 cursor-pointer rounded-full px-4 text-sm font-bold',
                state === v ? 'bg-navy text-white' : 'text-ink-2 hover:text-navy',
              )}
            >
              {label}
            </button>
          ))}
        </div>
        {withCreate && (
          <button type="button" className={btn.primary} onClick={() => setCreating(true)}>
            <Plus size={16} aria-hidden="true" /> 스터디 만들기
          </button>
        )}
      </div>
      {myWeak.length > 0 && (
        <p className="text-[13px] text-ink-2">
          내 약점 <b className="text-[#6b4a0c]">{myWeak.slice(0, 3).join(', ')}</b>
          {myWeak.length > 3 && ` 외 ${myWeak.length - 3}개`}과 겹치는 스터디를 먼저 보여 줘요
        </p>
      )}

      {groups.isPending && <Loading />}
      <ErrorText error={groups.error} />
      {groups.data && groups.data.items.length === 0 && (
        <Empty>{state === 'open' ? '모집 중인 스터디가 없어요. 첫 스터디를 만들어 보세요.' : '해당하는 스터디가 없어요.'}</Empty>
      )}
      {!!groups.data?.items.length && (
        <ul className="overflow-hidden rounded-2xl border border-home-line bg-white">
          {groups.data.items.map((g) => (
            <StudyRow key={g.id} g={g} />
          ))}
        </ul>
      )}
      {groups.data && groups.data.total > PER && (
        <nav aria-label="쪽" className="flex items-center justify-center gap-2">
          <button type="button" className={btn.quiet} disabled={!page} onClick={() => setPage(page - 1)}>
            이전
          </button>
          <span className="text-sm text-ink-2 tabular-nums">
            {page + 1} / {Math.ceil(groups.data.total / PER)}
          </span>
          <button
            type="button"
            className={btn.quiet}
            disabled={(page + 1) * PER >= groups.data.total}
            onClick={() => setPage(page + 1)}
          >
            다음
          </button>
        </nav>
      )}
      {creating && <StudyCreateModal subjectId={subjectId} onClose={() => setCreating(false)} />}
    </section>
  )
}

function StudyRow({ g }: { g: Study }) {
  const [open, setOpen] = useState(false)
  const [managing, setManaging] = useState(false)
  const act = useParticipation(g)
  const joined = g.is_mine || g.my_application === 'approved'
  const full = g.capacity > 0 && g.participant_count >= g.capacity
  const weak = g.shared_weak ?? []

  const badge = g.is_mine
    ? ['개설자', 'bg-gold-soft text-[#6b4a0c]']
    : g.my_application === 'approved'
      ? ['참여 중', 'bg-tone-blue text-navy']
      : g.my_application === 'pending'
        ? ['승인 대기', 'bg-home-bg text-ink-2']
        : null

  return (
    <li className={cn('border-b border-home-line px-5 py-4 last:border-b-0', g.closed_at && 'bg-home-bg/50')}>
      <div className="flex flex-wrap items-start gap-x-4 gap-y-3">
        <div className="min-w-0 flex-1 basis-80">
          <div className="flex flex-wrap items-center gap-2">
            <h2 className="text-[17px] font-bold break-words">{g.title}</h2>
            {badge && <span className={cn('rounded-full px-2.5 py-0.5 text-xs font-bold', badge[1])}>{badge[0]}</span>}
            {g.closed_at && (
              <span className="rounded-full bg-home-bg px-2.5 py-0.5 text-xs font-bold text-ink-2">모집 끝</span>
            )}
          </div>
          <p className="mt-1 text-[13px] text-ink-2">
            {MODE_LABEL[g.mode] ?? g.mode} · {g.schedule} · {g.location} · {peopleLabel(g)} · {g.owner_name}
          </p>
          <button
            type="button"
            onClick={() => setOpen(!open)}
            aria-expanded={open}
            className={cn(
              'mt-2 block w-full cursor-pointer text-left text-sm whitespace-pre-wrap break-words',
              !open && 'line-clamp-2',
            )}
            title={open ? '접기' : '전체 보기'}
          >
            {g.description}
          </button>
          {weak.length > 0 && (
            <div className="mt-2 flex flex-wrap items-center gap-1.5">
              <span className="text-xs font-bold text-[#6b4a0c]">나와 겹치는 약점</span>
              {weak.slice(0, 4).map((w) => (
                <span key={w} className="rounded-full bg-gold-soft px-2.5 py-0.5 text-xs font-bold text-[#6b4a0c]">
                  {w}
                </span>
              ))}
            </div>
          )}
        </div>

        <div className="flex shrink-0 items-center gap-1.5">
          {g.is_mine && (
            <button type="button" className={btn.line} onClick={() => setManaging(true)}>
              신청 관리{!!g.pending_count && <span className="rounded-full bg-gold px-1.5 text-xs text-white">{g.pending_count}</span>}
            </button>
          )}
          {joined ? (
            <Link to={`/study/groups/${g.id}`} className={btn.primary}>
              입장
            </Link>
          ) : g.my_application === 'pending' ? (
            <button type="button" className={btn.quiet} disabled={act.isPending} onClick={() => act.mutate('cancel')}>
              신청 취소
            </button>
          ) : g.closed_at ? null : (
            <button type="button" className={btn.primary} disabled={act.isPending || full} onClick={() => act.mutate('apply')}>
              {full ? '정원 마감' : act.isPending ? '신청 중…' : '신청'}
            </button>
          )}
        </div>
      </div>
      <ErrorText error={act.error} />
      {managing && <ManageModal g={g} onClose={() => setManaging(false)} />}
    </li>
  )
}

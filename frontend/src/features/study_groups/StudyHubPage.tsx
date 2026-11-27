import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Plus } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router'
import { api, unwrap } from '@/api/client'
import { Empty, ErrorText, Loading } from '@/components/States'
import { useAuth } from '@/features/auth/useAuth'
import { AppShell } from '@/features/home/AppShell'
import { cn } from '@/lib/utils'
import { StudyCreateModal } from './StudyCreateModal'
import { MODE_LABEL, peopleLabel, type Study, useMyStudy } from './useMyStudy'

/**
 * 사이드바 '스터디' 화면(/study/groups). 스터디는 과목 단위라 강좌 화면 밖에 둔다.
 * 위: 내 스터디(과목 상관없이) / 아래: 내 과목에서 모집 중(약점이 겹치는 것부터, 바로 신청).
 * 만들기·신청 관리 같은 자세한 일은 과목별 스터디 화면(/study/subjects/:id/groups)에서 한다.
 */
export function StudyHubPage() {
  return (
    <AppShell>
      <StudyHub />
    </AppShell>
  )
}

function StudyHub() {
  const { subjects, mine, recruiting, loading } = useMyStudy()
  const [subject, setSubject] = useState<number | null>(null)
  const shown = subject ? recruiting.filter((g) => g.subject_id === subject) : recruiting
  const subjectList = [...subjects.entries()]

  if (loading) return <Loading />

  return (
    <>
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold">스터디</h1>
        </div>
        {subjectList.length > 0 && (
          <CreateButton subjects={subjectList} />
        )}
      </div>

      <section aria-labelledby="mine" className="flex flex-col gap-3">
        <h2 id="mine" className="text-xl font-bold">
          내 스터디 <span className="text-[15px] font-normal text-ink-2">{mine.length}</span>
        </h2>
        {mine.length === 0 ? (
          <Empty>아직 참여 중인 스터디가 없어요. 아래 모집 중인 스터디에 신청해 보세요.</Empty>
        ) : (
          <div className="grid grid-cols-1 gap-3.5 md:grid-cols-2">
            {mine.map((g) => (
              <article key={g.id} className="flex flex-col gap-3 rounded-2xl border border-home-line bg-white p-5">
                <div className="flex items-start justify-between gap-2.5">
                  <div className="min-w-0">
                    <div className="text-[13px] text-ink-2">{subjects.get(g.subject_id)}</div>
                    <h3 className="mt-0.5 text-[17px] font-bold">{g.title}</h3>
                  </div>
                  <span
                    className={cn(
                      'shrink-0 rounded-full px-2.5 py-1 text-xs font-bold',
                      g.is_mine ? 'bg-gold-soft text-[#6b4a0c]' : 'bg-tone-blue text-navy',
                    )}
                  >
                    {g.is_mine ? '개설자' : '참여 중'}
                  </span>
                </div>
                <div className="text-[13px] text-ink-2">
                  {MODE_LABEL[g.mode] ?? g.mode} · {g.schedule} · {g.location} · {peopleLabel(g)}
                  {g.is_mine && !!g.pending_count && ` (신청 ${g.pending_count})`}
                  {g.closed_at && ' · 모집 종료'}
                </div>
                <div className="mt-auto flex flex-wrap gap-2">
                  <Link
                    to={`/study/groups/${g.id}`}
                    className="inline-flex h-11 items-center rounded-full bg-navy px-5 text-[15px] font-bold text-white hover:bg-navy-deep"
                  >
                    채팅 열기
                  </Link>
                  {g.is_mine && (
                    <Link
                      to={`/study/subjects/${g.subject_id}/groups`}
                      className="inline-flex h-11 items-center rounded-full border border-home-line bg-white px-4 text-[15px] font-bold text-navy hover:bg-navy-tint"
                    >
                      신청 관리
                    </Link>
                  )}
                </div>
              </article>
            ))}
          </div>
        )}
      </section>

      <section aria-labelledby="open" className="flex flex-col gap-3">
        <div className="flex flex-wrap items-center justify-between gap-2.5">
          <h2 id="open" className="text-xl font-bold">
            내 과목에서 모집 중
          </h2>
          {subjectList.length > 1 && (
            <div role="radiogroup" aria-label="과목" className="flex flex-wrap gap-1.5">
              {[[null, '전체'] as const, ...subjectList].map(([id, name]) => (
                <button
                  key={id ?? 'all'}
                  type="button"
                  role="radio"
                  aria-checked={subject === id}
                  onClick={() => setSubject(id)}
                  className={cn(
                    'h-10 cursor-pointer rounded-full px-4 text-sm font-bold',
                    subject === id ? 'bg-navy text-white' : 'border border-home-line bg-white text-ink-2 hover:text-navy',
                  )}
                >
                  {name}
                </button>
              ))}
            </div>
          )}
        </div>
        {shown.length === 0 ? (
          <Empty>모집 중인 스터디가 없어요. 직접 만들어 보세요.</Empty>
        ) : (
          <ul className="overflow-hidden rounded-2xl border border-home-line bg-white">
            {shown.map((g) => (
              <RecruitRow key={g.id} g={g} subjectName={subjects.get(g.subject_id) ?? ''} />
            ))}
          </ul>
        )}
        <p className="text-[13px] text-ink-2">
          나와 약점이 겹치는 스터디를 먼저 보여 줘요. 약점은 퀴즈·시험 기록의 숙련도로 계산해요.
        </p>
      </section>
    </>
  )
}

/** 모집 중인 스터디 한 줄 + 바로 신청 */
function RecruitRow({ g, subjectName }: { g: Study; subjectName: string }) {
  const { user } = useAuth()
  const qc = useQueryClient()
  const apply = useMutation({
    mutationFn: () =>
      unwrap(
        api.POST('/api/v1/subjects/{subject_id}/study-groups/{group_id}/apply', {
          params: { path: { subject_id: g.subject_id, group_id: g.id } },
        }),
      ),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['study-groups', user?.id, g.subject_id] }),
  })
  const pending = g.my_application === 'pending'
  const weak = g.shared_weak ?? []
  return (
    <li className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-4 border-b border-home-line px-5 py-4 last:border-b-0">
      <div className="flex min-w-0 flex-col gap-1.5">
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-[13px] text-ink-2">{subjectName}</span>
          <Link to={`/study/subjects/${g.subject_id}/groups`} className="font-bold hover:text-navy">
            {g.title}
          </Link>
        </div>
        <div className="text-[13px] text-ink-2">
          {MODE_LABEL[g.mode] ?? g.mode} · {g.schedule} · {peopleLabel(g)} · {g.owner_name} 개설
        </div>
        {weak.length > 0 && (
          <div className="flex flex-wrap items-center gap-1.5">
            <span className="text-xs font-bold text-[#6b4a0c]">나와 겹치는 약점</span>
            {weak.map((w) => (
              <span key={w} className="rounded-full bg-gold-soft px-2.5 py-0.5 text-xs font-bold text-[#6b4a0c]">
                {w}
              </span>
            ))}
          </div>
        )}
        <ErrorText error={apply.error} />
      </div>
      <button
        type="button"
        disabled={pending || apply.isPending}
        onClick={() => apply.mutate()}
        className="h-10 cursor-pointer rounded-full border border-home-line bg-white px-4 text-sm font-bold text-navy hover:bg-navy-tint disabled:cursor-default disabled:border-transparent disabled:bg-home-bg disabled:text-ink-2"
      >
        {pending ? '신청함' : apply.isPending ? '신청 중…' : '신청'}
      </button>
    </li>
  )
}

/** 스터디 만들기: 창 안에서 과목을 고르고 바로 만든다 */
function CreateButton({ subjects }: { subjects: [number, string][] }) {
  const [open, setOpen] = useState(false)
  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="inline-flex h-11 cursor-pointer items-center gap-1.5 rounded-full bg-navy px-5 text-[15px] font-bold text-white hover:bg-navy-deep"
      >
        <Plus size={16} aria-hidden="true" /> 스터디 만들기
      </button>
      {open && <StudyCreateModal subjects={subjects} onClose={() => setOpen(false)} />}
    </>
  )
}

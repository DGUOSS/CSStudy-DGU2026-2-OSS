import { ChevronRight, Users } from 'lucide-react'
import { Link } from 'react-router'
import { Empty } from '@/components/States'
import { MODE_LABEL, peopleLabel, useMyStudy } from '@/features/study_groups/useMyStudy'
import { SectionHeader } from './SectionHeader'

/**
 * 홈의 "내 스터디 그룹": 내가 개설했거나 승인된 스터디를 과목 상관없이 모아 보여 주고, 제목·과목·일정만 짧게 보여 준다.
 * 참여 중인 스터디가 없으면 내 약점과 겹치는 모집 중 스터디를 안내한다. 전체는 사이드바 '스터디'(/study/groups).
 */
export function MyStudyGroups() {
  const { subjects, mine, recruiting, matched, loading } = useMyStudy()

  return (
    <section className="flex flex-col gap-3.5">
      <div className="flex items-baseline justify-between gap-3">
        <SectionHeader title="내 스터디 그룹" />
        <Link to="/study/groups" className="text-sm font-bold text-navy hover:underline">
          스터디 전체 ›
        </Link>
      </div>
      {loading ? (
        <p className="text-sm text-ink-2">스터디 불러오는 중…</p>
      ) : mine.length === 0 ? (
        <Empty>
          아직 참여 중인 스터디가 없어요.
          {matched.length > 0 && (
            <>
              {' '}
              <Link to="/study/groups" className="font-bold text-navy hover:underline">
                내 약점과 겹치는 모집 중 스터디 {matched.length}개 보기
              </Link>
            </>
          )}
        </Empty>
      ) : (
        <ul className="overflow-hidden rounded-2xl border border-home-line bg-white">
          {mine.slice(0, 4).map((g) => (
            <li key={g.id} className="border-b border-home-line last:border-b-0">
              <Link to={`/study/groups/${g.id}`} className="flex items-center gap-4 px-5 py-4 hover:bg-home-bg">
                <span className="flex size-11 shrink-0 items-center justify-center rounded-xl bg-tone-blue text-navy">
                  <Users size={22} strokeWidth={1.8} aria-hidden="true" />
                </span>
                <div className="min-w-0 flex-1">
                  <p className="flex items-center gap-2">
                    <span className="truncate font-bold">{g.title}</span>
                    {g.is_mine && (
                      <span className="shrink-0 rounded-full bg-gold-soft px-2 py-0.5 text-xs font-bold text-[#6b4a0c]">
                        개설자
                      </span>
                    )}
                  </p>
                  <p className="truncate text-sm text-ink-2">
                    {subjects.get(g.subject_id) ?? ''} · {MODE_LABEL[g.mode] ?? g.mode} · {g.schedule} · {peopleLabel(g)}
                  </p>
                </div>
                <ChevronRight size={18} className="shrink-0 text-ink-2" aria-hidden="true" />
              </Link>
            </li>
          ))}
        </ul>
      )}
      {mine.length > 0 && recruiting.length > 0 && (
        <Link to="/study/groups" className="self-start text-sm font-bold text-navy hover:underline">
          내 과목에서 모집 중 {recruiting.length}개{matched.length > 0 && ` · 약점이 겹치는 ${matched.length}개`} ›
        </Link>
      )}
    </section>
  )
}

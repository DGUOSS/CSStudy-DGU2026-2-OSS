import { Users } from 'lucide-react'
import { Link } from 'react-router'
import { useCourse } from '@/features/courses/queries'
import { MODE_LABEL, peopleLabel, useMyStudy } from '@/features/study_groups/useMyStudy'

/**
 * 퀴즈 결과의 스터디 입구(시안 S2): 이번에 약했던 개념이 겹치는 모집 중 스터디가 있으면 한 줄로 안내한다.
 * 없으면 아무것도 안 그린다. 겹치는 약점은 백엔드가 계산한 shared_weak(나와 그 스터디의 약점 교집합)를 쓴다.
 */
export function StudyNudge({ courseId, weakNames }: { courseId: number; weakNames: string[] }) {
  const course = useCourse(courseId)
  const subjectId = course.data?.subject_id
  const { matched } = useMyStudy(subjectId ? [subjectId] : [])
  // 이번 퀴즈의 약한 개념과 겹치는 것 우선, 없으면 약점이 겹치는 아무 스터디
  const hit =
    matched.find((g) => (g.shared_weak ?? []).some((w) => weakNames.includes(w))) ?? matched[0]
  if (!hit) return null
  const concept = (hit.shared_weak ?? []).find((w) => weakNames.includes(w)) ?? hit.shared_weak?.[0]
  return (
    <div className="flex flex-wrap items-center gap-3.5 rounded-xl border border-dashed border-[#c5cede] px-4 py-3.5">
      <span className="flex size-10 shrink-0 items-center justify-center rounded-xl bg-navy-tint text-navy">
        <Users size={20} aria-hidden="true" />
      </span>
      <span className="flex min-w-0 flex-[1_1_16rem] flex-col gap-0.5">
        <span className="text-[15px]">
          <b>같이 하면 덜 막혀요</b> · {concept}이(가) 약한 사람들이 모인 스터디가 있어요
        </span>
        <span className="truncate text-[13px] text-ink-2">
          {hit.title} · {MODE_LABEL[hit.mode] ?? hit.mode} · {peopleLabel(hit)}
        </span>
      </span>
      <Link
        to="/study/groups"
        className="inline-flex h-10 items-center rounded-full border border-home-line bg-white px-4 text-sm font-bold text-navy hover:bg-navy-tint"
      >
        스터디 보기
      </Link>
    </div>
  )
}

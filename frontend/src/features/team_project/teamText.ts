import type { Schemas } from '@/api/client'

type TeamLabel = Schemas['TeamLabelOut']

const SYLLABUS_TEXT: Record<string, string> = {
  yes: '팀 프로젝트 있음',
  no: '팀 프로젝트 없음',
  not_mentioned: '팀 프로젝트 언급 없음',
}

/** 라벨의 근거를 한 줄로: 운영진 / 수강생 n명 중 m명 / 계획서 문장 */
export function teamSourceText(t: TeamLabel, withTerm = true): string {
  const votes = t.yes_votes + t.no_votes
  const voteText = votes ? `수강생 ${votes}명 중 ${t.yes_votes}명 "있었다"` : ''
  const pending = votes ? `${voteText}(2명 이상·과반이면 반영)` : ''
  const syllabusText = t.syllabus
    ? `강의계획서: ${t.evidence ? `"${t.evidence}"` : SYLLABUS_TEXT[t.syllabus]}`
    : ''
  const parts =
    t.source === 'admin'
      ? [`운영진 확인${t.note ? `: ${t.note}` : ''}`, voteText, syllabusText]
      : t.source === 'students'
        ? [voteText, syllabusText]
        : t.source === 'syllabus'
          ? [syllabusText, pending]
          : [pending || '정보 없음']
  const body = parts.filter(Boolean).join(' · ')
  return withTerm ? `${t.term} · ${body}` : body
}

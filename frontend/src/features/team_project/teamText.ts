import type { Schemas } from '@/api/client'

type TeamLabel = Schemas['TeamLabelOut']

/** 라벨의 근거를 한 줄로: 어느 학기, 계획서인지 후기인지 */
export function teamSourceText(t: TeamLabel): string {
  const votes = t.yes_votes + t.no_votes
  const voteText = votes ? `후기 ${votes}명 중 ${t.yes_votes}명 "있었다"` : ''
  if (t.source === 'syllabus') {
    const base =
      t.label === 'likely_no'
        ? `${t.term} 강의계획서에 팀 프로젝트 언급 없음`
        : `${t.term} 강의계획서${t.evidence ? `: "${t.evidence}"` : ''}`
    return voteText ? `${base} · ${voteText}` : base
  }
  if (t.source === 'reviews') return `${t.term} ${voteText}`
  return `${t.term} 정보 없음`
}

import { Link, useParams } from 'react-router'
import { AppShell } from '@/features/home/AppShell'
import { useSubjects } from '@/features/courses/queries'
import { Empty, ErrorText, Loading } from '@/components/States'
import { StudyGroupsPanel } from './StudyGroupsPanel'

export function StudyGroupsPage({ design = false }: { design?: boolean }) {
  return design ? <AppShell><Content design /></AppShell> : <div className="flex flex-col gap-6"><Content design={false} /></div>
}
function Content({ design }: { design: boolean }) {
  const subjectId = Number(useParams().subjectId)
  const subjects = useSubjects()
  if (subjects.isPending) return <Loading />
  if (subjects.isError) return <ErrorText error={subjects.error} />
  const subject = subjects.data?.find(s => s.id === subjectId)
  if (!subject) return <Empty>과목을 찾을 수 없습니다.</Empty>
  return <><header><Link to={design ? "/study" : `/subjects/${subjectId}`} className="text-sm text-navy hover:underline">← 과목으로 돌아가기</Link><h1 className="mt-2 text-2xl font-bold">{subject.name} 스터디</h1><p className="mt-1 text-sm text-ink-2">교수님과 관계없이 같은 과목을 공부하는 사람들을 만나요.</p></header><StudyGroupsPanel key={subjectId} subjectId={subjectId} design={design} /></>
}

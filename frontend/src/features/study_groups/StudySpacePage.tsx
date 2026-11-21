import { useQuery } from '@tanstack/react-query'
import { ArrowLeft } from 'lucide-react'
import { Link, useParams } from 'react-router'
import { api, unwrap, ApiError } from '@/api/client'
import { Loading } from '@/components/States'
import { AppShell } from '@/features/home/AppShell'
import { useAuth } from '@/features/auth/useAuth'
import { StudyChat } from './StudyChat'

export function StudySpacePage({ design = false }: { design?: boolean }) {
  return design ? <AppShell><SpaceContent design /></AppShell> : <div className="flex flex-col gap-6"><SpaceContent design={false} /></div>
}

function SpaceContent({ design }: { design: boolean }) {
  const groupId = Number(useParams().groupId)
  const { user } = useAuth()
  const space = useQuery({
    queryKey: ['study-space', user?.id, groupId],
    queryFn: () => unwrap(api.GET('/api/v1/study-groups/{group_id}/space', { params: { path: { group_id: groupId } } })),
    enabled: !!user,
    staleTime: 0,
    retry: false,
  })
  if (space.isPending) return <Loading />
  if (space.isError) {
    const restricted = space.error instanceof ApiError && space.error.status === 403
    return <section role="alert" className="rounded-2xl border border-home-line bg-white p-6">
      <h1 className="text-xl font-bold">{restricted ? '참여 승인 후 입장할 수 있어요' : '스터디 공간을 열지 못했어요'}</h1>
      <p className="mt-2 text-sm text-ink-2">{space.error.message}</p>
      <div className="mt-5 flex gap-4"><Link to={design ? "/study" : "/"} className="text-sm font-bold text-navy hover:underline">내 과목으로 돌아가기</Link><button onClick={() => space.refetch()} className="text-sm font-bold text-navy hover:underline">다시 확인</button></div>
    </section>
  }
  const group = space.data
  return <>
    <header>
      <Link to={`${design ? "/study" : ""}/subjects/${group.subject_id}/groups`} className="inline-flex items-center gap-1 text-sm text-ink-2 hover:text-navy"><ArrowLeft size={16} />스터디 목록으로</Link>
      <div className="mt-4 flex flex-wrap items-center gap-2"><span className="rounded-full bg-navy-tint px-3 py-1 text-xs font-bold text-navy">{group.subject_name}</span><span className="text-xs text-ink-2">{group.is_owner ? '개설자' : '참여자'}</span></div>
      <h1 className="mt-3 break-words text-2xl font-bold">{group.title}</h1>
      <p className="mt-2 text-sm text-ink-2">개설자와 승인된 참여자만 함께하는 스터디 공간이에요.</p>
    </header>
    <StudyChat groupId={group.id} />
  </>
}

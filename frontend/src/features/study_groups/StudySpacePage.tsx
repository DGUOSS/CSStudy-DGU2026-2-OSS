import { useQuery } from '@tanstack/react-query'
import { ArrowLeft, Users } from 'lucide-react'
import { Link, useParams } from 'react-router'
import { api, unwrap, ApiError } from '@/api/client'
import { Loading } from '@/components/States'
import { AppShell } from '@/features/home/AppShell'
import { useAuth } from '@/features/auth/useAuth'

export function StudySpacePage() {
  return <AppShell><SpaceContent /></AppShell>
}

function SpaceContent() {
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
      <div className="mt-5 flex gap-4"><Link to="/study" className="text-sm font-bold text-navy hover:underline">내 과목으로 돌아가기</Link><button onClick={() => space.refetch()} className="text-sm font-bold text-navy hover:underline">다시 확인</button></div>
    </section>
  }
  const group = space.data
  return <>
    <header>
      <Link to={`/study/subjects/${group.subject_id}/groups`} className="inline-flex items-center gap-1 text-sm text-ink-2 hover:text-navy"><ArrowLeft size={16} />스터디 목록으로</Link>
      <div className="mt-4 flex flex-wrap items-center gap-2"><span className="rounded-full bg-navy-tint px-3 py-1 text-xs font-bold text-navy">{group.subject_name}</span><span className="text-xs text-ink-2">{group.is_owner ? '개설자' : '참여자'}</span></div>
      <h1 className="mt-3 break-words text-2xl font-bold">{group.title}</h1>
      <p className="mt-2 text-sm text-ink-2">개설자와 승인된 참여자만 함께하는 스터디 공간이에요.</p>
    </header>
    <section className="flex min-h-64 flex-col items-center justify-center rounded-2xl border border-home-line bg-white px-6 py-12 text-center">
      <span className="mb-4 flex size-14 items-center justify-center rounded-2xl bg-navy-tint text-navy"><Users size={28} aria-hidden="true" /></span>
      <h2 className="text-lg font-bold">우리 스터디 공간</h2>
      <p className="mt-2 text-sm leading-relaxed text-ink-2">아직 등록된 활동이 없어요.<br />함께 공부할 공간을 준비하고 있어요.</p>
    </section>
  </>
}

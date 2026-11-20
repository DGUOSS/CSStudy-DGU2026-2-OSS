import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router'
import { useState } from 'react'
import { Plus, Users } from 'lucide-react'
import { api, unwrap, type Schemas } from '@/api/client'
import { Empty, ErrorText, Loading } from '@/components/States'
import { Modal } from '@/components/Modal'
import { Button } from '@/components/ui/button'
import { useAuth } from '@/features/auth/useAuth'

type Study = Schemas['StudyOut']
type Draft = Schemas['StudyCreate']
const modes = { online: '온라인', offline: '오프라인', hybrid: '온·오프라인 병행' }
const inputClass = 'mt-1 w-full rounded-xl border border-home-line bg-white px-3 py-2 text-sm focus-visible:outline-2 focus-visible:outline-navy'
const blank: Draft = { title: '', description: '', capacity: 4, mode: 'offline', schedule: '', location: '' }

export function StudyGroupsPanel({ subjectId, design = false }: { subjectId: number; design?: boolean }) {
  const { user } = useAuth()
  const qc = useQueryClient()
  const [state, setState] = useState<'open' | 'closed' | 'all'>('open')
  const [page, setPage] = useState(0)
  const [creating, setCreating] = useState(false)
  const [draft, setDraft] = useState<Draft>({ ...blank })
  const [closing, setClosing] = useState<Study | null>(null)
  const [message, setMessage] = useState('')
  const key = ['study-groups', user?.id, subjectId]
  const groups = useQuery({
    queryKey: [...key, state, page],
    queryFn: () => unwrap(api.GET('/api/v1/subjects/{subject_id}/study-groups', { params: { path: { subject_id: subjectId }, query: { state, offset: page * 10, limit: 10 } } })),
    enabled: !!user,
  })
  const create = useMutation({
    mutationFn: () => unwrap(api.POST('/api/v1/subjects/{subject_id}/study-groups', { params: { path: { subject_id: subjectId } }, body: draft })),
    onSuccess: () => { qc.invalidateQueries({ queryKey: key }); setCreating(false); setPage(0); setState('open'); setMessage('스터디를 개설했어요.') },
  })
  const close = useMutation({
    mutationFn: (id: number) => unwrap(api.POST('/api/v1/subjects/{subject_id}/study-groups/{group_id}/close', { params: { path: { subject_id: subjectId, group_id: id } } })),
    onSuccess: () => { qc.invalidateQueries({ queryKey: key }); setClosing(null); qc.invalidateQueries({ queryKey: ['study-applications', user?.id] }); setPage(0); setMessage('모집을 종료했어요. 모집 종료 탭에서 다시 확인할 수 있어요.') },
  })
  return <section className="min-w-0 space-y-4 [--primary:var(--color-navy)] [--ring:var(--color-navy)] [&_button]:rounded-full" aria-label="과목 스터디 모집">
    <header className="flex flex-wrap items-center justify-between gap-3">
      <div><h2 className="text-xl font-bold">스터디 모집</h2><p className="mt-1 text-sm text-ink-2">같은 과목을 공부하는 사람들과 함께할 스터디를 열어 보세요.</p></div>
      <Button onClick={() => { setDraft({ ...blank }); create.reset(); setCreating(true) }}><Plus size={16} />스터디 개설</Button>
    </header>
    <div className="flex gap-2" role="group" aria-label="모집 상태">
      {([['open', '모집 중'], ['closed', '모집 종료'], ['all', '전체']] as const).map(([value, label]) => <Button key={value} variant={state === value ? 'default' : 'outline'} aria-pressed={state === value} onClick={() => { setState(value); setPage(0) }}>{label}</Button>)}
    </div>
    {(groups.data?.my_weak ?? []).length > 0 && <p className="rounded-xl bg-home-bg p-3 text-sm text-ink-2">내 약점 개념 <b className="text-navy">{groups.data?.my_weak?.join(', ')}</b> 기준으로, 약점이 비슷한 스터디를 먼저 보여 줘요.</p>}
    {message && <p role="status" className="rounded-xl bg-navy-tint p-3 text-sm text-navy">{message}</p>}
    {groups.isPending && <Loading />}
    {groups.isError && <div role="alert"><ErrorText error={groups.error} /><Button variant="outline" onClick={() => groups.refetch()}>다시 시도</Button></div>}
    {groups.data && !groups.data.items.length && <Empty>{state === 'open' ? '모집 중인 스터디가 없어요. 첫 스터디를 개설해 보세요.' : '해당하는 스터디가 없어요.'}</Empty>}
    <ul className="space-y-3">{groups.data?.items.map(group => <li key={group.id} className="rounded-2xl border border-home-line bg-white p-5">
      <div className="mb-3 flex flex-wrap items-center gap-2"><span className={`rounded-full px-3 py-1 text-xs font-bold ${group.closed_at ? 'bg-home-bg text-ink-2' : 'bg-gold-soft text-navy'}`}>{group.closed_at ? '모집 종료' : '모집 중'}</span>{group.is_mine && <span className="text-xs font-bold text-navy">내가 개설한 스터디</span>}{(group.shared_weak ?? []).length > 0 && <span className="rounded-full bg-navy-tint px-3 py-1 text-xs font-bold text-navy" title="나와 이 스터디 참여자들이 함께 어려워하는 개념">약점 비슷 · {group.shared_weak?.slice(0, 3).join(', ')}{(group.shared_weak?.length ?? 0) > 3 ? ` 외 ${(group.shared_weak?.length ?? 0) - 3}개` : ''}</span>}<span className="ml-auto text-xs text-ink-2">{new Date(group.created_at).toLocaleDateString('ko-KR')}</span></div>
      <h3 className="break-words text-lg font-bold">{group.title}</h3>
      <p className="mt-1 text-sm text-ink-2">개설자 {group.owner_name}</p>
      <p className="mt-3 whitespace-pre-wrap break-words text-sm leading-relaxed">{group.description}</p>
      <dl className="mt-4 grid gap-3 rounded-xl bg-home-bg p-4 text-sm sm:grid-cols-2">
        <div><dt className="text-xs font-bold text-ink-2">모집 규모</dt><dd className="mt-1 flex items-center gap-1"><Users size={16} />{group.capacity === 0 ? `${group.participant_count}명 참여 · 인원 제한 없음` : `${group.participant_count}/${group.capacity}명 참여`} (개설자 포함)</dd></div>
        <div><dt className="text-xs font-bold text-ink-2">진행 방식</dt><dd className="mt-1">{modes[group.mode]}</dd></div>
        <div><dt className="text-xs font-bold text-ink-2">시간·기간</dt><dd className="mt-1 whitespace-pre-wrap break-words">{group.schedule}</dd></div>
        <div><dt className="text-xs font-bold text-ink-2">장소·진행 채널</dt><dd className="mt-1 whitespace-pre-wrap break-words">{group.location}</dd></div>
      </dl>
      {(group.is_mine || group.my_application === 'approved') && <Link to={`${design ? "/study" : ""}/groups/${group.id}`} className="mt-4 inline-flex h-11 items-center rounded-full bg-navy px-5 text-sm font-bold text-white hover:bg-navy-deep">스터디 입장</Link>}
      <Participation group={group} subjectId={subjectId} onChanged={() => qc.invalidateQueries({ queryKey: key })} />
      {group.is_mine && !group.closed_at && <div className="mt-4 flex justify-end"><Button variant="outline" onClick={() => { close.reset(); setClosing(group) }}>모집 종료</Button></div>}
    </li>)}</ul>
    {groups.data && (page > 0 || groups.data.total > 10) && <nav aria-label="스터디 목록 페이지" className="flex items-center justify-center gap-3"><Button variant="outline" disabled={!page} onClick={() => setPage(page - 1)}>이전</Button><span className="text-sm">{page + 1}쪽</span><Button variant="outline" disabled={(page + 1) * 10 >= groups.data.total} onClick={() => setPage(page + 1)}>다음</Button></nav>}
    {creating && <Modal title="스터디 개설" onClose={() => setCreating(false)} busy={create.isPending}>
      <form className="flex min-h-0 flex-col" onSubmit={e => { e.preventDefault(); if (!create.isPending) create.mutate() }}>
        <fieldset disabled={create.isPending} className="min-h-0 space-y-4 overflow-y-auto p-5">
          <label className="block text-sm font-bold">스터디 제목<input required minLength={2} maxLength={100} className={inputClass} value={draft.title} onChange={e => setDraft({ ...draft, title: e.target.value })} placeholder="예: 프로세스 동기화 함께 복습해요" /></label>
          <label className="block text-sm font-bold">소개·학습 목표<textarea required minLength={10} maxLength={3000} rows={4} className={inputClass} value={draft.description} onChange={e => setDraft({ ...draft, description: e.target.value })} placeholder="함께 공부할 내용과 진행 방법을 10자 이상 적어 주세요." /></label>
          <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={draft.capacity === 0} onChange={e => setDraft({ ...draft, capacity: e.target.checked ? 0 : 4 })} />인원 제한 없음</label>
          <div className="grid gap-4 sm:grid-cols-2">
            <label className="block text-sm font-bold">총인원 (개설자 포함)<input required type="number" disabled={draft.capacity === 0} min={0} max={20} className={inputClass} value={Number.isNaN(draft.capacity) ? '' : draft.capacity} onChange={e => setDraft({ ...draft, capacity: e.target.valueAsNumber })} /></label>
            <label className="block text-sm font-bold">진행 방식<select className={inputClass} value={draft.mode} onChange={e => setDraft({ ...draft, mode: e.target.value as Draft['mode'] })}>{Object.entries(modes).map(([id, name]) => <option key={id} value={id}>{name}</option>)}</select></label>
          </div>
          <label className="block text-sm font-bold">시간·기간<input required minLength={2} maxLength={200} className={inputClass} value={draft.schedule} onChange={e => setDraft({ ...draft, schedule: e.target.value })} placeholder="예: 매주 수요일 18시 / 기말고사까지, 또는 협의 예정" /></label>
          <label className="block text-sm font-bold">장소·진행 채널<input required minLength={2} maxLength={200} className={inputClass} value={draft.location} onChange={e => setDraft({ ...draft, location: e.target.value })} placeholder="예: 중앙도서관 스터디룸 / 온라인, 또는 협의 예정" /></label>
          <p className="text-xs text-ink-2">입력한 내용과 개설자 이름은 이 과목을 열람할 수 있는 사용자에게 표시돼요.</p>
        </fieldset>
        <footer className="shrink-0 border-t border-home-line p-5"><ErrorText error={create.error} /><div className="flex justify-end gap-2"><Button type="button" variant="outline" disabled={create.isPending} onClick={() => setCreating(false)}>취소</Button><Button type="submit" disabled={create.isPending}>{create.isPending ? '개설 중…' : '개설하기'}</Button></div></footer>
      </form>
    </Modal>}
    {closing && <Modal title="모집을 종료할까요?" onClose={() => setClosing(null)} busy={close.isPending}><div className="overflow-y-auto p-5"><p className="break-words font-bold">{closing.title}</p><p className="mt-2 text-sm text-ink-2">종료 후에는 다시 모집할 수 없어요. 승인된 참여자는 유지되며 대기 중인 신청은 거절 처리됩니다.</p><ErrorText error={close.error} /><div className="mt-5 flex justify-end gap-2"><Button variant="outline" disabled={close.isPending} onClick={() => setClosing(null)}>취소</Button><Button disabled={close.isPending} onClick={() => close.mutate(closing.id)}>{close.isPending ? '종료 중…' : '모집 종료하기'}</Button></div></div></Modal>}
  </section>
}


const applicationLabels = { pending: '승인 대기', approved: '참여 중', rejected: '거절됨', cancelled: '취소됨' }
function Participation({ group, subjectId, onChanged }: { group: Study; subjectId: number; onChanged: () => void }) {
  const { user } = useAuth()
  const [show, setShow] = useState(false)
  const [cancelConfirm, setCancelConfirm] = useState(false)
  const query = useQuery({ queryKey: ['study-applications', user?.id, group.id], enabled: group.is_mine && show,
    queryFn: () => unwrap(api.GET('/api/v1/subjects/{subject_id}/study-groups/{group_id}/applications', { params: { path: { subject_id: subjectId, group_id: group.id } } })),
  })
  const action = useMutation({
    mutationFn: (kind: 'apply' | 'cancel') => {
      const params = { path: { subject_id: subjectId, group_id: group.id } }
      return kind === 'apply' ? unwrap(api.POST('/api/v1/subjects/{subject_id}/study-groups/{group_id}/apply', { params })) : unwrap(api.POST('/api/v1/subjects/{subject_id}/study-groups/{group_id}/cancel', { params }))
    }, onSuccess: () => { setCancelConfirm(false); onChanged() }, onError: () => onChanged(),
  })
  const decision = useMutation({
    mutationFn: ({ id, value }: { id: number; value: 'approved' | 'rejected' }) => unwrap(api.POST('/api/v1/subjects/{subject_id}/study-groups/{group_id}/applications/{application_id}/decision', { params: { path: { subject_id: subjectId, group_id: group.id, application_id: id } }, body: { decision: value } })),
    onSettled: () => { query.refetch(); onChanged() },
  })
  const full = group.capacity > 0 && group.participant_count >= group.capacity
  return <div className="mt-4 space-y-3">
    {group.is_mine ? <>
      <Button variant="outline" aria-expanded={show} onClick={() => setShow(!show)}>참여자 관리 · 신청 대기 {group.pending_count ?? 0}명</Button>
      {show && <div className="rounded-xl border border-home-line p-4">
        <p className="mb-3 text-sm font-bold">승인된 참여자 {group.participant_count - 1}명 · 개설자 1명</p>
        {query.isPending && <Loading />}<ErrorText error={query.error} />
        {query.isError && <Button variant="outline" onClick={() => query.refetch()}>다시 시도</Button>}
        {query.data?.length === 0 && <p className="text-sm text-ink-2">아직 신청자가 없어요.</p>}
        <ul className="divide-y divide-home-line">{query.data?.map(a => <li key={a.id} className="flex flex-wrap items-center gap-2 py-3"><span className="font-bold">{a.name}</span><span className="text-sm text-ink-2">{applicationLabels[a.status]}</span>{a.status === 'pending' && <div className="ml-auto flex gap-2"><Button size="sm" disabled={decision.isPending || !!group.closed_at || full} onClick={() => decision.mutate({ id: a.id, value: 'approved' })}>승인</Button><Button size="sm" variant="outline" disabled={decision.isPending} onClick={() => decision.mutate({ id: a.id, value: 'rejected' })}>거절</Button></div>}</li>)}</ul>
        <ErrorText error={decision.error} />
      </div>}
    </> : <div className="flex flex-wrap items-center gap-3">
      {group.my_application && <span className="text-sm font-bold text-navy">{applicationLabels[group.my_application]}</span>}
      {group.my_application === 'pending' || group.my_application === 'approved' ? <Button variant="outline" disabled={action.isPending} onClick={() => setCancelConfirm(true)}>{group.my_application === 'approved' ? '참여 취소' : '신청 취소'}</Button> : !group.closed_at && <Button disabled={action.isPending || full} onClick={() => action.mutate('apply')}>{full ? '정원 마감' : action.isPending ? '신청 중…' : '참여 신청'}</Button>}
      <ErrorText error={action.error} />
    </div>}
    {cancelConfirm && <Modal title="신청 또는 참여를 취소할까요?" onClose={() => setCancelConfirm(false)} busy={action.isPending}><div className="p-5"><p className="text-sm">승인된 참여를 취소하면 참여 인원에서 제외돼요. 다시 참여하려면 모집 중에 재신청해야 합니다.</p><ErrorText error={action.error} /><div className="mt-4 flex justify-end gap-2"><Button variant="outline" disabled={action.isPending} onClick={() => setCancelConfirm(false)}>돌아가기</Button><Button disabled={action.isPending} onClick={() => action.mutate('cancel')}>취소 확정</Button></div></div></Modal>}
  </div>
}

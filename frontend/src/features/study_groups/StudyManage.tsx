import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { api, unwrap } from '@/api/client'
import { Modal } from '@/components/Modal'
import { ErrorText, Loading } from '@/components/States'
import { useAuth } from '@/features/auth/useAuth'
import { btn, groupsKey } from './studyKit'
import type { Study } from './useMyStudy'

/** 개설자용: 신청자 승인·거절, 모집 종료 */
export function ManageModal({ g, onClose }: { g: Study; onClose: () => void }) {
  const { user } = useAuth()
  const qc = useQueryClient()
  const [confirmClose, setConfirmClose] = useState(false)
  const path = { subject_id: g.subject_id, group_id: g.id }
  const apps = useQuery({
    queryKey: ['study-applications', user?.id, g.id],
    queryFn: () =>
      unwrap(api.GET('/api/v1/subjects/{subject_id}/study-groups/{group_id}/applications', { params: { path } })),
  })
  const refresh = () => {
    apps.refetch()
    qc.invalidateQueries({ queryKey: groupsKey(user?.id, g.subject_id) })
  }
  const decide = useMutation({
    mutationFn: ({ id, value }: { id: number; value: 'approved' | 'rejected' }) =>
      unwrap(
        api.POST('/api/v1/subjects/{subject_id}/study-groups/{group_id}/applications/{application_id}/decision', {
          params: { path: { ...path, application_id: id } },
          body: { decision: value },
        }),
      ),
    onSettled: refresh,
  })
  const close = useMutation({
    mutationFn: () => unwrap(api.POST('/api/v1/subjects/{subject_id}/study-groups/{group_id}/close', { params: { path } })),
    onSuccess: () => {
      refresh()
      onClose()
    },
  })
  const full = g.capacity > 0 && g.participant_count >= g.capacity
  const pending = (apps.data ?? []).filter((a) => a.status === 'pending')
  const approved = (apps.data ?? []).filter((a) => a.status === 'approved')

  return (
    <Modal title={`${g.title} · 신청 관리`} onClose={onClose} busy={decide.isPending || close.isPending}>
      <div className="flex min-h-0 flex-col gap-5 overflow-y-auto p-5">
        {apps.isPending && <Loading />}
        <ErrorText error={apps.error ?? decide.error} />
        <section>
          <h3 className="mb-2 text-sm font-bold">
            기다리는 신청 <span className="font-normal text-ink-2">{pending.length}</span>
            {full && <span className="ml-2 text-xs font-bold text-[#8a6212]">정원이 차서 더 승인할 수 없어요</span>}
          </h3>
          {pending.length === 0 ? (
            <p className="rounded-xl bg-home-bg px-4 py-3 text-sm text-ink-2">기다리는 신청이 없어요.</p>
          ) : (
            <ul className="divide-y divide-home-line rounded-xl border border-home-line">
              {pending.map((a) => (
                <li key={a.id} className="flex items-center gap-2 px-4 py-2.5">
                  <span className="mr-auto font-bold">{a.name}</span>
                  <button
                    type="button"
                    className={btn.quiet}
                    disabled={decide.isPending}
                    onClick={() => decide.mutate({ id: a.id, value: 'rejected' })}
                  >
                    거절
                  </button>
                  <button
                    type="button"
                    className={btn.primary}
                    disabled={decide.isPending || full || !!g.closed_at}
                    onClick={() => decide.mutate({ id: a.id, value: 'approved' })}
                  >
                    승인
                  </button>
                </li>
              ))}
            </ul>
          )}
        </section>
        <section>
          <h3 className="mb-2 text-sm font-bold">
            함께하는 사람 <span className="font-normal text-ink-2">{approved.length + 1}</span>
          </h3>
          <div className="flex flex-wrap gap-1.5">
            <span className="rounded-full bg-gold-soft px-3 py-1 text-sm font-bold text-[#6b4a0c]">{g.owner_name} (개설자)</span>
            {approved.map((a) => (
              <span key={a.id} className="rounded-full bg-navy-tint px-3 py-1 text-sm font-bold text-navy">
                {a.name}
              </span>
            ))}
          </div>
        </section>
      </div>
      {!g.closed_at && (
        <footer className="flex shrink-0 flex-wrap items-center justify-end gap-2 border-t border-home-line px-5 py-4">
          {confirmClose ? (
            <>
              <p className="mr-auto text-sm text-ink-2">다시 열 수 없어요. 기다리는 신청은 거절돼요.</p>
              <button type="button" className={btn.quiet} onClick={() => setConfirmClose(false)}>
                취소
              </button>
              <button type="button" className={btn.primary} disabled={close.isPending} onClick={() => close.mutate()}>
                {close.isPending ? '닫는 중…' : '모집 끝내기'}
              </button>
            </>
          ) : (
            <button type="button" className={btn.line} onClick={() => setConfirmClose(true)}>
              모집 끝내기
            </button>
          )}
          <ErrorText error={close.error} />
        </footer>
      )}
    </Modal>
  )
}

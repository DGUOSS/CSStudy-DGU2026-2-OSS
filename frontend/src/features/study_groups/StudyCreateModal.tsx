import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { api, type Schemas, unwrap } from '@/api/client'
import { Modal } from '@/components/Modal'
import { ErrorText } from '@/components/States'
import { useAuth } from '@/features/auth/useAuth'
import { cn } from '@/lib/utils'

type Draft = Schemas['StudyCreate']
const blank: Draft = { title: '', description: '', capacity: 4, mode: 'offline', schedule: '', location: '' }
const MODES = [
  ['offline', '오프라인'],
  ['online', '온라인'],
  ['hybrid', '병행'],
] as const
const field =
  'mt-1.5 w-full rounded-xl border border-home-line bg-white px-3.5 py-2.5 text-[15px] focus-visible:outline-2 focus-visible:outline-navy'

/**
 * 새 디자인의 스터디 만들기 창. 과목 화면에서는 과목이 정해져 있고(subjectId),
 * 스터디 모음 화면에서는 창 안에서 과목을 고른다(subjects). 다른 화면을 거치지 않고 바로 만든다.
 */
export function StudyCreateModal({
  subjectId,
  subjects,
  onClose,
  onCreated,
}: {
  subjectId?: number
  subjects?: [number, string][]
  onClose: () => void
  onCreated?: (subjectId: number) => void
}) {
  const { user } = useAuth()
  const qc = useQueryClient()
  const [sid, setSid] = useState<number | null>(subjectId ?? subjects?.[0]?.[0] ?? null)
  const [d, setD] = useState<Draft>({ ...blank })
  const set = (patch: Partial<Draft>) => setD({ ...d, ...patch })
  const create = useMutation({
    mutationFn: () =>
      unwrap(api.POST('/api/v1/subjects/{subject_id}/study-groups', { params: { path: { subject_id: sid! } }, body: d })),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['study-groups', user?.id, sid] })
      onCreated?.(sid!)
      onClose()
    },
  })
  const unlimited = d.capacity === 0

  return (
    <Modal title="스터디 만들기" onClose={onClose} busy={create.isPending}>
      <form
        className="flex min-h-0 flex-col"
        onSubmit={(e) => {
          e.preventDefault()
          if (sid && !create.isPending) create.mutate()
        }}
      >
        <fieldset disabled={create.isPending} className="flex min-h-0 flex-col gap-4 overflow-y-auto p-5">
          {subjects && subjects.length > 1 && (
            <label className="block text-sm font-bold">
              과목
              <select className={field} value={sid ?? ''} onChange={(e) => setSid(Number(e.target.value))}>
                {subjects.map(([id, name]) => (
                  <option key={id} value={id}>
                    {name}
                  </option>
                ))}
              </select>
            </label>
          )}
          <label className="block text-sm font-bold">
            제목
            <input
              required
              minLength={2}
              maxLength={100}
              className={field}
              value={d.title}
              onChange={(e) => set({ title: e.target.value })}
              placeholder="예: 포인터 문제 같이 풀어요"
            />
          </label>
          <label className="block text-sm font-bold">
            소개
            <textarea
              required
              minLength={10}
              maxLength={3000}
              rows={3}
              className={field}
              value={d.description}
              onChange={(e) => set({ description: e.target.value })}
              placeholder="무엇을 어떻게 공부할지 10자 이상 적어 주세요"
            />
          </label>

          <div className="grid gap-4 sm:grid-cols-2">
            <div className="text-sm font-bold">
              진행 방식
              <div role="radiogroup" aria-label="진행 방식" className="mt-1.5 flex rounded-xl bg-home-bg p-1">
                {MODES.map(([id, label]) => (
                  <button
                    key={id}
                    type="button"
                    role="radio"
                    aria-checked={d.mode === id}
                    onClick={() => set({ mode: id })}
                    className={cn(
                      'h-9 flex-1 cursor-pointer rounded-lg text-sm font-bold',
                      d.mode === id ? 'bg-white text-navy shadow-sm' : 'text-ink-2 hover:text-navy',
                    )}
                  >
                    {label}
                  </button>
                ))}
              </div>
            </div>
            <div className="text-sm font-bold">
              인원 (나 포함)
              <div className="mt-1.5 flex items-center gap-3">
                <input
                  type="number"
                  aria-label="총인원"
                  required={!unlimited}
                  disabled={unlimited}
                  min={2}
                  max={20}
                  className={cn(field, 'mt-0 w-24 disabled:bg-home-bg disabled:text-ink-2')}
                  value={unlimited ? '' : Number.isNaN(d.capacity) ? '' : d.capacity}
                  onChange={(e) => set({ capacity: e.target.valueAsNumber })}
                />
                <label className="flex items-center gap-1.5 text-sm font-medium">
                  <input
                    type="checkbox"
                    className="size-4 accent-navy"
                    checked={unlimited}
                    onChange={(e) => set({ capacity: e.target.checked ? 0 : 4 })}
                  />
                  제한 없음
                </label>
              </div>
            </div>
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            <label className="block text-sm font-bold">
              언제
              <input
                required
                minLength={2}
                maxLength={200}
                className={field}
                value={d.schedule}
                onChange={(e) => set({ schedule: e.target.value })}
                placeholder="예: 매주 수 18:00"
              />
            </label>
            <label className="block text-sm font-bold">
              어디서
              <input
                required
                minLength={2}
                maxLength={200}
                className={field}
                value={d.location}
                onChange={(e) => set({ location: e.target.value })}
                placeholder="예: 중앙도서관 / 디스코드"
              />
            </label>
          </div>
          <p className="text-xs text-ink-2">적은 내용과 내 이름은 이 과목을 듣는 사람들에게 보여요.</p>
        </fieldset>
        <footer className="flex shrink-0 items-center justify-end gap-2 border-t border-home-line px-5 py-4">
          <div className="mr-auto min-w-0">
            <ErrorText error={create.error} />
          </div>
          <button
            type="button"
            disabled={create.isPending}
            onClick={onClose}
            className="h-11 cursor-pointer rounded-full border border-home-line px-5 text-[15px] font-bold text-ink-2 hover:bg-home-bg"
          >
            취소
          </button>
          <button
            type="submit"
            disabled={create.isPending || !sid}
            className="h-11 cursor-pointer rounded-full bg-navy px-5 text-[15px] font-bold text-white hover:bg-navy-deep disabled:opacity-50"
          >
            {create.isPending ? '만드는 중…' : '만들기'}
          </button>
        </footer>
      </form>
    </Modal>
  )
}

import { X } from 'lucide-react'
import { ErrorText } from '@/components/States'
import { Button } from '@/components/ui/button'
import { type MyStatus, STATUS_LABEL, useRemoveMySubject, useSetMySubject } from './queries'

/** 과목을 내 과목에 넣거나(수강 중/수강함) 빼는 버튼 묶음 */
export function MySubjectButtons({
  subjectId,
  status,
}: {
  subjectId: number
  status?: string | null
}) {
  const set = useSetMySubject()
  const remove = useRemoveMySubject()
  const busy = set.isPending || remove.isPending
  return (
    <div className="flex flex-col items-end gap-1">
      <div className="flex gap-1.5">
        {(['current', 'taken'] as MyStatus[]).map((s) => (
          <Button
            key={s}
            type="button"
            size="sm"
            variant={status === s ? 'default' : 'outline'}
            disabled={busy}
            onClick={() => status !== s && set.mutate({ subjectId, status: s })}
          >
            {STATUS_LABEL[s]}
          </Button>
        ))}
        {status && (
          <Button
            type="button"
            size="sm"
            variant="ghost"
            aria-label="내 과목에서 빼기"
            disabled={busy}
            onClick={() => remove.mutate(subjectId)}
          >
            <X />
          </Button>
        )}
      </div>
      <ErrorText error={set.error ?? remove.error} />
    </div>
  )
}

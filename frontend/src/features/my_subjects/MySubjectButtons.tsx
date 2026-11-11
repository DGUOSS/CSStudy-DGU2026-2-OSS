import { Check, Plus } from 'lucide-react'
import { ErrorText } from '@/components/States'
import { Button } from '@/components/ui/button'
import { useRemoveMySubject, useSetMySubject } from './queries'

/** 과목을 내 과목에 넣거나 빼는 버튼. 수강 중/수강함은 따로 나누지 않는다. */
export function MySubjectButtons({ subjectId, added }: { subjectId: number; added?: boolean }) {
  const set = useSetMySubject()
  const remove = useRemoveMySubject()
  const busy = set.isPending || remove.isPending
  return (
    <div className="flex flex-col items-end gap-1">
      {added ? (
        <Button
          type="button"
          size="sm"
          variant="secondary"
          disabled={busy}
          onClick={() => remove.mutate(subjectId)}
          title="누르면 내 과목에서 뺍니다"
        >
          <Check />
          내 과목
        </Button>
      ) : (
        <Button
          type="button"
          size="sm"
          variant="outline"
          disabled={busy}
          onClick={() => set.mutate({ subjectId, status: 'current' })}
        >
          <Plus />
          내 과목에 추가
        </Button>
      )}
      <ErrorText error={set.error ?? remove.error} />
    </div>
  )
}

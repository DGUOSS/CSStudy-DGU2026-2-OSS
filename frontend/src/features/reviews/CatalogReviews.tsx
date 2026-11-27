import { useState } from 'react'
import { Modal } from '@/components/Modal'
import { ReviewsTab } from './ReviewsTab'

export function CatalogReviews({ courseId, subject, professor }: {
  courseId: number | null
  subject: string
  professor: string | null
}) {
  const [open, setOpen] = useState(false)
  const title = professor ? `${subject} · ${professor} 교수님 강의평` : `${subject} 강의평`

  return (
    <>
      <button
        type="button"
        className="mt-1 inline-flex min-h-9 items-center rounded-full border border-home-line px-3 text-xs font-bold text-navy hover:bg-navy-tint"
        onClick={() => setOpen(true)}
      >
        강의평 보기
      </button>
      {open && (
        <Modal title={title} onClose={() => setOpen(false)}>
          <div className="min-h-0 overflow-y-auto p-5">
            {courseId == null
              ? <p className="text-sm text-ink-2">아직 등록된 강의평이 없어요.</p>
              : <ReviewsTab courseId={courseId} readOnly />}
          </div>
        </Modal>
      )}
    </>
  )
}

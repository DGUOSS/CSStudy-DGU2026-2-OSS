import { useLayoutEffect, useId, useRef, type ReactNode } from 'react'
import { X } from 'lucide-react'

/** Native modal: keyboard focus stays inside; Escape and closing restore the trigger. */
export function NoticeDialog({ title, children, onClose, busy = false }: {
  title: string; children: ReactNode; onClose: () => void; busy?: boolean
}) {
  const ref = useRef<HTMLDialogElement>(null)
  const heading = useId()
  useLayoutEffect(() => {
    const trigger = document.activeElement instanceof HTMLElement ? document.activeElement : null
    const previous = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    const dialog = ref.current
    dialog?.showModal()
    return () => {
      dialog?.close()
      document.body.style.overflow = previous
      trigger?.focus()
    }
  }, [])
  return <dialog ref={ref} aria-labelledby={heading}
    onCancel={event => { event.preventDefault(); if (!busy) onClose() }}
    className="m-auto max-h-[90dvh] w-[calc(100%-2rem)] max-w-2xl overflow-hidden rounded-2xl border border-home-line bg-white p-0 text-foreground backdrop:bg-navy-deep/40 [--primary:var(--color-navy)] [--ring:var(--color-navy)] [&_button]:rounded-full">
    <div className="flex max-h-[90dvh] flex-col">
      <header className="flex shrink-0 items-start justify-between gap-4 border-b border-home-line px-5 py-4">
        <h2 id={heading} className="min-w-0 break-words text-lg font-bold">{title}</h2>
        <button type="button" aria-label="닫기" disabled={busy} onClick={onClose}
          className="flex size-10 shrink-0 items-center justify-center text-ink-2 hover:bg-home-bg focus-visible:outline-2 focus-visible:outline-navy disabled:opacity-40"><X size={20} /></button>
      </header>
      {children}
    </div>
  </dialog>
}

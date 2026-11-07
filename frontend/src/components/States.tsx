import type { ReactNode } from 'react'

export function Loading() {
  return <p className="py-10 text-center text-sm text-muted-foreground">불러오는 중…</p>
}

export function ErrorText({ error }: { error: Error | null }) {
  if (!error) return null
  return <p className="py-4 text-sm text-destructive">{error.message}</p>
}

export function Empty({ children }: { children: ReactNode }) {
  return (
    <div className="rounded-xl border border-dashed p-8 text-center text-sm text-muted-foreground">
      {children}
    </div>
  )
}

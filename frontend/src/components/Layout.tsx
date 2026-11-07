import { BookOpenCheck, LogOut } from 'lucide-react'
import { Link, Navigate, Outlet, useLocation } from 'react-router'
import { Button } from '@/components/ui/button'
import { useAuth } from '@/features/auth/useAuth'

/** 로그인해야 볼 수 있는 화면의 공통 틀 */
export function Layout() {
  const { user, loading, logout } = useAuth()
  const location = useLocation()
  if (loading) return <p className="p-8 text-center text-muted-foreground">불러오는 중…</p>
  if (!user) return <Navigate to="/login" replace state={{ from: location.pathname }} />

  return (
    <div className="min-h-svh">
      <header className="sticky top-0 z-10 border-b bg-card/90 backdrop-blur">
        <div className="mx-auto flex h-14 max-w-4xl items-center justify-between px-4">
          <Link to="/" className="flex items-center gap-2 font-semibold">
            <BookOpenCheck className="size-5 text-primary" />
            동국 스터디
          </Link>
          <div className="flex items-center gap-2 text-sm">
            <span className="text-muted-foreground">{user.name}</span>
            <Button variant="ghost" size="sm" onClick={() => logout.mutate()}>
              <LogOut />
              로그아웃
            </Button>
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-4xl px-4 py-6">
        <Outlet />
      </main>
    </div>
  )
}

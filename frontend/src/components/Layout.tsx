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
      <header className="sticky top-0 z-10 border-b bg-card/90 backdrop-blur print:hidden">
        <div className="mx-auto flex h-14 max-w-4xl items-center justify-between px-4">
          <Link to="/" className="flex shrink-0 items-center gap-2 font-semibold whitespace-nowrap">
            <BookOpenCheck className="size-5 text-primary" />
            동국 스터디
          </Link>
          <div className="flex min-w-0 items-center gap-2 text-sm whitespace-nowrap sm:gap-3">
            {user.role === 'admin' && (
              <Link to="/admin/courses" className="text-primary hover:underline">
                관리
              </Link>
            )}
            <Link to="/find" className="text-muted-foreground hover:underline">
              강좌 찾기
            </Link>
            <Link to="/requests" className="text-muted-foreground hover:underline">
              내 요청
            </Link>
            {/* 휴대폰에서는 이름을 숨겨 메뉴가 줄바꿈되지 않게 */}
            <span className="hidden max-w-32 truncate text-muted-foreground sm:inline">{user.name}</span>
            <Button variant="ghost" size="sm" onClick={() => logout.mutate()} aria-label="로그아웃">
              <LogOut />
              <span className="hidden sm:inline">로그아웃</span>
            </Button>
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-4xl px-4 py-6 print:max-w-none print:p-0">
        <Outlet />
      </main>
    </div>
  )
}

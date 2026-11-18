import { BookOpen, GraduationCap, House, LayoutGrid, LogOut, School, User } from 'lucide-react'
import { Link, useLocation } from 'react-router'
import { useAuth } from '@/features/auth/useAuth'
import { cn } from '@/lib/utils'

const NAV = [
  { label: '홈', icon: LayoutGrid, to: '/home' },
  { label: '학습', icon: BookOpen, to: '/study' },
  { label: '생활', icon: House, to: null },
  { label: '학교', icon: School, to: null },
] as const

export function HomeSidebar() {
  const { user, logout } = useAuth()
  const { pathname } = useLocation()
  return (
    <aside className="hidden w-60 shrink-0 flex-col border-r border-home-line bg-white px-5 pt-7 pb-6 md:flex">
      <Link to="/home" className="flex items-center gap-3 px-2">
        <span className="flex size-10 items-center justify-center rounded-full bg-navy text-white">
          <GraduationCap size={22} />
        </span>
        <span className="text-xl font-bold tracking-tight">동국 스터디</span>
      </Link>

      <nav className="mt-8 flex flex-col gap-1.5">
        {NAV.map(({ label, icon: Icon, to }) => {
          const cls = 'flex h-12 items-center gap-3 rounded-xl px-4 text-base'
          if (!to)
            return (
              <span
                key={label}
                title="준비 중"
                className={cn(cls, 'cursor-not-allowed font-medium text-ink-2/50')}
              >
                <Icon size={20} strokeWidth={1.8} />
                {label}
              </span>
            )
          const active = pathname === to || pathname.startsWith(`${to}/`)
          return (
            <Link
              key={label}
              to={to}
              className={cn(
                cls,
                active
                  ? 'bg-navy-tint font-bold text-navy'
                  : 'font-medium text-ink-2 hover:bg-home-bg',
              )}
            >
              <Icon size={20} strokeWidth={1.8} />
              {label}
            </Link>
          )
        })}
      </nav>

      <div className="mt-auto flex flex-col gap-2 border-t border-home-line pt-4">
        {user?.role === 'admin' && (
          <Link to="/admin/courses" className="px-3 text-sm text-navy hover:underline">
            관리
          </Link>
        )}
        <Link to="/requests" className="px-3 text-sm text-ink-2 hover:underline">
          내 요청
        </Link>
        <div className="mt-1 flex items-center gap-3 px-1">
          <span className="flex size-9 items-center justify-center rounded-full bg-navy-tint text-navy">
            <User size={18} />
          </span>
          <span className="min-w-0 flex-1 truncate text-[15px] font-bold">{user?.name}</span>
          <button
            type="button"
            aria-label="로그아웃"
            title="로그아웃"
            onClick={() => logout.mutate()}
            className="cursor-pointer rounded-md p-1.5 text-ink-2 hover:bg-home-bg"
          >
            <LogOut size={18} />
          </button>
        </div>
      </div>
    </aside>
  )
}

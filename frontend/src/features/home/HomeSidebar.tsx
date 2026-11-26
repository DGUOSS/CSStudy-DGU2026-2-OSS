import { BookOpen, GraduationCap, House, LayoutGrid, LogOut, School, User, Users } from 'lucide-react'
import { Link, useLocation } from 'react-router'
import { useAuth } from '@/features/auth/useAuth'
import { cn } from '@/lib/utils'

// 스터디 화면 주소: /study/groups(모음), /study/groups/:id(채팅), /study/subjects/:id/groups(과목별)
const isStudyPath = (p: string) => p.startsWith('/study/groups') || /^\/study\/subjects\/[^/]+\/groups/.test(p)

const NAV = [
  { label: '홈', icon: LayoutGrid, to: '/home', active: (p: string) => p === '/home' },
  // 학습은 /study 아래 전부, 단 스터디 화면은 '스터디' 메뉴가 켜진다
  { label: '학습', icon: BookOpen, to: '/study', active: (p: string) => (p === '/study' || p.startsWith('/study/')) && !isStudyPath(p) },
  { label: '스터디', icon: Users, to: '/study/groups', active: isStudyPath },
  { label: '생활', icon: House, to: null, active: () => false },
  { label: '학교', icon: School, to: null, active: () => false },
] as const

export function HomeSidebar() {
  const { user, logout } = useAuth()
  const { pathname } = useLocation()
  return (
    // 화면 높이에 고정(sticky + h-svh): 본문이 길어져도 사이드바가 따라 늘어나지 않아 아래 프로필이 항상 보인다.
    // 메뉴가 화면보다 길어지면 사이드바 안에서만 스크롤
    <aside className="sticky top-0 hidden h-svh w-60 shrink-0 flex-col self-start overflow-y-auto border-r border-home-line bg-white px-5 pt-7 pb-6 md:flex">
      <Link to="/home" className="flex items-center gap-3 px-2">
        <span className="flex size-10 items-center justify-center rounded-full bg-navy text-white">
          <GraduationCap size={22} />
        </span>
        <span className="text-xl font-bold tracking-tight">동국 스터디</span>
      </Link>

      <nav className="mt-8 flex flex-col gap-1.5">
        {NAV.map(({ label, icon: Icon, to, active: isActive }) => {
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
          const active = isActive(pathname)
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

import { NavLink, Navigate } from 'react-router'
import { useAuth } from '@/features/auth/useAuth'
import { cn } from '@/lib/utils'

/** 관리자 화면 공통 탭. 관리자가 아니면 홈으로 보낸다. */
export function AdminNav() {
  const { user } = useAuth()
  if (user && user.role !== 'admin') return <Navigate to="/" replace />
  const tab = ({ isActive }: { isActive: boolean }) =>
    cn(
      'inline-flex h-10 shrink-0 items-center rounded-full px-4 text-sm font-bold whitespace-nowrap',
      isActive
        ? 'bg-primary text-primary-foreground'
        : 'border bg-card text-muted-foreground hover:bg-accent hover:text-accent-foreground',
    )
  return (
    <nav aria-label="관리 메뉴" className="flex gap-2 overflow-x-auto pb-1">
      <NavLink to="/admin/courses" className={tab}>
        과목·강좌·교안 관리
      </NavLink>
      <NavLink to="/admin/requests" className={tab}>
        강좌 열기 요청
      </NavLink>
      <NavLink to="/admin/catalog" className={tab}>
        개설 목록
      </NavLink>
    </nav>
  )
}

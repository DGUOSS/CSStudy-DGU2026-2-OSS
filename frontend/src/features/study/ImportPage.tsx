import { ArrowLeft } from 'lucide-react'
import { Link } from 'react-router'
import { ImportPanel } from '@/features/enrollments/ImportPanel'
import { AppShell } from '@/features/home/AppShell'

/** 수강 기록 가져오기(/study/import): 엔드림스에서 내 수강 기록을 보내 내 강좌를 채운다. */
export function ImportPage() {
  return (
    <AppShell>
      <Link to="/study" className="inline-flex items-center gap-1 text-sm font-bold text-navy">
        <ArrowLeft size={16} />
        학습으로
      </Link>
      <div>
        <h1 className="text-2xl font-bold">수강 기록 가져오기</h1>
        <p className="mt-1 text-sm text-ink-2">
          엔드림스의 수강 기록을 가져오면 내가 들은 수업의 강좌가 &lsquo;내 강좌&rsquo;에 나타나요.
          엔드림스 로그인은 직접 하고, 비밀번호는 동국스터디로 오지 않아요.
        </p>
      </div>
      <div className="rounded-2xl border border-home-line bg-white p-5 [--primary:var(--color-navy)] [--ring:var(--color-navy)]">
        <ImportPanel compact />
      </div>
    </AppShell>
  )
}

import { BookOpenCheck, FileText, GraduationCap, MessageSquareText, Users } from 'lucide-react'
import { type FormEvent, useState } from 'react'
import { Link, Navigate, useLocation, useNavigate } from 'react-router'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { DESIGN_ON } from '@/lib/design'
import { SchoolLogin } from './SchoolLogin'
import { useAuth, useSchoolLoginConfig } from './useAuth'

export function AuthPage({ mode }: { mode: 'login' | 'signup' }) {
  const { user, login, signup, googleLogin } = useAuth()
  const navigate = useNavigate()
  const from = (useLocation().state as { from?: string } | null)?.from ?? '/'
  const [email, setEmail] = useState('')
  const [name, setName] = useState('')
  const [password, setPassword] = useState('')
  const mutation = mode === 'login' ? login : signup
  const school = useSchoolLoginConfig()
  // 학교 계정 로그인이 켜져 있으면 그것만 쓴다(처음 로그인하면 자동 가입). 꺼져 있을 때만 이메일 로그인
  const schoolOnly = Boolean(school.data?.client_id)

  if (user) return <Navigate to={from} replace />
  if (school.isPending) return null
  if (schoolOnly && mode === 'signup') return <Navigate to="/login" state={{ from }} replace />

  const submit = (e: FormEvent) => {
    e.preventDefault()
    const done = { onSuccess: () => navigate(from, { replace: true }) }
    if (mode === 'login') login.mutate({ email, password }, done)
    else signup.mutate({ email, name, password }, done)
  }

  const card = (
      <Card>
        <CardHeader>
          <CardTitle className="text-xl">
            {mode === 'login' || schoolOnly ? '로그인' : '회원가입'}
          </CardTitle>
          <CardDescription>동국대 과목·교수별 시험 공부</CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          <SchoolLogin
            onCredential={(c) =>
              googleLogin.mutate(c, { onSuccess: () => navigate(from, { replace: true }) })
            }
          />
          {googleLogin.error && (
            <p className="text-sm text-destructive">{googleLogin.error.message}</p>
          )}
          {!schoolOnly && (
            <form onSubmit={submit} className="flex flex-col gap-4">
              <div className="grid gap-2">
                <Label htmlFor="email">{mode === 'login' ? '이메일 또는 아이디' : '이메일'}</Label>
                <Input
                  id="email"
                  type={mode === 'login' ? 'text' : 'email'}
                  autoComplete={mode === 'login' ? 'username' : 'email'}
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                />
              </div>
              {mode === 'signup' && (
                <div className="grid gap-2">
                  <Label htmlFor="name">이름</Label>
                  <Input
                    id="name"
                    required
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                  />
                </div>
              )}
              <div className="grid gap-2">
                <Label htmlFor="password">비밀번호{mode === 'signup' && ' (8자 이상)'}</Label>
                <Input
                  id="password"
                  type="password"
                  autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
                  minLength={mode === 'signup' ? 8 : undefined}
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                />
              </div>
              {mutation.error && (
                <p className="text-sm text-destructive">{mutation.error.message}</p>
              )}
              <Button type="submit" disabled={mutation.isPending}>
                {mode === 'login' ? '로그인' : '가입하기'}
              </Button>
              <p className="text-center text-sm text-muted-foreground">
                {mode === 'login' ? (
                  <>
                    계정이 없나요?{' '}
                    <Link to="/signup" state={{ from }} className="font-bold text-primary underline">
                      회원가입
                    </Link>
                  </>
                ) : (
                  <>
                    이미 계정이 있나요?{' '}
                    <Link to="/login" state={{ from }} className="font-bold text-primary underline">
                      로그인
                    </Link>
                  </>
                )}
              </p>
            </form>
          )}
        </CardContent>
      </Card>
  )

  if (!DESIGN_ON)
    return <div className="mx-auto flex min-h-svh max-w-sm flex-col justify-center px-4">{card}</div>

  // 새 디자인: 왼쪽 남색 소개(넓은 화면만) + 오른쪽 로그인 상자. 동작(학교 로그인·이메일 폼)은 위와 같다
  const title = mode === 'login' || schoolOnly ? '로그인' : '회원가입'
  const input =
    'h-12 w-full rounded-xl border border-home-line bg-white px-3.5 text-[15px] focus-visible:outline-2 focus-visible:outline-navy'
  return (
    <div className="design-scope grid min-h-svh bg-home-bg lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
      <aside className="hidden flex-col justify-between bg-navy-deep p-12 text-white lg:flex">
        <div className="flex items-center gap-3">
          <span className="flex size-11 items-center justify-center rounded-full bg-white text-navy">
            <GraduationCap size={24} aria-hidden="true" />
          </span>
          <span className="text-2xl font-bold tracking-tight">동국 스터디</span>
        </div>
        <div className="flex flex-col gap-8">
          <h1 className="text-4xl leading-tight font-bold">
            우리 교수님 시험,
            <br />
            미리 풀어 보기
          </h1>
          <ul className="flex flex-col gap-4 text-[15px] text-[#c9d3e8]">
            {[
              [BookOpenCheck, '교수님 강좌별 교안으로 만든 퀴즈'],
              [FileText, '종이 모의고사와 결과 리포트'],
              [MessageSquareText, '강의평·팀플 이력으로 수업 미리 보기'],
              [Users, '같은 과목 사람들과 스터디'],
            ].map(([Icon, text]) => {
              const I = Icon as typeof Users
              return (
                <li key={text as string} className="flex items-center gap-3">
                  <span className="flex size-9 items-center justify-center rounded-xl bg-white/10 text-white">
                    <I size={18} aria-hidden="true" />
                  </span>
                  {text as string}
                </li>
              )
            })}
          </ul>
        </div>
        <p className="text-sm text-[#c9d3e8]">동국대학교 공개SW프로젝트</p>
      </aside>

      <main className="flex flex-col items-center justify-center gap-6 px-4 py-10">
        <div className="flex items-center gap-3 lg:hidden">
          <span className="flex size-11 items-center justify-center rounded-full bg-navy text-white">
            <GraduationCap size={24} aria-hidden="true" />
          </span>
          <span className="text-2xl font-bold tracking-tight">동국 스터디</span>
        </div>
        <section className="flex w-full max-w-sm flex-col gap-5 rounded-3xl border border-home-line bg-white p-8">
          <div>
            <h2 className="text-2xl font-bold">{title}</h2>
            <p className="mt-1 text-sm text-ink-2">
              {schoolOnly ? '동국대 Google 계정으로 들어와요. 처음이면 자동으로 가입돼요.' : '동국대 과목·교수별 시험 공부'}
            </p>
          </div>
          <SchoolLogin
            onCredential={(c) => googleLogin.mutate(c, { onSuccess: () => navigate(from, { replace: true }) })}
          />
          {googleLogin.error && <p className="text-sm text-[#c8453f]">{googleLogin.error.message}</p>}
          {/* 구글(학교 계정) 로그인일 때는 가입 대신 학교 계정 관리 사이트로 안내 */}
          {schoolOnly && (
            <p className="border-t border-home-line pt-4 text-center text-sm text-ink-2">
              학교 계정이 없거나 비밀번호를 잊었나요?{' '}
              <a
                href="https://cloud.dongguk.edu"
                target="_blank"
                rel="noopener noreferrer"
                className="font-bold whitespace-nowrap text-navy hover:underline"
              >
                학교 계정 관리 ↗
              </a>
            </p>
          )}
          {!schoolOnly && (
            <form onSubmit={submit} className="flex flex-col gap-4">
              <label className="flex flex-col gap-1.5 text-sm font-bold">
                {mode === 'login' ? '이메일 또는 아이디' : '이메일'}
                <input
                  className={input}
                  type={mode === 'login' ? 'text' : 'email'}
                  autoComplete={mode === 'login' ? 'username' : 'email'}
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                />
              </label>
              {mode === 'signup' && (
                <label className="flex flex-col gap-1.5 text-sm font-bold">
                  이름
                  <input className={input} required value={name} onChange={(e) => setName(e.target.value)} />
                </label>
              )}
              <label className="flex flex-col gap-1.5 text-sm font-bold">
                비밀번호{mode === 'signup' && <span className="font-normal text-ink-2"> (8자 이상)</span>}
                <input
                  className={input}
                  type="password"
                  autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
                  minLength={mode === 'signup' ? 8 : undefined}
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                />
              </label>
              {mutation.error && <p className="text-sm text-[#c8453f]">{mutation.error.message}</p>}
              <button
                type="submit"
                disabled={mutation.isPending}
                className="h-12 cursor-pointer rounded-full bg-navy text-base font-bold text-white hover:bg-navy-deep disabled:opacity-50"
              >
                {mutation.isPending ? '잠시만요…' : mode === 'login' ? '로그인' : '가입하기'}
              </button>
              <p className="text-center text-sm text-ink-2">
                {mode === 'login' ? '계정이 없나요? ' : '이미 계정이 있나요? '}
                <Link
                  to={mode === 'login' ? '/signup' : '/login'}
                  state={{ from }}
                  className="font-bold text-navy hover:underline"
                >
                  {mode === 'login' ? '회원가입' : '로그인'}
                </Link>
              </p>
            </form>
          )}
        </section>
      </main>
    </div>
  )
}

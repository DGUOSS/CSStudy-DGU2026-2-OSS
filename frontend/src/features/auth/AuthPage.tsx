import { type FormEvent, useState } from 'react'
import { Link, Navigate, useLocation, useNavigate } from 'react-router'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { useAuth } from './useAuth'

export function AuthPage({ mode }: { mode: 'login' | 'signup' }) {
  const { user, login, signup } = useAuth()
  const navigate = useNavigate()
  const from = (useLocation().state as { from?: string } | null)?.from ?? '/'
  const [email, setEmail] = useState('')
  const [name, setName] = useState('')
  const [password, setPassword] = useState('')
  const mutation = mode === 'login' ? login : signup

  if (user) return <Navigate to={from} replace />

  const submit = (e: FormEvent) => {
    e.preventDefault()
    const done = { onSuccess: () => navigate(from, { replace: true }) }
    if (mode === 'login') login.mutate({ email, password }, done)
    else signup.mutate({ email, name, password }, done)
  }

  return (
    <div className="mx-auto flex min-h-svh max-w-sm flex-col justify-center px-4">
      <Card>
        <CardHeader>
          <CardTitle className="text-xl">{mode === 'login' ? '로그인' : '회원가입'}</CardTitle>
          <CardDescription>동국대 과목·교수별 시험 공부</CardDescription>
        </CardHeader>
        <CardContent>
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
                <Input id="name" required value={name} onChange={(e) => setName(e.target.value)} />
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
                  <Link to="/signup" state={{ from }} className="text-primary underline">
                    회원가입
                  </Link>
                </>
              ) : (
                <>
                  이미 계정이 있나요?{' '}
                  <Link to="/login" state={{ from }} className="text-primary underline">
                    로그인
                  </Link>
                </>
              )}
            </p>
          </form>
        </CardContent>
      </Card>
    </div>
  )
}

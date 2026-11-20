/** 로그인 상태는 이 훅 하나로만 본다. 로그인 방식을 바꿔도 여기만 고치면 된다. */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api, ApiError, type Schemas, unwrap } from '@/api/client'

export type User = Schemas['UserOut']

export function useAuth() {
  const qc = useQueryClient()
  const me = useQuery({
    queryKey: ['me'],
    queryFn: async () => {
      try {
        return await unwrap(api.GET('/api/v1/auth/me'))
      } catch (e) {
        if (e instanceof ApiError && e.status === 401) return null
        throw e
      }
    },
    staleTime: Infinity,
  })

  const onLoggedIn = (user: User) => {
    qc.clear()
    qc.setQueryData(['me'], user)
  }

  const login = useMutation({
    mutationFn: (body: Schemas['LoginIn']) => unwrap(api.POST('/api/v1/auth/login', { body })),
    onSuccess: onLoggedIn,
  })
  const signup = useMutation({
    mutationFn: (body: Schemas['SignupIn']) => unwrap(api.POST('/api/v1/auth/signup', { body })),
    onSuccess: onLoggedIn,
  })
  // 동국대 계정(Google) 로그인: Google이 준 ID 토큰을 서버가 검증한다
  const googleLogin = useMutation({
    mutationFn: (credential: string) =>
      unwrap(api.POST('/api/v1/auth/google', { body: { credential } })),
    onSuccess: onLoggedIn,
  })
  const logout = useMutation({
    mutationFn: () => unwrap(api.POST('/api/v1/auth/logout')),
    onSuccess: () => {
      qc.clear()
      qc.setQueryData(['me'], null)
    },
  })

  return { user: me.data ?? null, loading: me.isPending, login, signup, googleLogin, logout }
}

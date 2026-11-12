import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import { ApiError } from './api/client'
import App from './App.tsx'
import { stashNdrimsHash } from './features/ndrims/receive'

// 엔드림스 창이 새 탭으로 보낸 기록(/ndrims#...)을 로그인 화면을 거치기 전에 옮겨 둔다
stashNdrimsHash()

const queryClient = new QueryClient({
  defaultOptions: { queries: {
      // 권한 없음(403)·없음(404) 같은 4xx는 다시 시도해도 같으니 바로 보여 준다
      retry: (n, e) => n < 1 && !(e instanceof ApiError && e.status < 500),
      refetchOnWindowFocus: false,
    }, },
})

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>
  </StrictMode>,
)

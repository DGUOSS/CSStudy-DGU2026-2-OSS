import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import { ApiError } from './api/client'
import App from './App.tsx'

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

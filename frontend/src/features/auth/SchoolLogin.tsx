/** 동국대 계정 로그인 버튼. 동국대 메일은 Google 워크스페이스라 Google 로그인 버튼을 쓴다. */
import { useEffect, useRef } from 'react'
import { useSchoolLoginConfig } from './useAuth'

type GoogleId = {
  initialize: (o: {
    client_id: string
    callback: (r: { credential: string }) => void
    hd?: string
    ux_mode?: 'popup'
  }) => void
  renderButton: (el: HTMLElement, o: Record<string, unknown>) => void
}
declare global {
  interface Window {
    google?: { accounts: { id: GoogleId } }
  }
}

const GSI_SRC = 'https://accounts.google.com/gsi/client'
let gsiLoad: Promise<void> | null = null
function loadGsi() {
  gsiLoad ??= new Promise((resolve, reject) => {
    const s = document.createElement('script')
    s.src = GSI_SRC
    s.async = true
    s.onload = () => resolve()
    s.onerror = () => {
      gsiLoad = null
      reject(new Error('Google 로그인을 불러오지 못했습니다'))
    }
    document.head.appendChild(s)
  })
  return gsiLoad
}

export function SchoolLogin({ onCredential }: { onCredential: (credential: string) => void }) {
  const box = useRef<HTMLDivElement>(null)
  const cb = useRef(onCredential)
  useEffect(() => {
    cb.current = onCredential
  })
  const config = useSchoolLoginConfig()
  const clientId = config.data?.client_id
  const domain = config.data?.domain

  useEffect(() => {
    if (!clientId) return
    const run = { alive: true }
    loadGsi()
      .then(() => {
        const id = window.google?.accounts.id
        if (!run.alive || !id || !box.current) return
        // hd는 계정 고르는 화면에서 학교 계정을 먼저 보여 줄 뿐이고, 실제 확인은 서버가 한다
        id.initialize({
          client_id: clientId,
          hd: domain,
          ux_mode: 'popup',
          callback: (r) => cb.current(r.credential),
        })
        id.renderButton(box.current, {
          theme: 'outline',
          size: 'large',
          shape: 'pill', // 사이트의 다른 버튼처럼 둥글게
          text: 'continue_with',
          locale: 'ko',
          width: box.current.clientWidth || 320,
        })
      })
      .catch(() => {})
    return () => {
      run.alive = false
    }
  }, [clientId, domain])

  if (!clientId) return null
  return (
    <div className="flex flex-col gap-2">
      <div ref={box} className="flex min-h-10 w-full justify-center" />
      <p className="text-center text-xs text-ink-2">
        동국대 계정(@{domain})만 로그인할 수 있습니다
      </p>
    </div>
  )
}

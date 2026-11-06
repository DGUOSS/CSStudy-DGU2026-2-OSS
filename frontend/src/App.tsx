import { useEffect, useState } from 'react'

export default function App() {
  const [status, setStatus] = useState('확인 중')
  useEffect(() => {
    fetch('/api/v1/health')
      .then((r) => r.json())
      .then((d) => setStatus(d.status))
      .catch(() => setStatus('백엔드 연결 실패'))
  }, [])
  return <h1>dgu-study 백엔드: {status}</h1>
}

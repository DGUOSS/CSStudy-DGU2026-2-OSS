import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [react()],
  server: {
    // WSL에서 윈도우 폴더(/mnt/c)를 쓸 때 파일 변경 감지용
    watch: { usePolling: true, interval: 300 },
    // /api 요청을 백엔드로 전달
    proxy: { '/api': 'http://localhost:8000' },
  },
})

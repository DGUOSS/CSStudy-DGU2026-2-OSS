/** 답안지 SVG를 A4 200dpi PNG로 받는다(인쇄 대신 그림판·태블릿에서 칠할 때) */
export function downloadPng(svg: string, filename: string) {
  const url = URL.createObjectURL(new Blob([svg], { type: 'image/svg+xml' }))
  const img = new Image()
  img.onload = () => {
    const canvas = document.createElement('canvas')
    canvas.width = 1654
    canvas.height = 2339
    const ctx = canvas.getContext('2d')!
    ctx.fillStyle = '#fff'
    ctx.fillRect(0, 0, canvas.width, canvas.height)
    ctx.drawImage(img, 0, 0, canvas.width, canvas.height)
    URL.revokeObjectURL(url)
    canvas.toBlob((blob) => {
      if (!blob) return
      const a = document.createElement('a')
      a.href = URL.createObjectURL(blob)
      a.download = filename
      a.click()
      setTimeout(() => URL.revokeObjectURL(a.href), 1000)
    }, 'image/png')
  }
  img.src = url
}

/** 답안지 모든 쪽을 PNG로 받는다 */
export function downloadSheetPngs(pages: string[], paperId: number) {
  pages.forEach((svg, i) => downloadPng(svg, `답안지_${paperId}_${i + 1}쪽.png`))
}

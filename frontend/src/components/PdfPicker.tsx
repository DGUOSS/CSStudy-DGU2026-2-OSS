import { FileText, Upload, X } from 'lucide-react'
import { useRef, useState } from 'react'
import { cn } from '@/lib/utils'

/** 교안 PDF 고르기: 눌러서 고르거나 끌어다 놓는 상자 + 고른 파일 목록(빼기 가능) */
export function PdfPicker({ files, onChange }: { files: File[]; onChange: (f: File[]) => void }) {
  const ref = useRef<HTMLInputElement>(null)
  const [over, setOver] = useState(false)
  const add = (list: FileList | null) => {
    const pdfs = Array.from(list ?? []).filter(
      (f) => f.type === 'application/pdf' || f.name.toLowerCase().endsWith('.pdf'),
    )
    const seen = new Set(files.map((f) => f.name + f.size))
    onChange([...files, ...pdfs.filter((f) => !seen.has(f.name + f.size))])
  }
  return (
    <div className="flex flex-col gap-2">
      <button
        type="button"
        onClick={() => ref.current?.click()}
        onDragOver={(e) => {
          e.preventDefault()
          setOver(true)
        }}
        onDragLeave={() => setOver(false)}
        onDrop={(e) => {
          e.preventDefault()
          setOver(false)
          add(e.dataTransfer.files)
        }}
        className={cn(
          'flex cursor-pointer flex-col items-center gap-1 rounded-lg border-2 border-dashed px-4 py-5 text-sm transition-colors',
          over ? 'border-primary bg-primary/5' : 'border-muted-foreground/30 hover:border-primary',
        )}
      >
        <Upload className="size-5 text-primary" />
        <span className="font-medium">교안 PDF 고르기</span>
        <span className="text-xs text-muted-foreground">
          여기를 누르거나 파일을 끌어다 놓으세요. 여러 개 가능
        </span>
      </button>
      <input
        ref={ref}
        type="file"
        accept="application/pdf,.pdf"
        multiple
        className="hidden"
        onChange={(e) => {
          add(e.target.files)
          e.target.value = ''
        }}
      />
      {files.length > 0 && (
        <ul className="flex flex-col gap-1">
          {files.map((f, i) => (
            <li
              key={f.name + f.size}
              className="flex items-center gap-2 rounded-md border bg-card px-2 py-1 text-xs"
            >
              <FileText className="size-3.5 shrink-0 text-muted-foreground" />
              <span className="min-w-0 flex-1 truncate">{f.name}</span>
              <span className="text-muted-foreground">
                {f.size < 1024 * 1024
                  ? `${Math.max(1, Math.round(f.size / 1024))}KB`
                  : `${(f.size / 1024 / 1024).toFixed(1)}MB`}
              </span>
              <button
                type="button"
                aria-label={`${f.name} 빼기`}
                className="cursor-pointer rounded p-0.5 hover:bg-muted"
                onClick={() => onChange(files.filter((_, j) => j !== i))}
              >
                <X className="size-3.5" />
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

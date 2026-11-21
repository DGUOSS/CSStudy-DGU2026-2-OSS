/** 스터디 공간 채팅. 3초마다 새 메시지만 받아 온다(창이 보일 때만). */
import { useMutation } from '@tanstack/react-query'
import { type FormEvent, useEffect, useRef, useState } from 'react'
import { Send } from 'lucide-react'
import { api, unwrap, type Schemas } from '@/api/client'
import { ErrorText } from '@/components/States'

type Message = Schemas['MessageOut']
const POLL_MS = 3000
// 서버 시각은 UTC. DB에 따라 시간대 표시 없이 오므로 그때는 UTC로 읽는다
const asUtc = (t: string) => new Date(/[zZ]|[+-]\d\d:\d\d$/.test(t) ? t : `${t}Z`)

function fetchMessages(groupId: number, afterId: number) {
  return unwrap(
    api.GET('/api/v1/study-groups/{group_id}/messages', {
      params: { path: { group_id: groupId }, query: { after_id: afterId } },
    }),
  )
}

export function StudyChat({ groupId }: { groupId: number }) {
  const [messages, setMessages] = useState<Message[]>([])
  const [loaded, setLoaded] = useState(false)
  const [error, setError] = useState<Error | null>(null)
  const [draft, setDraft] = useState('')
  const lastId = useRef(0)
  const box = useRef<HTMLDivElement>(null)

  const add = (incoming: Message[]) => {
    if (!incoming.length) return
    setMessages((prev) => {
      const seen = new Set(prev.map((m) => m.id))
      const next = [...prev, ...incoming.filter((m) => !seen.has(m.id))]
      lastId.current = Math.max(lastId.current, ...next.map((m) => m.id))
      return next
    })
  }

  useEffect(() => {
    const run = { stop: false }
    const tick = async () => {
      if (document.hidden && lastId.current) return
      try {
        add(await fetchMessages(groupId, lastId.current))
        setError(null)
      } catch (e) {
        setError(e as Error)
      } finally {
        if (!run.stop) setLoaded(true)
      }
    }
    tick()
    const timer = setInterval(tick, POLL_MS)
    return () => {
      run.stop = true
      clearInterval(timer)
    }
  }, [groupId])

  useEffect(() => {
    const el = box.current
    if (el) el.scrollTop = el.scrollHeight
  }, [messages.length])

  const send = useMutation({
    mutationFn: (body: string) =>
      unwrap(
        api.POST('/api/v1/study-groups/{group_id}/messages', {
          params: { path: { group_id: groupId } },
          body: { body },
        }),
      ),
    onSuccess: (m) => {
      add([m])
      setDraft('')
    },
  })

  const submit = (e: FormEvent) => {
    e.preventDefault()
    const body = draft.trim()
    if (body && !send.isPending) send.mutate(body)
  }

  return (
    <section
      aria-label="스터디 채팅"
      className="flex h-[32rem] max-h-[70svh] min-h-80 flex-col rounded-2xl border border-home-line bg-white"
    >
      <header className="border-b border-home-line px-5 py-3">
        <h2 className="font-bold">스터디 채팅</h2>
        <p className="text-xs text-ink-2">개설자와 승인된 참여자만 볼 수 있어요.</p>
      </header>
      <div
        ref={box}
        className="min-h-0 flex-1 space-y-3 overflow-y-auto px-5 py-4"
        aria-live="polite"
      >
        {!loaded && <p className="text-sm text-ink-2">불러오는 중…</p>}
        {loaded && !messages.length && (
          <p className="py-10 text-center text-sm text-ink-2">
            아직 대화가 없어요. 첫 인사를 남겨 보세요.
          </p>
        )}
        {messages.map((m) => (
          <div key={m.id} className={`flex flex-col ${m.is_mine ? 'items-end' : 'items-start'}`}>
            {!m.is_mine && (
              <span className="mb-1 text-xs text-ink-2">
                {m.user_name}
                {m.is_owner && <b className="ml-1 text-navy">개설자</b>}
              </span>
            )}
            <div className={`flex items-end gap-1.5 ${m.is_mine ? 'flex-row-reverse' : ''}`}>
              <p
                className={`max-w-[75vw] whitespace-pre-wrap break-words rounded-2xl px-3.5 py-2 text-sm sm:max-w-md ${
                  m.is_mine ? 'bg-navy text-white' : 'bg-home-bg'
                }`}
              >
                {m.body}
              </p>
              <time className="shrink-0 text-[11px] text-ink-2" dateTime={m.created_at}>
                {asUtc(m.created_at).toLocaleTimeString('ko-KR', {
                  hour: '2-digit',
                  minute: '2-digit',
                })}
              </time>
            </div>
          </div>
        ))}
      </div>
      {(error || send.error) && (
        <div className="px-5 pb-2">
          <ErrorText error={(send.error ?? error) as Error} />
        </div>
      )}
      <form onSubmit={submit} className="flex gap-2 border-t border-home-line p-3">
        <label htmlFor="chat-input" className="sr-only">
          메시지
        </label>
        <textarea
          id="chat-input"
          rows={1}
          maxLength={1000}
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) submit(e)
          }}
          placeholder="메시지 입력"
          title="Enter 보내기 · Shift+Enter 줄바꿈"
          className="min-h-11 flex-1 resize-none rounded-xl border border-home-line px-3 py-2.5 text-sm focus-visible:outline-2 focus-visible:outline-navy"
        />
        <button
          type="submit"
          disabled={!draft.trim() || send.isPending}
          aria-label="보내기"
          className="flex size-11 shrink-0 items-center justify-center rounded-full bg-navy text-white disabled:opacity-40"
        >
          <Send size={18} />
        </button>
      </form>
    </section>
  )
}

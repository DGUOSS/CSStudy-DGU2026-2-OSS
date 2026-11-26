import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { api, unwrap } from '@/api/client'
import { Button } from '@/components/ui/button'

const source = 'https://www.dongguk.edu/article/HAKSANOTICE/list'

export function NoticesPanel() {
  const [selected, setSelected] = useState<number | null>(null)
  const [expanded, setExpanded] = useState(false)
  const [input, setInput] = useState('')
  const [query, setQuery] = useState('')
  const [page, setPage] = useState(1)
  const changeSearch = (value: string) => {
    setQuery(value.trim())
    setPage(1)
    setSelected(null)
    setExpanded(false)
  }
  const changePage = (value: number) => {
    setPage(value)
    setSelected(null)
    setExpanded(false)
  }
  const sourceUrl = `${source}?${new URLSearchParams({ searchCondition: 'TA.SUBJECT||TA.CONTENT', searchKeyword: query, pageIndex: String(page) })}`
  const notices = useQuery({ queryKey: ['academic-notices', query, page], queryFn: () => unwrap(api.GET('/api/v1/notices', { params: { query: { q: query, page } } })), staleTime: 600000, retry: 1 })
  const total = notices.data?.total ?? 0
  const items = [...(notices.data?.items ?? [])].sort((a, b) => b.date.localeCompare(a.date) || b.id - a.id)
  return <section className="rounded-xl border bg-card p-5" aria-labelledby="notices-heading">
    <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
      <h2 id="notices-heading" className="text-lg font-semibold">학사공지</h2>
      <a href={sourceUrl} target="_blank" rel="noopener noreferrer" className="text-sm text-primary hover:underline">학교 공지 전체보기 ↗</a>
    </div>
    <form className="mb-3 flex flex-wrap gap-2" role="search" onSubmit={event => { event.preventDefault(); changeSearch(input) }}>
      <label htmlFor="notice-search" className="sr-only">학사공지 제목·본문 검색</label>
      <input id="notice-search" type="search" value={input} onChange={event => setInput(event.target.value)} maxLength={100} placeholder="검색어 입력 (예: 장학금, 졸업, 계절학기)" className="min-w-0 flex-1 rounded-md border bg-background px-3 py-2 text-sm" />
      <Button type="submit" size="sm">검색</Button>
      {query && <Button type="button" variant="outline" size="sm" onClick={() => { setInput(''); changeSearch('') }}>초기화</Button>}
    </form>
    <p className="mb-2 text-xs text-muted-foreground">학교 게시판 전체의 제목·본문을 검색합니다.</p>
    {query && notices.data && <p role="status" className="mb-2 text-sm">“{notices.data.query}” 검색 결과 {total}건</p>}
    {notices.data && items.length === 0 && <p role="status" className="py-4 text-sm text-muted-foreground">검색 결과가 없습니다. 다른 키워드로 검색해 보세요.</p>}
    {notices.isPending && <p role="status" className="text-sm">공지를 불러오는 중입니다.</p>}
    {notices.isError && <div role="status" className="text-sm"><p>공지를 불러오지 못했어요. 학교 공지 전체보기에서 확인해 주세요.</p><Button variant="outline" size="sm" onClick={() => notices.refetch()}>다시 시도</Button></div>}
    {notices.data?.stale && <p role="status" className="mb-2 text-sm text-[#8a6212]">학교 사이트 연결이 지연되어 이전 공지를 표시합니다.</p>}
    <ul className="divide-y">{(query || expanded ? items : items.slice(0, 5)).map(item => <li key={item.id} className="py-3">
      <button className="w-full rounded text-left focus-visible:outline-2 focus-visible:outline-primary" aria-expanded={selected === item.id} aria-controls={`notice-${item.id}`} onClick={() => setSelected(selected === item.id ? null : item.id)}>
        <div className="mb-1 flex flex-wrap gap-2 text-xs text-muted-foreground">{item.pinned && <span className="font-semibold text-primary">중요</span>}<span>{item.category}</span><span>{item.date}</span></div>
        <span className="text-sm font-medium hover:text-primary">{item.title}</span>
      </button>
      <div id={`notice-${item.id}`} hidden={selected !== item.id}>{selected === item.id && <NoticeBody id={item.id} url={item.url} query={query} page={page} />}</div>
    </li>)}</ul>
    {!query && items.length > 5 && <Button className="mt-2" variant="ghost" size="sm" onClick={() => setExpanded(!expanded)}>{expanded ? '접기' : `공지 더 보기 (${items.length}건)`}</Button>}
    {notices.data && total > 10 && <nav aria-label="공지 페이지" className="mt-3 flex items-center justify-center gap-3">
      <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => changePage(page - 1)}>이전</Button>
      <span className="text-sm">{page} / {Math.ceil(total / 10)}</span>
      <Button variant="outline" size="sm" disabled={page >= Math.ceil(total / 10)} onClick={() => changePage(page + 1)}>다음</Button>
    </nav>}
    <p className="mt-3 text-xs text-muted-foreground">출처: 동국대학교 · 업데이트 반영에 최대 10분 소요{notices.data && ` · 확인 ${new Date(notices.data.fetched_at).toLocaleString('ko-KR')}`}</p>
  </section>
}

function NoticeBody({ id, url, query, page }: { id: number; url: string; query: string; page: number }) {
  const detail = useQuery({ queryKey: ['academic-notice-detail', id, query, page], queryFn: () => unwrap(api.GET('/api/v1/notices/{notice_id}', { params: { path: { notice_id: id }, query: { q: query, page } } })), staleTime: 600000, retry: 1 })
  return <div className="mt-3 rounded-lg bg-muted/40 p-4">
    {detail.isPending && <p role="status" className="text-sm">본문을 불러오는 중입니다.</p>}
    {detail.isError && <p role="status" className="text-sm">본문을 불러오지 못했어요. 아래 원문 링크를 이용해 주세요.</p>}
    {detail.data?.stale && <p className="mb-2 text-sm text-[#8a6212]">이전에 가져온 본문입니다. 최신 내용은 원문을 확인해 주세요.</p>}
    {detail.data && <p className="max-h-96 overflow-y-auto whitespace-pre-wrap break-words text-sm leading-relaxed">{detail.data.text || '텍스트가 없는 공지입니다. 원문에서 확인해 주세요.'}</p>}
    <p className="mt-3 text-xs text-muted-foreground">이미지·표의 원래 형태와 첨부파일은 학교 원문에서 확인해 주세요.</p>
    <a href={url} target="_blank" rel="noopener noreferrer" className="mt-2 inline-block text-sm text-primary hover:underline">원문 및 첨부파일 보기 ↗</a>
  </div>
}

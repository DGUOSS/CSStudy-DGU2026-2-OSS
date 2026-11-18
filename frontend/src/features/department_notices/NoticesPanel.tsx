import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { Star, Settings2, ExternalLink } from 'lucide-react'
import { api, unwrap, type Schemas } from '@/api/client'
import { Button } from '@/components/ui/button'
import { useAuth } from '@/features/auth/useAuth'
import { NoticeDialog } from './NoticeDialog'

type Item = Schemas['Item']

export function NoticesPanel() {
  const { user } = useAuth()
  const qc = useQueryClient()
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState<string[]>([])
  const [departmentSearch, setDepartmentSearch] = useState('')
  const [source, setSource] = useState('all')
  const [input, setInput] = useState('')
  const [query, setQuery] = useState('')
  const [page, setPage] = useState(1)
  const [selected, setSelected] = useState<Item | null>(null)
  const [expanded, setExpanded] = useState(false)
  const catalog = useQuery({ queryKey: ['notice-catalog'], queryFn: () => unwrap(api.GET('/api/v1/department-notices/catalog')), staleTime: Infinity })
  const preferenceKey = ['notice-preferences', user?.id]
  const preferences = useQuery({ queryKey: preferenceKey, queryFn: () => unwrap(api.GET('/api/v1/department-notices/preferences')), enabled: !!user })
  const favoriteIds = preferences.data?.department_ids ?? []
  const departments = catalog.data?.departments ?? []
  const favorites = favoriteIds.flatMap(id => departments.filter(d => d.id === id))
  const notices = useQuery({
    queryKey: ['department-notice-feed', user?.id, favoriteIds, source, query, page],
    queryFn: () => unwrap(api.GET('/api/v1/department-notices/feed', { params: { query: { source, q: query, page } } })),
    enabled: !!user && preferences.isSuccess,
    staleTime: 600000, retry: 1,
  })
  const resetView = () => { setPage(1); setSelected(null); setExpanded(false) }
  const save = useMutation({
    mutationFn: () => unwrap(api.PUT('/api/v1/department-notices/preferences', { body: { department_ids: draft } })),
    onSuccess: data => {
      qc.setQueryData(preferenceKey, data)
      qc.invalidateQueries({ queryKey: ['department-notice-feed', user?.id] })
      setSource('all'); resetView(); setEditing(false)
    },
  })
  const items = notices.data?.items ?? []
  const board = source === 'all' ? undefined : notices.data?.boards[0]
  const shown = expanded ? items : items.slice(0, 5)
  const matchedDepartments = departments.filter(d => `${d.name} ${d.college}`.toLowerCase().includes(departmentSearch.trim().toLowerCase()))
  const colleges = [...new Set(matchedDepartments.map(d => d.college))]
  const maxFavorites = catalog.data?.max_favorites ?? 8
  const currentName = source === 'all' ? '전체' : source === 'school' ? '학교 공통' : favorites.find(d => d.source_ids.includes(source))?.name ?? '학과'
  const changeSource = (id: string) => { setSource(id); resetView() }
  return <section className="min-w-0 rounded-2xl border border-home-line bg-white p-5 [--primary:var(--color-navy)] [--ring:var(--color-navy)] [&_button]:rounded-full [&_button]:font-bold [&_input]:accent-navy" aria-labelledby="notices-heading">
    <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
      <div><h2 id="notices-heading" className="text-xl font-bold">우리 학교 공지</h2><p className="text-sm text-ink-2">학교·관심 학과의 최신 공지를 모았어요.</p></div>
      <Button variant="outline" size="sm" disabled={!preferences.data || !catalog.data} onClick={() => { save.reset(); setDraft([...favoriteIds]); setDepartmentSearch(''); setEditing(true) }}><Settings2 className="size-4" />관심 학과 설정</Button>
    </div>
    {(preferences.isError || catalog.isError) && <div role="alert" className="mb-3 text-sm text-destructive">설정을 불러오지 못했어요. <button className="underline" onClick={() => { preferences.refetch(); catalog.refetch() }}>다시 시도</button></div>}
    {editing && <NoticeDialog title="관심 학과 설정" onClose={() => setEditing(false)} busy={save.isPending}>
      <div className="shrink-0 px-5 pt-4">
      <p className="mt-1 text-xs text-ink-2">최대 {maxFavorites}개까지 선택할 수 있어요.</p>
      <label className="sr-only" htmlFor="department-search">학과 또는 단과대학 검색</label>
      <input id="department-search" value={departmentSearch} onChange={e => setDepartmentSearch(e.target.value)} placeholder="학과 또는 단과대학 검색" className="my-3 w-full h-11 rounded-xl border border-home-line bg-white px-3 text-[15px] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-navy/40" />
      <div className="mb-3 flex max-h-24 flex-wrap gap-2 overflow-y-auto" aria-label="선택한 학과">
        {draft.map(id => <button key={id} type="button" disabled={save.isPending} onClick={() => setDraft(draft.filter(value => value !== id))} aria-label={`${departments.find(d => d.id === id)?.name} 선택 해제`} className="rounded-full bg-navy-tint px-3 py-1 text-xs font-bold text-navy">{departments.find(d => d.id === id)?.name} ×</button>)}
        {!draft.length && <span className="text-sm text-ink-2">아래에서 관심 학과를 골라 주세요.</span>}
      </div></div>
      <div className="min-h-0 flex-1 overflow-y-auto px-5 pb-3">
        {colleges.map(college => <fieldset key={college} className="mb-3"><legend className="mb-2 text-sm font-semibold">{college}</legend><div className="grid gap-2 sm:grid-cols-2">
          {matchedDepartments.filter(d => d.college === college).map(d => {
            const checked = draft.includes(d.id)
            const unavailable = !d.source_ids.length
            return <button key={d.id} type="button" aria-pressed={checked}
              disabled={save.isPending || unavailable || (!checked && draft.length >= maxFavorites)}
              onClick={() => setDraft(checked ? draft.filter(id => id !== d.id) : [...draft, d.id])}
              className={`flex min-h-11 w-full cursor-pointer items-center gap-3 rounded-xl border p-3 text-left text-sm transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-navy disabled:cursor-not-allowed disabled:opacity-50 ${checked ? 'border-navy bg-navy-tint' : 'border-home-line bg-white hover:bg-home-bg'}`}>
              <Star aria-hidden="true" className={`size-5 shrink-0 ${checked ? 'fill-gold text-gold' : 'text-ink-2'}`} />
              <span>{d.name}{unavailable && <span className="block text-xs">{d.note}</span>}</span>
            </button>
          })}
        </div></fieldset>)}
        {!matchedDepartments.length && <p className="py-4 text-sm">찾는 학과가 없습니다.</p>}
      </div>
      <div className="shrink-0 border-t border-home-line bg-white p-5"><div className="flex items-center gap-2"><span className="mr-auto text-sm">{draft.length} / {maxFavorites}개 선택</span><Button variant="outline" size="sm" disabled={save.isPending} onClick={() => setEditing(false)}>취소</Button><Button size="sm" disabled={save.isPending} onClick={() => save.mutate()}>{save.isPending ? '저장 중…' : '저장'}</Button></div>
      {save.isError && <p role="alert" className="mt-2 text-sm text-destructive">저장하지 못했어요. 다시 시도해 주세요.</p>}
    </div></NoticeDialog>}
    {preferences.isSuccess && !favoriteIds.length && !editing && <p className="mb-3 rounded-xl bg-home-bg p-3 text-sm text-ink-2">관심 학과를 추가하면 학과 공지도 함께 볼 수 있어요.</p>}
    <div className="mb-4 flex min-w-0 gap-2 overflow-x-auto pb-2 [&_button]:shrink-0" role="group" aria-label="공지 출처 선택">
      {[{id:'all',name:'전체'}, {id:'school',name:'학교 공통'}, ...favorites.map(d => ({id:d.source_ids[0],name:d.name}))].map(tab => <Button key={tab.id} size="sm" variant={source === tab.id ? 'default' : 'outline'} aria-pressed={source === tab.id} onClick={() => changeSource(tab.id)}>{tab.name}</Button>)}
    </div>
    <form role="search" className="mb-2 flex flex-wrap gap-2" onSubmit={e => { e.preventDefault(); setQuery(input.trim()); resetView() }}>
      <label className="sr-only" htmlFor="notice-search">공지 제목·본문 검색</label>
      <input id="notice-search" type="search" maxLength={100} value={input} onChange={e => setInput(e.target.value)} placeholder={`${currentName} 공지 검색`} className="min-w-0 flex-1 h-11 rounded-xl border border-home-line bg-white px-3 text-[15px] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-navy/40" />
      <Button type="submit" className="h-11 px-5">검색</Button>
      {query && <Button type="button" variant="outline" size="sm" onClick={() => { setInput(''); setQuery(''); resetView() }}>초기화</Button>}
    </form>
    <p className="mb-3 text-xs text-ink-2">{source === 'all' ? '게시판별 첫 페이지를 모았어요. 이전 공지는 각 탭에서 확인하세요.' : `${currentName} 게시판 전체에서 제목·본문을 검색합니다.`}</p>
    {preferences.isPending || (notices.isPending && preferences.isSuccess) ? <p role="status" className="py-3 text-sm">공지를 불러오는 중입니다.</p> : null}
    {notices.isError && <p role="alert" className="text-sm text-destructive">공지를 불러오지 못했어요. <button className="underline" onClick={() => notices.refetch()}>다시 시도</button></p>}
    {!!notices.data?.failed_sources.length && <div role="status" className="mb-3 rounded-md bg-amber-50 p-3 text-sm text-amber-900">일부 게시판 연결이 지연되고 있어요. 원문에서 확인해 주세요.<ul>{notices.data.failed_sources.map(s => <li key={s.id}><a href={s.url} target="_blank" rel="noopener noreferrer" className="underline">{s.name} ↗</a></li>)}</ul><button className="mt-1 underline" onClick={() => notices.refetch()}>다시 시도</button></div>}
    {notices.data?.boards.some(b => b.stale) && <p role="status" className="mb-2 text-sm text-amber-700">일부 게시판은 이전에 가져온 목록입니다. 최신 내용은 원문을 확인하세요.</p>}
    {board && <div className="mb-2 flex flex-wrap justify-between gap-2 text-xs text-ink-2"><span>{query ? `“${query}” 검색 결과 ` : ''}{board.total}건 · {page}쪽</span><a href={board.source_url} target="_blank" rel="noopener noreferrer" className="text-primary hover:underline">게시판 원문 ↗</a></div>}
    {notices.isSuccess && !items.length && !notices.data.failed_sources.length && <p role="status" className="py-5 text-sm text-ink-2">{query ? '검색 결과가 없습니다. 다른 키워드로 검색해 보세요.' : '표시할 공지가 없습니다.'}</p>}
    <ul className="divide-y divide-home-line">{shown.map(item => {
      const key = `${item.source_id}-${item.id}`
      return <li key={key}><button type="button" className="w-full px-2 py-4 text-left transition-colors hover:bg-home-bg focus-visible:outline-2 focus-visible:outline-navy" aria-haspopup="dialog" onClick={() => setSelected(item)}>
        <div className="mb-2 flex flex-wrap items-center gap-2 text-xs text-ink-2"><span className="rounded-full bg-navy-tint px-2.5 py-1 font-bold text-navy">{item.source_name}</span>{item.pinned && <span className="rounded-full bg-gold-soft px-2.5 py-1 font-bold text-navy">중요</span>}<span className="ml-auto">{item.date || '작성일은 원문 확인'}</span></div>
        <span className="line-clamp-2 break-words text-[15px] font-bold">{item.title}</span>
      </button></li>
    })}</ul>
    {selected && <NoticeDialog title={selected.title} onClose={() => setSelected(null)}>
      <div className="min-h-0 overflow-y-auto p-5"><p className="text-sm text-ink-2">{selected.source_name} · {selected.date || '작성일은 원문 확인'}</p><NoticeBody item={selected} query={query} page={page} /></div>
    </NoticeDialog>}
    {items.length > 5 && <Button variant="ghost" size="sm" onClick={() => setExpanded(!expanded)}>{expanded ? '접기' : `더 보기 (${items.length}건)`}</Button>}
    {board && (page > 1 || board.has_next) && <nav aria-label="공지 페이지" className="mt-3 flex items-center justify-center gap-3"><Button size="sm" variant="outline" disabled={page <= 1} onClick={() => { setPage(page-1); setSelected(null); setExpanded(false) }}>이전</Button><span className="text-sm">{page}쪽</span><Button size="sm" variant="outline" disabled={!board.has_next} onClick={() => { setPage(page+1); setSelected(null); setExpanded(false) }}>다음</Button></nav>}
    <p className="mt-3 text-xs text-ink-2">출처: 동국대학교 및 학과 홈페이지 · 업데이트 반영에 최대 10분 소요</p>
  </section>
}

function NoticeBody({ item, query, page }: { item: Item; query: string; page: number }) {
  const { user } = useAuth()
  const detail = useQuery({
    queryKey: ['department-notice-detail', user?.id, item.source_id, item.id, query, page],
    queryFn: () => unwrap(api.GET('/api/v1/department-notices/sources/{source_id}/items/{notice_id}', { params: { path: { source_id: item.source_id, notice_id: item.id }, query: { q: query, page } } })),
    staleTime: 600000, retry: 1,
  })
  return <div className="mt-3 rounded-xl bg-home-bg p-4">
    {detail.isPending && <p role="status" className="text-sm">본문을 불러오는 중입니다.</p>}
    {detail.isError && <p role="status" className="text-sm">본문을 불러오지 못했어요. 아래 원문을 이용해 주세요.</p>}
    {detail.data?.stale && <p className="mb-2 text-sm text-amber-700">이전에 가져온 본문입니다.</p>}
    {detail.data && <p className="whitespace-pre-wrap break-words text-sm leading-relaxed">{detail.data.text || '텍스트가 없는 공지입니다. 원문에서 확인해 주세요.'}</p>}
    <p className="mt-3 text-xs text-ink-2">이미지·표의 원래 형태와 첨부파일은 원문에서 확인해 주세요.</p>
    <a href={item.url} target="_blank" rel="noopener noreferrer" className="mt-2 inline-flex items-center gap-1 text-sm text-primary hover:underline">원문 및 첨부파일 보기<ExternalLink className="size-3" /></a>
  </div>
}

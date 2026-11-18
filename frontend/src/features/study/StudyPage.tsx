import { ChevronRight, Download, Lock, Search } from 'lucide-react'
import { Link } from 'react-router'
import { api, unwrap } from '@/api/client'
import { Empty, ErrorText, Loading } from '@/components/States'
import { RequestWithFiles } from '@/features/course_requests/RequestWithFiles'
import { useMyCourses } from '@/features/enrollments/queries'
import { AppShell } from '@/features/home/AppShell'

/** 학습(/study): 내 과목과 그 강좌(교수) 목록, 과목 추가 */
export function StudyPage() {
  return (
    <AppShell>
      <StudyContent />
    </AppShell>
  )
}

function StudyContent() {
  const mine = useMyCourses()
  const courses = mine.data?.courses ?? []

  // 내 강좌를 과목명으로 묶는다
  const groups = new Map<string, { code: string | null; items: typeof courses }>()
  for (const c of courses) {
    const g = groups.get(c.subject_name) ?? { code: c.sbj_no, items: [] }
    g.items.push(c)
    groups.set(c.subject_name, g)
  }

  return (
    <>
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold">학습</h1>
          <p className="mt-1 text-sm text-ink-2">
            내 강좌에서 교수님 강좌를 골라 시험 대비 퀴즈를 풀어 보세요.
          </p>
        </div>
        <div className="flex shrink-0 gap-2">
          <Link
            to="/study/import"
            className="inline-flex h-11 items-center gap-2 rounded-full border border-home-line bg-white px-5 text-[15px] font-bold text-navy hover:bg-navy-tint"
          >
            <Download size={16} />
            수강 기록 가져오기
          </Link>
          <Link
            to="/study/find"
            className="inline-flex h-11 items-center gap-2 rounded-full bg-navy px-5 text-[15px] font-bold text-white hover:bg-navy-deep"
          >
            <Search size={16} />
            강좌 찾기
          </Link>
        </div>
      </div>

      {mine.isPending ? (
        <Loading />
      ) : groups.size === 0 ? (
        <Empty>
          아직 내 강좌가 없어요. &lsquo;수강 기록 가져오기&rsquo;로 엔드림스 기록을 가져오거나
          &lsquo;강좌 찾기&rsquo;를 이용해 주세요.
        </Empty>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2">
          {[...groups.entries()].map(([name, g]) => (
            <section
              key={name}
              className="flex flex-col gap-3 rounded-2xl border border-home-line bg-white p-5"
            >
              <div>
                <h2 className="text-lg font-bold">{name}</h2>
                {g.code && <p className="text-sm text-ink-2">{g.code}</p>}
              </div>
              <ul className="flex flex-col gap-2">
                {g.items.map((c) => (
                  <li key={c.course_id}>
                    <Link
                      to={`/study/courses/${c.course_id}`}
                      className="flex items-center justify-between rounded-xl bg-navy-tint px-4 py-3 hover:bg-tone-blue"
                    >
                      <span>
                        <span className="block font-bold text-navy">{c.professor_name} 교수님</span>
                        <span className="block text-xs text-ink-2">
                          {c.status === 'current' ? '수강 중' : '수강함'}
                          {c.terms.length > 0 && ` · ${c.terms.join(', ')}`}
                        </span>
                      </span>
                      <ChevronRight size={18} className="text-navy" />
                    </Link>
                  </li>
                ))}
              </ul>
            </section>
          ))}
        </div>
      )}
      {(mine.data?.public?.length ?? 0) > 0 && (
        <section className="flex flex-col gap-3">
          <div>
            <h2 className="text-xl font-bold">공용 강좌</h2>
            <p className="text-sm text-ink-2">수강 기록이 없어도 누구나 들어갈 수 있어요.</p>
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            {mine.data?.public?.map((c) => (
              <Link
                key={c.course_id}
                to={`/study/courses/${c.course_id}`}
                className="flex items-center justify-between rounded-2xl border border-home-line bg-white px-5 py-4 hover:bg-navy-tint"
              >
                <span>
                  <span className="block font-bold">{c.subject_name}</span>
                  <span className="block text-sm text-ink-2">{c.professor_name} 교수님 · 공용</span>
                </span>
                <ChevronRight size={18} className="text-navy" />
              </Link>
            ))}
          </div>
        </section>
      )}

      {(mine.data?.waiting.length ?? 0) > 0 && (
        <section className="flex flex-col gap-3">
          <div>
            <h2 className="text-xl font-bold">아직 열리지 않은 수업</h2>
            <p className="text-sm text-ink-2">
              동국스터디에 아직 강좌가 없는 수업이에요. 요청할 때 교안 PDF를 같이 올리면 더 빨리
              열려요(선택).
            </p>
          </div>
          <ul className="flex flex-col divide-y divide-home-line rounded-2xl border border-home-line bg-white">
            {mine.data?.waiting.map((w) => (
              <li key={w.enrollment_id} className="flex flex-wrap items-center gap-3 px-5 py-4">
                <Lock size={16} className="text-ink-2" />
                <div className="min-w-0 flex-1">
                  <div className="font-bold">
                    {w.sbj_nm}
                    {w.professor_name && (
                      <span className="font-normal text-ink-2"> · {w.professor_name}</span>
                    )}
                  </div>
                  <div className="text-xs text-ink-2">
                    {w.sbj_no} · {w.term} · {w.status === 'current' ? '수강 중' : '수강함'}
                  </div>
                </div>
                {w.request === 'mine' ? (
                  <span className="inline-flex h-9 items-center rounded-full bg-gold-soft px-4 text-sm font-bold text-navy">
                    요청함{w.request_count > 1 && ` (${w.request_count}명)`}
                  </span>
                ) : w.professor_name ? (
                  <RequestWithFiles
                    label={`열어 달라고 요청${w.request_count > 0 ? ` (${w.request_count}명 대기)` : ''}`}
                    create={async (note) =>
                      (
                        await unwrap(
                          api.POST('/api/v1/me/enrollments/{enrollment_id}/request', {
                            params: { path: { enrollment_id: w.enrollment_id } },
                            body: { note },
                          }),
                        )
                      ).request_id
                    }
                  />
                ) : (
                  <Link
                    to={`/requests/new?subject=${encodeURIComponent(w.sbj_nm)}&code=${encodeURIComponent(w.sbj_no)}&semester=${encodeURIComponent(w.term)}`}
                    title="교수 정보가 없어 교수님 이름을 직접 적어 요청해요"
                    className="inline-flex h-9 items-center rounded-full border border-home-line px-4 text-sm font-bold text-navy hover:bg-navy-tint"
                  >
                    직접 요청
                  </Link>
                )}
              </li>
            ))}
          </ul>
        </section>
      )}
      <p className="text-sm text-ink-2">
        찾는 강좌가 없나요?{' '}
        <Link to="/requests/new" className="font-bold text-navy hover:underline">
          개설 요청하기
        </Link>
      </p>
      <ErrorText error={mine.error} />
    </>
  )
}

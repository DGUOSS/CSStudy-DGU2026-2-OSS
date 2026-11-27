import { ChevronRight, Download, Lock, Search } from 'lucide-react'
import { Link } from 'react-router'
import { api, unwrap } from '@/api/client'
import { Empty, ErrorText, Loading } from '@/components/States'
import { RequestWithFiles } from '@/features/course_requests/RequestWithFiles'
import { useMyCourses } from '@/features/enrollments/queries'
import { AppShell } from '@/features/home/AppShell'
import { subjectIcon } from './subjectIcon'

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

  // 강좌 하나 = 가로로 긴 한 줄. 수강 중인 강좌를 먼저, 같은 과목은 붙여 둔다
  const rows = [...courses].sort(
    (a, b) =>
      Number(b.status === 'current') - Number(a.status === 'current') ||
      a.subject_name.localeCompare(b.subject_name, 'ko'),
  )

  return (
    <>
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold">학습</h1>
          <p className="mt-1 text-sm text-ink-2">
            내 강좌에서 교수님 강좌를 골라 시험 대비 퀴즈를 풀어 보세요.
          </p>
        </div>
        <div className="flex shrink-0 flex-wrap gap-2">
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
      ) : rows.length === 0 ? (
        <Empty>
          아직 내 강좌가 없어요. &lsquo;수강 기록 가져오기&rsquo;로 엔드림스 기록을 가져오거나
          &lsquo;강좌 찾기&rsquo;를 이용해 주세요.
        </Empty>
      ) : (
        <ul className="overflow-hidden rounded-2xl border border-home-line bg-white">
          {rows.map((c) => {
            const { Icon, tone } = subjectIcon(c.subject_name, c.subject_id)
            return (
            <li key={c.course_id} className="border-b border-home-line last:border-b-0">
              <Link
                to={`/study/courses/${c.course_id}`}
                className="flex items-center gap-4 px-5 py-4 hover:bg-home-bg"
              >
                <span className={`flex size-10 shrink-0 items-center justify-center rounded-xl ${tone}`}>
                  <Icon size={20} strokeWidth={1.8} aria-hidden="true" />
                </span>
                <span className="flex min-w-0 flex-1 flex-wrap items-baseline gap-x-3 gap-y-0.5">
                  <span className="truncate text-[17px] font-bold">{c.subject_name}</span>
                  <span className="text-[15px] text-ink-2">{c.professor_name} 교수님</span>
                  {c.sbj_no && <span className="text-[13px] text-ink-2">{c.sbj_no}</span>}
                </span>
                <span className="hidden shrink-0 text-[13px] text-ink-2 sm:block">
                  {c.terms.join(', ')}
                </span>
                <span
                  className={
                    c.status === 'current'
                      ? 'shrink-0 rounded-full bg-tone-blue px-2.5 py-1 text-xs font-bold text-navy'
                      : 'shrink-0 rounded-full bg-home-bg px-2.5 py-1 text-xs font-bold text-ink-2'
                  }
                >
                  {c.status === 'current' ? '수강 중' : '수강함'}
                </span>
                <ChevronRight size={18} className="shrink-0 text-ink-2" aria-hidden="true" />
              </Link>
            </li>
            )
          })}
        </ul>
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
                    label={`개설 요청${w.request_count > 0 ? ` (${w.request_count}명 대기)` : ''}`}
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

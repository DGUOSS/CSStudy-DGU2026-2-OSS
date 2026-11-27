import { Link, isRouteErrorResponse, useRouteError } from 'react-router'
import { DESIGN_ON } from '@/lib/design'
import { cn } from '@/lib/utils'

// 새 디자인이면 회색 바탕·남색 버튼 (오류 화면은 틀 밖이라 design-scope를 직접 붙인다)
const WRAP = cn(
  'mx-auto flex min-h-[50svh] max-w-md flex-col items-center justify-center gap-3 px-4 text-center',
  DESIGN_ON && 'design-scope min-h-svh max-w-none bg-home-bg',
)

/** 없는 주소이거나 화면을 그리다 오류가 났을 때. 개발자용 기본 오류 화면 대신 보여 준다. */
export function NotFound({ title = '페이지를 찾을 수 없어요' }: { title?: string }) {
  return (
    <div className={WRAP}>
      <p className="text-5xl font-bold text-muted-foreground/40" aria-hidden="true">
        404
      </p>
      <h1 className="text-xl font-bold">{title}</h1>
      <p className="text-sm text-muted-foreground">
        주소가 바뀌었거나 잘못 입력됐을 수 있어요. 홈에서 다시 찾아 주세요.
      </p>
      <Link
        to={DESIGN_ON ? '/home' : '/'}
        className="mt-2 inline-flex h-11 items-center rounded-full bg-primary px-6 text-[15px] font-bold text-primary-foreground"
      >
        홈으로
      </Link>
    </div>
  )
}

export function RouteError() {
  const error = useRouteError()
  if (isRouteErrorResponse(error) && error.status === 404) return <NotFound />
  return (
    <div className={WRAP}>
      <h1 className="text-xl font-bold">화면을 여는 중 문제가 생겼어요</h1>
      <p className="text-sm text-muted-foreground">
        새로고침해 보고, 계속되면 홈에서 다시 들어와 주세요.
      </p>
      <div className="mt-2 flex gap-2">
        <button
          type="button"
          onClick={() => window.location.reload()}
          className="inline-flex h-11 cursor-pointer items-center rounded-full border bg-white px-6 text-[15px] font-bold"
        >
          새로고침
        </button>
        <Link
          to={DESIGN_ON ? '/home' : '/'}
          className="inline-flex h-11 items-center rounded-full bg-primary px-6 text-[15px] font-bold text-primary-foreground"
        >
          홈으로
        </Link>
      </div>
    </div>
  )
}

import { Link, isRouteErrorResponse, useRouteError } from 'react-router'

/** 없는 주소이거나 화면을 그리다 오류가 났을 때. 개발자용 기본 오류 화면 대신 보여 준다. */
export function NotFound({ title = '페이지를 찾을 수 없어요' }: { title?: string }) {
  return (
    <div className="mx-auto flex min-h-[50svh] max-w-md flex-col items-center justify-center gap-3 px-4 text-center">
      <p className="text-5xl font-bold text-muted-foreground/40" aria-hidden="true">
        404
      </p>
      <h1 className="text-xl font-bold">{title}</h1>
      <p className="text-sm text-muted-foreground">
        주소가 바뀌었거나 잘못 입력됐을 수 있어요. 홈에서 다시 찾아 주세요.
      </p>
      <Link
        to="/"
        className="mt-2 rounded-full bg-primary px-5 py-2 text-sm font-semibold text-primary-foreground"
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
    <div className="mx-auto flex min-h-[50svh] max-w-md flex-col items-center justify-center gap-3 px-4 text-center">
      <h1 className="text-xl font-bold">화면을 여는 중 문제가 생겼어요</h1>
      <p className="text-sm text-muted-foreground">
        새로고침해 보고, 계속되면 홈에서 다시 들어와 주세요.
      </p>
      <div className="mt-2 flex gap-2">
        <button
          type="button"
          onClick={() => window.location.reload()}
          className="rounded-full border px-5 py-2 text-sm font-semibold"
        >
          새로고침
        </button>
        <Link
          to="/"
          className="rounded-full bg-primary px-5 py-2 text-sm font-semibold text-primary-foreground"
        >
          홈으로
        </Link>
      </div>
    </div>
  )
}

/**
 * 백엔드 호출은 전부 이 파일의 api를 쓴다.
 * 타입(schema.d.ts)은 자동 생성 파일이다. 직접 고치지 말고 `pnpm gen:api`로 다시 만든다.
 */
import createClient from 'openapi-fetch'
import type { components, paths } from './schema'

export const api = createClient<paths>({ baseUrl: '' })

export type Schemas = components['schemas']

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

function messageOf(error: unknown): string {
  const detail = (error as { detail?: unknown } | undefined)?.detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail) && detail[0]?.msg) return '입력값을 확인해 주세요'
  return '요청에 실패했습니다'
}

/** openapi-fetch 결과에서 data를 꺼내고, 실패면 ApiError를 던진다. */
export async function unwrap<T>(
  promise: Promise<{ data?: T; error?: unknown; response: Response }>,
): Promise<T> {
  const { data, error, response } = await promise
  if (!response.ok) throw new ApiError(response.status, messageOf(error))
  return data as T
}

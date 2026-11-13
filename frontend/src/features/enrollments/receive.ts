import { MESSAGE_TYPE, type NdrimsPayload } from './bookmarklet'

/**
 * 엔드림스 창의 [동국스터디로 보내기]가 새 탭으로 여는 주소: /ndrims#<기록 JSON>
 * 창 연결(window.opener)이 끊긴 경우에 쓴다. # 뒤는 서버로 가지 않는다.
 * 로그인 화면을 거쳐도 잃지 않도록 앱이 뜨기 전에 sessionStorage로 옮겨 둔다.
 */
const KEY = 'dgu-study-ndrims'

export function stashNdrimsHash() {
  if (location.pathname !== '/ndrims' || location.hash.length < 2) return
  try {
    sessionStorage.setItem(KEY, decodeURIComponent(location.hash.slice(1)))
  } catch {
    /* 저장 못 하면 받기 화면에서 안내 */
  }
  history.replaceState(null, '', location.pathname)
}

export function takeStashed(): NdrimsPayload | null {
  try {
    const raw = sessionStorage.getItem(KEY)
    sessionStorage.removeItem(KEY)
    const d = raw ? (JSON.parse(raw) as NdrimsPayload) : null
    return d?.type === MESSAGE_TYPE ? d : null
  } catch {
    return null
  }
}

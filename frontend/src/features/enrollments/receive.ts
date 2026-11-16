import { MESSAGE_TYPE } from './bookmarklet'

/**
 * 엔드림스 창의 [동국스터디로 보내기]가 창 연결이 끊긴 경우 새 탭으로 여는 주소: /ndrims#pull
 * 이 탭이 자기를 연 엔드림스 창(window.opener)에 기록을 달라고 하고, 받은 것을 확인 후 저장한다.
 * 로그인 화면을 거쳐도 잃지 않도록 앱이 뜨기 전에 표시를 sessionStorage로 옮겨 둔다.
 */
const KEY = 'dgu-study-ndrims-pull'

export function stashNdrimsHash() {
  if (location.pathname !== '/ndrims' || location.hash !== '#pull') return
  try {
    sessionStorage.setItem(KEY, '1')
  } catch {
    /* 저장 못 해도 이번 화면에서는 받는다 */
  }
  history.replaceState(null, '', location.pathname)
}

export function wantsPull(): boolean {
  try {
    return sessionStorage.getItem(KEY) === '1'
  } catch {
    return false
  }
}

export function donePull() {
  try {
    sessionStorage.removeItem(KEY)
  } catch {
    /* 무시 */
  }
}

export const PULL_TYPE = MESSAGE_TYPE + '-pull'

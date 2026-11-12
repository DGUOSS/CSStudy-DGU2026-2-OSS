/**
 * 엔드림스 창에서 누르는 즐겨찾기 버튼(북마클릿) 코드.
 *
 * 하는 일: 엔드림스 화면이 서버에서 받아 오는 데이터(JSON)를 옆에서 받아 적는다.
 * - 수강신청내역확인(EdcRegi170), 전체성적조회(EddRec050) → 수강 기록 (과목 찾는 칸만, 성적은 버림)
 * - 종합강의시간표조회(EdcLesn010) → 개설 목록 (관리자만 사이트에 저장됨)
 * 모은 것은 '동국스터디로 보내기'를 누르면 우리 사이트 창(window.opener)으로 넘긴다.
 * 비밀번호·쿠키는 건드리지 않고, 우리 서버는 엔드림스에 접속하지 않는다. 구조는 docs/NDRIMS.md.
 */

export const NDRIMS_URL: string = import.meta.env.VITE_NDRIMS_URL ?? 'https://ndrims.dongguk.edu/'
const extra = (import.meta.env.VITE_NDRIMS_EXTRA_ORIGINS ?? '')
  .split(',')
  .map((s: string) => s.trim())
  .filter(Boolean)
/** 사이트가 메시지를 받아 주는 엔드림스 주소들 */
export const NDRIMS_ORIGINS: string[] = ['https://ndrims.dongguk.edu', ...extra]

export const MESSAGE_TYPE = 'dgu-study-ndrims'

export type NdrimsPayload = {
  type: typeof MESSAGE_TYPE
  records: {
    year: string
    sem_cd: string
    sbj_no: string
    sbj_nm: string
    dvcls: string
    emp_nm?: string | null
  }[]
  catalog: Record<string, string | number | null>[]
}

// 엔드림스 창 안에서 실행되는 코드. 바깥 변수는 쓰지 않는다(문자열로 바뀌어 들어간다).
function inNdrims(SITE: string, HOSTS: string[], TYPE: string) {
  const w = window as unknown as { __dguStudy?: { show: () => void } }
  if (!HOSTS.some((h) => location.origin === h)) {
    alert('엔드림스(ndrims.dongguk.edu) 창에서 눌러 주세요.')
    return
  }
  if (w.__dguStudy) {
    w.__dguStudy.show()
    return
  }
  type Row = Record<string, unknown>
  const rec: Record<string, Row> = {}
  const cat: Record<string, Row> = {}
  const str = (v: unknown, n = 200) => (v == null ? null : String(v).slice(0, n))
  const num = (v: unknown) => (v == null || v === '' || isNaN(Number(v)) ? null : Number(v))
  const take = (url: string, text: string) => {
    if (!/\.do(\?|$)/.test(url)) return
    let rows: Row[]
    try {
      rows = (JSON.parse(text).dsMain || []) as Row[]
    } catch {
      return
    }
    if (/EdcRegi170\/doList/.test(url) || /EddRec050\/doList/.test(url)) {
      const grade = /EddRec050/.test(url)
      for (const x of rows) {
        const r = {
          year: str(grade ? x.YY : x.OPEN_YY, 4),
          sem_cd: str(grade ? x.SEM_CD : x.OPEN_SEM_CD, 20),
          sbj_no: str(x.SBJ_NO, 20),
          sbj_nm: str(x.SBJ_NM),
          dvcls: str(x.DVCLS, 10) || '',
          emp_nm: str(x.EMP_NM, 50),
        }
        if (!r.year || !r.sem_cd || !r.sbj_no || !r.sbj_nm) continue
        const k = [r.year, r.sem_cd, r.sbj_no, r.dvcls].join('|')
        rec[k] = { ...rec[k], ...r, emp_nm: r.emp_nm || (rec[k]?.emp_nm as string) || null }
      }
    } else if (/EdcLesn010\/doList/.test(url)) {
      for (const x of rows) {
        if (!x.SBJ_NO || !x.OPEN_YY) continue
        const k = [x.OPEN_YY, x.OPEN_SEM_CD, x.SBJ_NO, x.DVCLS].join('|')
        if (cat[k] && x.MAIN_PROF_YN !== 'Y') continue // 공동 강의는 대표 교수만
        cat[k] = {
          year: str(x.OPEN_YY, 4),
          sem_cd: str(x.OPEN_SEM_CD, 20),
          sbj_no: str(x.SBJ_NO, 20),
          sbj_nm: str(x.SBJ_NM),
          dvcls: str(x.DVCLS, 10) || '',
          emp_no: str(x.EMP_NO, 20),
          emp_nm: str(x.EMP_NM, 50),
          colg_nm: str(x.COLG_NM, 100),
          dpt_nm: str(x.DPT_NM, 100),
          cpdiv_nm: str(x.CPDIV_CD_NM, 50),
          cdt: str(x.CDT, 10),
          timetable: str(x.TMTBL_KOR_DSC, 300),
          room: str(x.ROOM_KOR_DSC, 300),
          mid_rate: num(x.MID_EVAL_RATE),
          fnl_rate: num(x.FNL_EVAL_RATE),
          atnd_rate: num(x.ATND_EVAL_RATE),
          proj_rate: num(x.PROJ_EVAL_RATE),
          plan_url: str(x.PLAN_URL, 500),
        }
      }
    } else return
    render()
  }
  const XO = XMLHttpRequest.prototype.open
  const XS = XMLHttpRequest.prototype.send
  XMLHttpRequest.prototype.open = function (
    this: XMLHttpRequest & { __u?: string },
    ...a: unknown[]
  ) {
    this.__u = String(a[1])
    return (XO as (...x: unknown[]) => void).apply(this, a)
  } as typeof XMLHttpRequest.prototype.open
  XMLHttpRequest.prototype.send = function (
    this: XMLHttpRequest & { __u?: string },
    ...a: unknown[]
  ) {
    this.addEventListener('load', () => {
      try {
        take(this.__u || this.responseURL, this.responseText)
      } catch {
        /* 무시 */
      }
    })
    return (XS as (...x: unknown[]) => void).apply(this, a)
  } as typeof XMLHttpRequest.prototype.send
  const F = window.fetch
  window.fetch = async (...a: Parameters<typeof fetch>) => {
    const res = await F(...a)
    try {
      const u = typeof a[0] === 'string' ? a[0] : (a[0] as Request).url
      res
        .clone()
        .text()
        .then((t) => take(u, t))
    } catch {
      /* 무시 */
    }
    return res
  }
  const box = document.createElement('div')
  box.style.cssText =
    'position:fixed;top:12px;right:12px;z-index:2147483647;width:300px;padding:14px;border-radius:12px;' +
    'background:#fff;color:#222;font:14px/1.5 sans-serif;box-shadow:0 6px 24px rgba(0,0,0,.25);border:2px solid #c8102e'
  document.body.appendChild(box)
  const msg = (t: string) => {
    const p = box.querySelector('[data-m]') as HTMLElement
    if (p) p.textContent = t
  }
  function render() {
    const n = Object.keys(rec).length
    const m = Object.keys(cat).length
    box.innerHTML =
      '<b style="color:#c8102e">동국스터디 가져오기</b>' +
      '<div style="margin:6px 0">수강 기록 <b>' +
      n +
      '</b>건' +
      (m ? ', 개설 강좌 <b>' + m + '</b>건' : '') +
      ' 모음</div>' +
      '<div style="font-size:12px;color:#666">누르면 바로 가져옵니다. 안 되면 수강신청 &gt; 수강신청내역확인, 성적 &gt; 전체성적조회 화면을 열어도 모입니다.</div>' +
      '<div data-m style="font-size:12px;color:#c8102e;margin-top:6px"></div>' +
      '<div style="display:flex;gap:6px;margin-top:8px"><button data-s style="flex:1;padding:6px;border:0;border-radius:8px;background:#c8102e;color:#fff;cursor:pointer">동국스터디로 보내기</button>' +
      '<button data-x style="padding:6px 10px;border:1px solid #ccc;border-radius:8px;background:#fff;cursor:pointer">닫기</button></div>'
    ;(box.querySelector('[data-x]') as HTMLElement).onclick = () => (box.style.display = 'none')
    ;(box.querySelector('[data-s]') as HTMLElement).onclick = send
  }
  function send() {
    const payload = { type: TYPE, records: Object.values(rec), catalog: Object.values(cat) }
    if (!payload.records.length && !payload.catalog.length) {
      msg('아직 모은 기록이 없습니다. 위 화면을 먼저 열어 주세요.')
      return
    }
    if (window.opener) {
      window.opener.postMessage(payload, SITE)
      msg('보냈습니다. 동국스터디 창으로 돌아가세요.')
    } else {
      navigator.clipboard.writeText(JSON.stringify(payload)).then(
        () => msg('동국스터디 창을 찾지 못해 복사했습니다. 가져오기 화면에 붙여 넣어 주세요.'),
        () => msg('동국스터디 창에서 "엔드림스 열기"로 연 창에서 다시 눌러 주세요.'),
      )
    }
  }
  // 화면을 열지 않고 바로 요청한다. 엔드림스 화면이 쓰는 것과 같은 순서:
  // 로그인 정보(NANA) → 사용자 정보(LOGIN_IDEN_NO, MAIN_OPEN_KEY) → 메뉴에서 화면별 NANA → 화면 데이터
  type Json = Record<string, unknown>
  const post = async (path: string, data: Record<string, string>, ds = true) => {
    const body = new URLSearchParams(
      ds
        ? {
            _psnIncldPgmResn: '',
            _psnIncldPgmResnCd: '',
            _vsRdsnPerm: '',
            ...data,
            '@d#': '@d1#',
            '@d1#': 'dmSearch',
            '@d1#tp': 'dm',
          }
        : data,
    )
    const res = await F(path, {
      method: 'POST',
      body,
      credentials: 'include',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8' },
    })
    const text = await res.text()
    take(path, text)
    return JSON.parse(text) as Json
  }
  const rowsOf = (j: Json) =>
    Object.values(j).flatMap((v) => (Array.isArray(v) ? (v as Json[]) : [])) as Json[]
  async function auto() {
    msg('엔드림스에서 바로 가져오는 중…')
    const acc = (await post('/unis/main/view/login/doUserLoginAccs.do', {}, false))
      .dmLoginAccsResult as Json | undefined
    const nana = acc && String(acc.NANA || '')
    if (!nana) throw new Error('login')
    const top = await post('/unis/main/view/menu/doListUserMenuListTop.do', {
      _runningNana: nana,
      '@d1#MOBILE_YN': 'N',
    })
    const u = (top.dmUserInfo || {}) as Json
    const run = {
      _runningLoginIdenNo: String(u.LOGIN_IDEN_NO || ''),
      _runningMainOpenKey: String(u.MAIN_OPEN_KEY || ''),
    }
    // 화면별 NANA: 위쪽 메뉴에 없으면 왼쪽 메뉴를 펼쳐 찾는다
    const menus = rowsOf(top)
    const pgmNana = async (pgm: string) => {
      const hit = (rows: Json[]) => rows.find((m) => String(m.PGM_URL || '').includes(pgm))
      let m = hit(menus)
      const tops = [...new Set(menus.map((x) => String(x.MENU_NO || '')).filter(Boolean))]
      for (const no of tops) {
        if (m) break
        const left = rowsOf(
          await post('/unis/main/view/menu/doListUserMenuListLeft.do', {
            _runningNana: nana,
            ...run,
            '@d1#MENU_NO': no,
            '@d1#MOBILE_YN': 'N',
          }),
        )
        menus.push(...left)
        m = hit(left)
      }
      return m ? String(m.NANA || '') : ''
    }
    // 학번: 사용자 정보 중 10자리 숫자
    const ten = [...Object.entries(u), ...Object.entries(acc || {})]
      .sort(([a], [b]) => Number(/STD|USER|LOGIN_ID/.test(b)) - Number(/STD|USER|LOGIN_ID/.test(a)))
      .map(([, v]) => String(v ?? ''))
      .find((v) => /^\d{10}$/.test(v))
    const stdNo = ten || (prompt('학번(10자리)을 입력해 주세요. 엔드림스 조회에만 씁니다.') ?? '').trim()
    if (!/^\d{10}$/.test(stdNo)) throw new Error('std')
    const before = Object.keys(rec).length
    // 지난 학기들: 전체성적조회
    const recNana = await pgmNana('EddRec050')
    if (recNana)
      await post('/ed/edd/rec/EddRec050/doList.do', {
        _runningNana: recNana,
        ...run,
        '@d1#STD_NO': stdNo,
        '@d1#LOCALE': 'ko',
      })
    // 이번 학기: 수강신청내역확인 (2~7월 1학기, 8~1월 2학기)
    const regiNana = await pgmNana('EdcRegi170')
    if (regiNana) {
      const d = new Date()
      const mo = d.getMonth() + 1
      const yy = String(mo === 1 ? d.getFullYear() - 1 : d.getFullYear())
      const sem = mo >= 2 && mo <= 7 ? 'CM160.10' : 'CM160.20'
      await post('/ed/edc/regi/EdcRegi170/doList.do', {
        _runningNana: regiNana,
        ...run,
        '@d1#OPEN_ORGN_CLSF_CD': 'CM015.110',
        '@d1#OPEN_YY': yy,
        '@d1#OPEN_SEM_CD': sem,
        '@d1#STD_NO': stdNo,
        '@d1#AUTH_CTL2_CD': '',
      })
    }
    if (Object.keys(rec).length === before) throw new Error('empty')
    send()
  }

  w.__dguStudy = { show: () => (box.style.display = 'block') }
  render()
  auto().catch((e: Error) =>
    msg(
      e.message === 'login'
        ? '엔드림스에 먼저 로그인한 뒤 다시 눌러 주세요.'
        : '바로 가져오지 못했습니다. 수강신청내역확인·전체성적조회 화면을 열면 모입니다.',
    ),
  )
}

/** 즐겨찾기 줄에 끌어다 놓을 javascript: 주소 */
export function bookmarkletHref(siteOrigin: string): string {
  const hosts = NDRIMS_ORIGINS
  const code = `(${inNdrims.toString()})(${JSON.stringify(siteOrigin)},${JSON.stringify(hosts)},${JSON.stringify(MESSAGE_TYPE)})`
  return `javascript:${encodeURIComponent(code)}`
}

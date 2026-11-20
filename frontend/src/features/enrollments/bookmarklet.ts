/**
 * 엔드림스 창에서 누르는 즐겨찾기 버튼(북마클릿) 코드.
 *
 * 하는 일: 엔드림스 화면이 서버에서 받아 오는 데이터(JSON)를 옆에서 받아 적는다.
 * - 수강신청내역확인(EdcRegi170), 전체성적조회(EddRec050) → 수강 기록 (과목 찾는 칸만, 성적은 버림)
 * - 종합강의시간표조회(EdcLesn010) → 개설 목록 (관리자만 사이트에 저장됨)
 * - 관리자: 고른 학기의 개설 목록 전체, 사이트 과목의 강의계획서(EdcPlan010P20) 글 → 팀플 판정용
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
    emp_no?: string | null
  }[]
  catalog: Record<string, string | number | null>[]
  /** 관리자: 강의계획서 글(판정에 쓰는 칸만). 서버는 팀플 여부와 근거 문장만 저장한다 */
  syllabi?: { year: string; sem_cd: string; sbj_no: string; dvcls: string; text: string }[]
}

// 엔드림스 창 안에서 실행되는 코드. 바깥 변수는 쓰지 않는다(문자열로 바뀌어 들어간다).
function inNdrims(SITE: string, HOSTS: string[], TYPE: string, ADMIN: boolean, CODES: string[]) {
  const w = window as unknown as { __dguStudy?: { show: () => void; run: () => void; v?: number; box?: HTMLElement } }
  if (!HOSTS.some((h) => location.origin === h)) {
    alert('엔드림스(ndrims.dongguk.edu) 창에서 눌러 주세요.')
    return
  }
  const VER = 12
  // 예전 버전 상자가 남아 있으면 치우고 새로 시작한다(새로고침 없이 새 버튼이 동작하도록)
  if (w.__dguStudy && w.__dguStudy.v !== VER) {
    w.__dguStudy.box?.remove()
    w.__dguStudy = undefined
  }
  if (w.__dguStudy) {
    w.__dguStudy.show()
    w.__dguStudy.run() // 다시 누르면 다시 가져온다
    return
  }
  type Row = Record<string, unknown>
  const rec: Record<string, Row> = {}
  const cat: Record<string, Row> = {} // 개설 목록(관리자가 보냄): 종합강의시간표 화면·전체 가져오기
  const look: Record<string, Row> = {} // 내 수업 교수 찾기용 조회 결과(보내지 않음)
  const syl: Record<string, { year: string; sem_cd: string; sbj_no: string; dvcls: string; text: string }> = {}
  const code = (v: unknown) => String(v ?? '').toUpperCase().replace(/[^A-Z0-9]/g, '')
  const SITE_CODES = new Set(CODES.map(code))
  const SEMS: [string, string][] = [['CM160.10', '1학기'], ['CM160.11', '여름학기'], ['CM160.20', '2학기'], ['CM160.21', '겨울학기']]
  let pick: [string, string] | null = null // 관리자가 고른 학기(없으면 이번 학기)
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
      let kept = 0
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
        kept++
      }
      log.push(
          `${grade ? '성적' : '수강신청'} 행 ${rows.length} → 기록 ${kept}` +
            (rows.length && !kept ? ` (칸: ${Object.keys(rows[0]).join(',')})` : ''),
        )
    } else if (/EdcLesn010\/doList/.test(url)) {
      lesnInto(cat, rows)
    } else return
    render()
  }
  // 종합강의시간표 행 → 개설 목록 한 줄(공동 강의는 대표 교수만)
  function lesnInto(into: Record<string, Row>, rows: Row[]) {
    for (const x of rows) {
      if (!x.SBJ_NO || !x.OPEN_YY || !x.OPEN_SEM_CD || !x.SBJ_NM) continue
      const k = [x.OPEN_YY, x.OPEN_SEM_CD, x.SBJ_NO, x.DVCLS].join('|')
      if (into[k] && x.MAIN_PROF_YN !== 'Y') continue
      into[k] = {
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
    try {
      // 종합강의시간표 화면이 조회할 때 보내는 칸(조회 조건)을 진단에 남긴다. 실행 정보·학번 같은 값은 가린다
      if (/EdcLesn010\/doList/.test(this.__u || '')) {
        const b = a[0]
        const ps =
          typeof b === 'string'
            ? new URLSearchParams(b)
            : b instanceof URLSearchParams
              ? b
              : b instanceof FormData
                ? new URLSearchParams(
                    [...b.entries()].map(([k, v]) => [k, String(v)] as [string, string]),
                  )
                : null
        if (ps)
          log.push(
            '시간표 조회 칸: ' +
              [...ps.entries()]
                .filter(([k]) => k.startsWith('@d1#'))
                .map(([k, v]) => k.slice(4) + '=' + (/^\d{6,}$/.test(v) ? '*' : v.slice(0, 20)))
                .join(', '),
          )
      }
    } catch {
      /* 무시 */
    }
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
  const log: string[] = [] // 진단: 칸 이름과 건수만 (값은 넣지 않음)
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
      '<b style="color:#c8102e">동국스터디 가져오기</b> <span style="font-size:11px;color:#999">v' + VER + '</span>' +
      '<div style="margin:6px 0">수강 기록 <b>' +
      n +
      '</b>건' +
      (m ? ', 개설 강좌 <b>' + m + '</b>건' : '') +
      (Object.keys(syl).length ? ', 계획서 <b>' + Object.keys(syl).length + '</b>건' : '') +
      ' 모음</div>' +
      '<div style="font-size:12px;color:#666">누르면 바로 가져옵니다. 안 되면 수강신청 &gt; 수강신청내역확인, 성적 &gt; 전체성적조회 화면을 열어도 모입니다.</div>' +
      '<div data-m style="font-size:12px;color:#c8102e;margin-top:6px"></div>' +
      (ADMIN
        ? '<div style="display:flex;gap:6px;margin-top:8px"><select data-y style="flex:1;padding:4px">' +
          [0, 1, 2, 3, 4].map((i) => { const y = String(Number(term()[0]) - i); return '<option value="' + y + '">' + y + '년</option>' }).join('') +
          '</select><select data-t style="flex:1;padding:4px">' +
          SEMS.map(([c, l]) => '<option value="' + c + '">' + l + '</option>').join('') +
          '</select></div>' +
          '<button data-c style="width:100%;margin-top:6px;padding:6px;border:1px solid #c8102e;border-radius:8px;background:#fff;color:#c8102e;cursor:pointer">관리자: 이 학기 개설 목록 전체 가져오기</button>' +
          '<button data-p style="width:100%;margin-top:6px;padding:6px;border:1px solid #c8102e;border-radius:8px;background:#fff;color:#c8102e;cursor:pointer">관리자: 이 학기 강의계획서 가져오기 (사이트 과목 ' +
          SITE_CODES.size +
          '개)</button>' +
          '<button data-r style="width:100%;margin-top:6px;padding:4px;border:0;background:none;color:#666;font-size:12px;cursor:pointer;text-decoration:underline">내 수강 기록도 가져오기</button>'
        : '') +
      '<div style="display:flex;gap:6px;margin-top:8px"><button data-s style="flex:1;padding:6px;border:0;border-radius:8px;background:#c8102e;color:#fff;cursor:pointer">동국스터디로 보내기</button>' +
      '<button data-x style="padding:6px 10px;border:1px solid #ccc;border-radius:8px;background:#fff;cursor:pointer">닫기</button></div>'
    ;(box.querySelector('[data-x]') as HTMLElement).onclick = () => (box.style.display = 'none')
    ;(box.querySelector('[data-s]') as HTMLElement).onclick = () => send()
    const ySel = box.querySelector('[data-y]') as HTMLSelectElement | null
    const tSel = box.querySelector('[data-t]') as HTMLSelectElement | null
    if (ySel && tSel) {
      const [y0, t0] = pick || term()
      ySel.value = y0
      tSel.value = t0
      ySel.onchange = tSel.onchange = () => (pick = [ySel.value, tSel.value])
    }
    const c = box.querySelector('[data-c]') as HTMLElement | null
    if (c) c.onclick = () => fullCatalog().catch(fail)
    const pl = box.querySelector('[data-p]') as HTMLElement | null
    if (pl) pl.onclick = () => syllabi().catch(fail)
    const r = box.querySelector('[data-r]') as HTMLElement | null
    if (r) r.onclick = () => run(true)
  }
  let viaOpener = !!window.opener
  let acked = false
  let pending: unknown = null // 새 탭이 달라고 하면 보낼 것
  window.addEventListener('message', (e) => {
    if (e.origin !== SITE) return
    const t = (e.data as { type?: string } | null)?.type
    if (t === TYPE + '-ack') acked = true
    if (t === TYPE + '-pull' && pending && e.source) {
      ;(e.source as Window).postMessage(pending, SITE)
      msg('보냈습니다. 동국스터디 탭에서 확인을 눌러 저장하세요.')
    }
  })
  function send(auto = false) {
    const payload = { type: TYPE, records: Object.values(rec), catalog: Object.values(cat), syllabi: Object.values(syl) }
    if (!payload.records.length && !payload.catalog.length) {
      msg('아직 모은 기록이 없습니다. 위 화면을 먼저 열어 주세요.')
      return
    }
    // 1) 우리 사이트가 연 창이면 그 창으로 보내고 받았다는 답을 기다린다
    if (viaOpener && window.opener) {
      acked = false
      try {
        window.opener.postMessage(payload, SITE)
      } catch {
        /* 아래에서 새 탭으로 */
      }
      msg('보내는 중…')
      setTimeout(() => {
        if (acked) return msg('보냈습니다. 동국스터디 창으로 돌아가세요.')
        viaOpener = false
        msg('동국스터디 창을 찾지 못했습니다. [동국스터디로 보내기]를 누르면 새 탭으로 보냅니다.')
      }, 2000)
      return
    }
    // 자동으로는 새 창을 열지 않는다(사용자가 버튼을 눌렀을 때만)
    if (auto) {
      msg('다 모았습니다. [동국스터디로 보내기]를 누르면 동국스터디로 보냅니다.')
      return
    }
    // 2) 창 연결이 끊겼으면(엔드림스 로그인 과정에서 끊긴다) 우리 사이트를 새 탭으로 연다.
    //    그 탭이 이 창에 '달라'고 하면 그 탭으로 보낸다(주소에 담지 않으니 개설 목록이 커도 된다)
    pending = payload
    const tab = window.open(SITE + '/ndrims#pull', 'dgu-study-import')
    msg(
      tab
        ? '동국스터디 탭을 열었습니다. 그 탭으로 보내는 중…'
        : '[동국스터디로 보내기]를 눌러 주세요. (팝업이 막혔다면 주소창 오른쪽에서 허용)',
    )
  }
  // 화면을 열지 않고 바로 요청한다. 엔드림스 화면이 쓰는 것과 같은 순서:
  // 로그인 정보(NANA) → 사용자 정보(LOGIN_IDEN_NO, MAIN_OPEN_KEY) → 메뉴에서 화면별 NANA → 화면 데이터
  type Json = Record<string, unknown>
  const post = async (path: string, data: Record<string, string>, ds = true, lookup = false) => {
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
    const name = path.split('/').slice(-2).join('/')
    let j: Json
    try {
      j = JSON.parse(text) as Json
    } catch {
      log.push(`${name} ${res.status} JSON 아님`)
      throw new Error(/LoginAccs/.test(name) ? 'login' : 'step')
    }
    log.push(`${name} ${res.status} ${shape(j)}`)
    if (lookup) lesnInto(look, ((j as { dsMain?: Row[] }).dsMain || []) as Row[])
    else take(path, text)
    return j
  }
  // 응답 모양: 데이터셋 이름[행 수], 객체{칸 이름}. 오류 문구만 값을 보인다
  const shape = (j: Json): string =>
    Object.entries(j)
      .map(([k, v]) =>
        Array.isArray(v)
          ? `${k}[${v.length}]`
          : v && typeof v === 'object'
            ? `${k}{${Object.keys(v as Json).join(',')}}`
            : /msg|err/i.test(k)
              ? `${k}="${String(v).slice(0, 80)}"`
              : k,
      )
      .join(' ')
  const rowsOf = (j: Json) =>
    Object.values(j).flatMap((v) => (Array.isArray(v) ? (v as Json[]) : [])) as Json[]
  // 이번 학기(2~7월 1학기, 8~1월 2학기)
  function term(): [string, string] {
    const d = new Date()
    const mo = d.getMonth() + 1
    return [String(mo === 1 ? d.getFullYear() - 1 : d.getFullYear()), mo >= 2 && mo <= 7 ? 'CM160.10' : 'CM160.20']
  }
  function termLabel(t: [string, string] = term()) {
    return t[0] + ' ' + (SEMS.find(([c]) => c === t[1])?.[1] ?? t[1])
  }
  type Sess = { nana: string; ids: Record<string, string>; pgmNana: (p: string) => Promise<string>; u: Json; acc: Json }
  let sess: Promise<Sess> | null = null
  function session(): Promise<Sess> {
    sess ??= (async () => {
      const acc = (await post('/unis/main/view/login/doUserLoginAccs.do', {}, false))
        .dmLoginAccsResult as Json | undefined
      const nana = acc && String(acc.NANA || '')
      if (!nana) throw new Error('login')
      const top = await post('/unis/main/view/menu/doListUserMenuListTop.do', {
        _runningNana: nana,
        '@d1#MOBILE_YN': 'N',
      })
      const u = (top.dmUserInfo || {}) as Json
      const ids = {
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
              ...ids,
              '@d1#MENU_NO': no,
              '@d1#MOBILE_YN': 'N',
            }),
          )
          menus.push(...left)
          m = hit(left)
        }
        log.push(`메뉴 ${menus.length}개, ${pgm} ${m ? '찾음' : '없음'}`)
        return m ? String(m.NANA || '') : ''
      }
      return { nana, ids, pgmNana, u, acc: acc || {} }
    })()
    sess.catch(() => (sess = null)) // 실패하면 다음에 다시
    return sess
  }

  // 관리자: 고른 학기 종합강의시간표 전체(대학·학과 조건 없이). 시간표 행(원본)을 돌려준다
  async function termRows(): Promise<{ rows: Json[]; lesnNana: string; ids: Record<string, string> }> {
    const t = pick || term()
    msg(termLabel(t) + ' 개설 목록을 가져오는 중… (몇 초 걸립니다)')
    const { ids, pgmNana } = await session()
    const lesnNana = await pgmNana('EdcLesn010')
    if (!lesnNana) throw new Error('lesn')
    const j = await post('/ed/edc/lesn/EdcLesn010/doList.do', {
      _runningNana: lesnNana,
      ...ids,
      '@d1#OPEN_ORGN_CLSF_CD': 'CM015.110',
      '@d1#OPEN_YY': t[0],
      '@d1#OPEN_SEM_CD': t[1],
    })
    render()
    return { rows: ((j as { dsMain?: Json[] }).dsMain || []) as Json[], lesnNana, ids }
  }
  async function fullCatalog() {
    const { rows } = await termRows()
    if (!rows.length) {
      msg('이 학기 개설 목록이 비어 있습니다. 수업/강의평가 > 종합강의시간표조회에서 대학별로 조회하면 상자에 모입니다.')
      return
    }
    send(true)
  }

  // 관리자: 고른 학기에서 사이트에 있는 과목의 강의계획서. 시간표의 "강의계획서" 버튼이 여는 팝업과 같은 요청
  async function syllabi() {
    if (!SITE_CODES.size) {
      msg('사이트에 과목코드가 있는 과목이 없습니다.')
      return
    }
    const { rows, lesnNana, ids } = await termRows()
    const targets: Record<string, Json> = {}
    for (const x of rows) {
      if (!SITE_CODES.has(code(x.SBJ_NO))) continue
      const k = [x.OPEN_YY, x.OPEN_SEM_CD, x.SBJ_NO, x.DVCLS].join('|')
      if (!targets[k] || x.MAIN_PROF_YN === 'Y') targets[k] = x
    }
    const list = Object.entries(targets)
    let empty = 0
    for (let i = 0; i < list.length; i++) {
      const [k, x] = list[i]
      msg(`강의계획서 ${i + 1}/${list.length} 가져오는 중…`)
      const q: Record<string, string> = {
        OPEN_ORGN_CLSF_CD: String(x.OPEN_ORGN_CLSF_CD || 'CM015.110'),
        OPEN_YY: String(x.OPEN_YY),
        OPEN_SEM_CD: String(x.OPEN_SEM_CD),
        EMP_NO: String(x.EMP_NO ?? ''),
        PLAN_LANG_CD: 'CM310.ko',
        DVCLS: String(x.DVCLS ?? ''),
        SBJ_NO: String(x.SBJ_NO),
        OPEN_DPTMJR_CD: String(x.OPEN_DPTMJR_CD ?? ''),
      }
      const j = await post('/ed/edc/plan/popup/EdcPlan010P20/doList.do', {
        _runningNana: lesnNana,
        ...ids,
        ...Object.fromEntries(Object.entries(q).map(([a, b]) => ['@d1#' + a, b])),
      })
      const text = planText(j)
      if (text) syl[k] = { year: q.OPEN_YY, sem_cd: q.OPEN_SEM_CD, sbj_no: q.SBJ_NO, dvcls: q.DVCLS, text }
      else empty++
      await new Promise((r) => setTimeout(r, 200)) // 학교 서버에 몰아서 보내지 않는다
    }
    log.push(`계획서 대상 ${list.length}, 받음 ${list.length - empty}, 비어 있음 ${empty}`)
    render()
    if (!list.length) {
      msg('이 학기에 열린 사이트 과목이 없습니다.')
      return
    }
    send(true)
  }
  // 계획서 응답 → 판정용 글. 수업 목표·개요, 평가, 주차별 내용, 과제·프로젝트만 쓴다.
  // dsTabAolAt(평가 도구)은 모든 강좌에 같은 선택지 목록("Team Project" 등)이 오고 CHK로만 다르다 → 고른 것(CHK=Y)만.
  // 코드·번호·날짜·교원 칸은 뺀다.
  function planText(j: Json): string {
    const skip = /(_CD|_NO|_YY|_YN|_DTTM|_ID|_SEQ|_RATE|CHK|DVCLS|TEL|EMAIL)$|^(EMP_|PROF|SBJ_NM|SYS_)/
    const rowsIn = (v: unknown) => (Array.isArray(v) ? (v as Json[]) : v && typeof v === 'object' ? [v as Json] : [])
    const lines = new Set<string>()
    for (const ds of ['dsMain', 'dsSub', 'dsTabLesn', 'dsTabWeek', 'dsTabProj'])
      for (const r of rowsIn(j[ds]))
        for (const [c, v] of Object.entries(r))
          if (typeof v === 'string' && v.trim() && !skip.test(c) && !/^기타\d$/.test(v.trim())) lines.add(v.trim())
    for (const r of rowsIn(j.dsTabAolAt))
      if (r.CHK === 'Y' && typeof r.AOL_LESN_AIM_TOOL_DSC === 'string') lines.add(r.AOL_LESN_AIM_TOOL_DSC.trim())
    return [...lines].join('\n').slice(0, 100000)
  }

  async function auto() {
    msg('엔드림스에서 바로 가져오는 중…')
    const { ids, pgmNana, u, acc } = await session()
    // 학번: 사용자 정보 중 10자리 숫자
    const pref = /STD|LOGIN_ID|MEMB_NO|USER/
    const hit = [...Object.entries(u), ...Object.entries(acc || {})]
      .sort(([a], [b]) => Number(pref.test(b)) - Number(pref.test(a)))
      .find(([, v]) => /^\d{10}$/.test(String(v ?? '')))
    const ten = hit && String(hit[1])
    const stdNo = ten || (prompt('학번(10자리)을 입력해 주세요. 엔드림스 조회에만 씁니다.') ?? '').trim()
    log.push(`학번 ${hit ? hit[0] + ' 칸에서 찾음' : '직접 입력'}`)
    if (!/^\d{10}$/.test(stdNo)) throw new Error('std')
    // 지난 학기들: 전체성적조회
    const recNana = await pgmNana('EddRec050')
    if (recNana)
      await post('/ed/edd/rec/EddRec050/doList.do', {
        _runningNana: recNana,
        ...ids,
        '@d1#STD_NO': stdNo,
        '@d1#LOCALE': 'ko',
      })
    // 이번 학기: 수강신청내역확인 (2~7월 1학기, 8~1월 2학기)
    const regiNana = await pgmNana('EdcRegi170')
    if (regiNana) {
      const [yy, sem] = term()
      await post('/ed/edc/regi/EdcRegi170/doList.do', {
        _runningNana: regiNana,
        ...ids,
        '@d1#OPEN_ORGN_CLSF_CD': 'CM015.110',
        '@d1#OPEN_YY': yy,
        '@d1#OPEN_SEM_CD': sem,
        '@d1#STD_NO': stdNo,
        '@d1#AUTH_CTL2_CD': '',
      })
    }
    // 이번 학기 수업은 교수 칸이 없다 → 종합강의시간표에서 학수번호로 찾아 교수명·교원번호를 붙인다
    const noProf = Object.values(rec).filter((r) => !r.emp_nm)
    const lesnNana = noProf.length ? await pgmNana('EdcLesn010') : ''
    if (lesnNana) {
      for (const r of noProf) {
        try {
          await post('/ed/edc/lesn/EdcLesn010/doList.do', {
            _runningNana: lesnNana,
            ...ids,
            '@d1#OPEN_ORGN_CLSF_CD': 'CM015.110',
            '@d1#OPEN_YY': String(r.year),
            '@d1#OPEN_SEM_CD': String(r.sem_cd),
            '@d1#SBJ_NO': String(r.sbj_no),
          }, true, true)
        } catch {
          /* 진단에 남음 */
        }
        const c = look[[r.year, r.sem_cd, r.sbj_no, r.dvcls].join('|')]
        if (c) {
          r.emp_nm = c.emp_nm
          r.emp_no = c.emp_no
        }
      }
      log.push(
        `교수 찾음 ${noProf.filter((r) => r.emp_nm).length}/${noProf.length}` +
          ` (시간표 행 ${Object.keys(look).length})`,
      )
    }
    log.push(`모은 수강 기록 모두 ${Object.keys(rec).length}건`)
    render()
    if (!Object.keys(rec).length) throw new Error('empty')
    send(true)
  }

  let busy = false
  const run = (force = false) => {
    if (ADMIN && !force) {
      render()
      msg('관리자: 학기를 고르고 개설 목록이나 강의계획서를 가져옵니다.')
      return
    }
    if (busy) return
    busy = true
    log.length = 0
    sess = null // 다시 누르면 엔드림스 로그인 정보부터 다시
    auto()
      .catch(fail)
      .finally(() => (busy = false))
  }
  w.__dguStudy = { show: () => (box.style.display = 'block'), run, v: VER, box }
  render()
  run()
  function fail(e: Error) {
    log.push(`멈춤: ${e.message}`)
    // 진단은 화면에 보이지 않고 개발자 도구(F12) 콘솔에만 남긴다. 칸 이름·건수만 있고 값은 없다
    console.info('[동국스터디 진단]\n' + log.join('\n'))
    render()
    msg(
      e.message === 'login'
        ? '엔드림스에 먼저 로그인한 뒤 다시 눌러 주세요.'
        : e.message === 'step' && Object.keys(cat).length
          ? '엔드림스 응답을 읽지 못했습니다. 다른 곳에서 엔드림스에 로그인하면 이 창의 접속이 끊깁니다. 다시 로그인한 뒤 눌러 주세요.'
        : e.message === 'lesn'
          ? '종합강의시간표 메뉴를 찾지 못했습니다. 그 화면을 열고 대학별로 조회하면 상자에 모입니다.'
        : '바로 가져오지 못했습니다. 수강신청 > 수강신청내역확인, 성적 > 전체성적조회 화면을 열면 모입니다.',
    )
  }
}

/** 즐겨찾기 줄에 끌어다 놓을 javascript: 주소 */
export function bookmarkletHref(siteOrigin: string, admin = false, codes: string[] = []): string {
  const hosts = NDRIMS_ORIGINS
  const code = `(${inNdrims.toString()})(${JSON.stringify(siteOrigin)},${JSON.stringify(hosts)},${JSON.stringify(MESSAGE_TYPE)},${admin},${JSON.stringify(admin ? codes : [])})`
  return `javascript:${encodeURIComponent(code)}`
}

// 새 디자인 켜기: frontend/.env.local에 VITE_DESIGN=on (내 컴퓨터에서만). 끄면 기존 화면 그대로(배포 기본값).
// 켜면 첫 화면이 /home, 기존 Layout 화면들도 새 디자인 틀(사이드바)로 보이고, 새 화면이 있는 옛 주소는 새 주소로 넘어간다.
export const DESIGN_ON = import.meta.env.VITE_DESIGN === 'on'

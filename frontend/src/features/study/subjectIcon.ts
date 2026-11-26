import {
  Atom,
  BookOpen,
  Bot,
  Brain,
  Briefcase,
  Calculator,
  ChartLine,
  Code,
  Cpu,
  Database,
  Earth,
  FlaskConical,
  Flower2,
  Globe,
  Dumbbell,
  HeartPulse,
  Landmark,
  Languages,
  type LucideIcon,
  Microscope,
  Network,
  Palette,
  PenLine,
  Scale,
  Shapes,
  ShieldCheck,
  Sigma,
  Terminal,
  Users,
} from 'lucide-react'

/**
 * 과목 이름에 든 낱말로 아이콘을 고른다. 위에서부터 처음 맞는 것을 쓴다(구체적인 낱말을 위에).
 * 맞는 게 없으면 책 아이콘: 엉뚱한 아이콘(명상 과목에 CPU 같은)보다 무난한 게 낫다.
 */
const RULES: [RegExp, LucideIcon][] = [
  [/인공지능|머신러닝|딥러닝|기계학습|AI/i, Bot],
  [/보안|암호/, ShieldCheck],
  [/데이터베이스|DB|빅데이터|데이터/i, Database],
  [/네트워크|통신|인터넷/, Network],
  [/웹|모바일|앱/, Globe],
  [/운영체제|시스템|컴퓨터구성|컴퓨터구조|아키텍처|하드웨어|임베디드|회로|반도체|디지털/, Cpu],
  [/리눅스|유닉스|쉘|셸/, Terminal],
  [/알고리즘|자료구조|이산/, Code],
  [/프로그래밍|코딩|소프트웨어|컴파일러|객체|파이썬|자바|C\+\+|SW/i, Code],
  [/그래픽|비전|영상처리|게임/, Shapes],
  [/미적분|선형대수|수학|확률|통계|해석|대수|기하/, Sigma],
  [/회계|재무|세무/, Calculator],
  [/경제|금융|투자/, ChartLine],
  [/경영|마케팅|창업|리더십/, Briefcase],
  [/물리|역학|전자기/, Atom],
  [/화학|생화학|실험/, FlaskConical],
  [/생물|생명|미생물|유전/, Microscope],
  [/의학|간호|보건|약학|건강/, HeartPulse],
  [/명상|불교|선(?:수행|학)?$|참선|요가|마음/, Flower2],
  [/심리|인지|뇌/, Brain],
  [/법학|법률|헌법|민법|형법|상법|법과|^법/, Scale],
  [/역사|세계사|한국사|동양사|서양사|사학|문화재|고고/, Landmark],
  [/영어|일본어|중국어|독일어|프랑스어|스페인어|외국어|언어|회화/, Languages],
  [/글쓰기|작문|문학|국어|독서|논술/, PenLine],
  [/미술|디자인|드로잉|예술|사진/, Palette],
  [/체육|스포츠|운동|골프|수영|테니스/, Dumbbell],
  [/사회|정치|행정|커뮤니케이션|윤리/, Users],
  [/지리|환경|지구|기후|생태/, Earth],
  [/철학|사상/, Brain],
  [/컴퓨터|정보/, Code],
]

const TONES = ['bg-tone-blue text-navy', 'bg-tone-gold text-[#6b4a0c]', 'bg-tone-gray text-navy-deep']

export function subjectIcon(name: string, id: number): { Icon: LucideIcon; tone: string } {
  const Icon = RULES.find(([re]) => re.test(name))?.[1] ?? BookOpen
  // 색은 과목 번호로 섞는다(새로고침해도 같은 과목은 같은 색)
  const h = Math.imul(id + 1, 2654435761) >>> 0
  return { Icon, tone: TONES[h % TONES.length] }
}

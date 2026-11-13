import { Empty, Loading } from '@/components/States'
import { Card } from '@/components/ui/card'
import { ImportPanel } from '@/features/enrollments/ImportPanel'
import { useTerms } from '@/features/catalog/queries'
import { AdminNav } from './AdminNav'

/** 관리자: 엔드림스 종합강의시간표(개설 목록) 가져오기. 강좌는 만들지 않고 찾기·요청·교수 확정에 쓴다. */
export function AdminCatalogPage() {
  const terms = useTerms()
  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-bold">관리</h1>
        <p className="text-sm text-muted-foreground">
          학기마다 한 번, 엔드림스 종합강의시간표를 가져옵니다. 강좌는 만들어지지 않고 '강좌 찾기'와
          요청, 교수 확인(교원번호)에만 쓰입니다.
        </p>
      </div>
      <AdminNav />
      <Card className="p-4">
        <h2 className="mb-2 font-semibold">저장된 개설 목록</h2>
        {terms.isPending ? (
          <Loading />
        ) : terms.data?.length === 0 ? (
          <Empty>아직 없습니다.</Empty>
        ) : (
          <ul className="text-sm">
            {terms.data?.map((t) => (
              <li key={`${t.year}${t.sem_cd}`}>
                {t.label}: {t.count}개 분반
              </li>
            ))}
          </ul>
        )}
      </Card>
      <ImportPanel compact />
      <p className="text-xs text-muted-foreground">
        종합강의시간표 화면에서 학기만 고르고 대학·학과는 비운 채 조회하면 그 학기 전체가 한 번에
        모입니다.
      </p>
    </div>
  )
}

import { Plus } from 'lucide-react'
import { Link } from 'react-router'
import { Empty, ErrorText, Loading } from '@/components/States'
import { Badge } from '@/components/ui/badge'
import { buttonVariants } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { AttachFiles } from './AttachFiles'
import { STATUS_LABEL, useMyRequests } from './queries'

export function MyRequestsPage() {
  const requests = useMyRequests()
  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold">내 강좌 열기 요청</h1>
          <p className="text-sm text-muted-foreground">
            교안이 붙으면 관리자가 확인한 뒤 강좌를 엽니다. 교안을 가지고 있다면 붙여 주세요.
          </p>
        </div>
        <Link to="/requests/new" className={buttonVariants({ variant: 'outline', size: 'sm' })}>
          <Plus />
          직접 요청
        </Link>
      </div>
      {requests.isPending ? (
        <Loading />
      ) : requests.data?.length === 0 ? (
        <Empty>
          아직 보낸 요청이 없습니다. 내 강좌의 '아직 열리지 않은 수업'이나{' '}
          <Link to="/find" className="text-primary hover:underline">
            강좌 찾기
          </Link>
          에서 요청할 수 있습니다.
        </Empty>
      ) : (
        <div className="flex flex-col gap-3">
          {requests.data?.map((r) => (
            <Card key={r.id} className="flex flex-col gap-2 p-4">
              <div className="flex items-center justify-between gap-2">
                <div className="font-semibold">
                  {r.subject_name} · {r.professor_name} 교수님
                </div>
                <Badge variant={r.status === 'pending' ? 'outline' : 'secondary'}>
                  {STATUS_LABEL[r.status] ?? r.status}
                </Badge>
              </div>
              <div className="text-sm text-muted-foreground">
                {r.semester && `${r.semester} · `}
                {r.has_material ? `교안 ${r.material_count}개` : '교안 없음'} ·{' '}
                {new Date(r.created_at).toLocaleDateString()}
                {r.status === 'pending' &&
                  r.same_pending_count > 1 &&
                  ` · 같은 강좌 요청 ${r.same_pending_count}명`}
              </div>
              {r.status === 'pending' && (
                <div>
                  <AttachFiles requestId={r.id} />
                </div>
              )}
              {r.status === 'rejected' && r.reject_reason && (
                <p className="text-sm">반려 사유: {r.reject_reason}</p>
              )}
              {r.status === 'approved' && r.course_id && (
                <Link to={`/courses/${r.course_id}`} className="text-sm text-primary underline">
                  강좌로 가기
                </Link>
              )}
            </Card>
          ))}
        </div>
      )}
      <ErrorText error={requests.error} />
    </div>
  )
}

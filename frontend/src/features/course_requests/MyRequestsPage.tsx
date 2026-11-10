import { Plus } from 'lucide-react'
import { Link } from 'react-router'
import { Empty, ErrorText, Loading } from '@/components/States'
import { Badge } from '@/components/ui/badge'
import { buttonVariants } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { STATUS_LABEL, useMyRequests } from './queries'

export function MyRequestsPage() {
  const requests = useMyRequests()
  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold">내 추가 요청</h1>
          <p className="text-sm text-muted-foreground">관리자가 승인하면 강좌가 열립니다.</p>
        </div>
        <Link to="/requests/new" className={buttonVariants({ variant: 'outline', size: 'sm' })}>
          <Plus />새 요청
        </Link>
      </div>
      {requests.isPending ? (
        <Loading />
      ) : requests.data?.length === 0 ? (
        <Empty>아직 보낸 요청이 없습니다.</Empty>
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
                {r.has_material ? `교안 ${r.material_title ?? ''}` : '교안 없음'} ·{' '}
                {new Date(r.created_at).toLocaleDateString()}
              </div>
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

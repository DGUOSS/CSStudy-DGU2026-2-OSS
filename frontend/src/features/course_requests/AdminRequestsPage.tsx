import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Check, X } from 'lucide-react'
import { useState } from 'react'
import { api, unwrap } from '@/api/client'
import { Empty, ErrorText, Loading } from '@/components/States'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { AdminNav } from '@/features/admin/AdminNav'
import { AttachFiles } from './AttachFiles'
import { type CourseRequest, STATUS_LABEL, useAdminRequests } from './queries'

type Filter = 'pending' | 'approved' | 'rejected' | undefined
const FILTERS: { key: Filter; label: string }[] = [
  { key: 'pending', label: '대기 중' },
  { key: 'approved', label: '승인' },
  { key: 'rejected', label: '반려' },
  { key: undefined, label: '전체' },
]

/** 관리자: 과목·강좌 추가 요청 승인/반려 */
export function AdminRequestsPage() {
  const [filter, setFilter] = useState<Filter>('pending')
  const requests = useAdminRequests(filter)

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-bold">관리</h1>
        <p className="text-sm text-muted-foreground">
          교안이 붙은 요청만 승인할 수 있습니다. 승인하면 강좌가 열리고 교안이 자료로 붙으며, 같은
          강좌를 기다리던 요청과 수강 기록이 함께 이어집니다.
        </p>
      </div>
      <AdminNav />
      <div className="flex gap-2">
        {FILTERS.map((f) => (
          <Button
            key={f.label}
            size="sm"
            variant={filter === f.key ? 'default' : 'outline'}
            onClick={() => setFilter(f.key)}
          >
            {f.label}
          </Button>
        ))}
      </div>
      {requests.isPending ? (
        <Loading />
      ) : requests.data?.length === 0 ? (
        <Empty>요청이 없습니다.</Empty>
      ) : (
        <div className="flex flex-col gap-3">
          {requests.data?.map((r) => (
            <RequestCard key={r.id} r={r} />
          ))}
        </div>
      )}
      <ErrorText error={requests.error} />
    </div>
  )
}

function RequestCard({ r }: { r: CourseRequest }) {
  const qc = useQueryClient()
  const [subjectName, setSubjectName] = useState(r.subject_name)
  const [professorName, setProfessorName] = useState(r.professor_name)
  const [reason, setReason] = useState('')
  const SOURCE_LABEL: Record<string, string> = {
    catalog: '개설 목록에서',
    record: '수강 기록에서',
    manual: '직접 입력',
  }
  const done = () => {
    qc.invalidateQueries({ queryKey: ['course-requests'] })
    qc.invalidateQueries({ queryKey: ['subjects'] })
  }
  const approve = useMutation({
    mutationFn: () =>
      unwrap(
        api.POST('/api/v1/admin/course-requests/{request_id}/approve', {
          params: { path: { request_id: r.id } },
          body: { subject_name: subjectName, professor_name: professorName },
        }),
      ),
    onSuccess: done,
  })
  const reject = useMutation({
    mutationFn: () =>
      unwrap(
        api.POST('/api/v1/admin/course-requests/{request_id}/reject', {
          params: { path: { request_id: r.id } },
          body: { reason },
        }),
      ),
    onSuccess: done,
  })
  const pending = r.status === 'pending'

  return (
    <Card className="flex flex-col gap-3 p-4">
      <div className="flex items-center justify-between gap-2">
        <div className="text-sm text-muted-foreground">
          #{r.id} · {r.requester_name ?? '알 수 없음'} · {new Date(r.created_at).toLocaleString()}
        </div>
        <Badge variant={r.status === 'pending' ? 'outline' : 'secondary'}>
          {STATUS_LABEL[r.status] ?? r.status}
        </Badge>
      </div>
      {pending ? (
        <div className="grid gap-2 sm:grid-cols-2">
          <Input
            aria-label="과목명"
            value={subjectName}
            onChange={(e) => setSubjectName(e.target.value)}
          />
          <Input
            aria-label="교수명"
            value={professorName}
            onChange={(e) => setProfessorName(e.target.value)}
          />
        </div>
      ) : (
        <div className="font-semibold">
          {r.subject_name} · {r.professor_name} 교수님
        </div>
      )}
      <div className="text-sm text-muted-foreground">
        {SOURCE_LABEL[r.source] ?? r.source} · {r.subject_code && `${r.subject_code} · `}
        {r.professor_emp_no && `교원 ${r.professor_emp_no} · `}
        {pending && r.same_pending_count > 1 && `같은 강좌 요청 ${r.same_pending_count}명 · `}
        {r.semester && `${r.semester} · `}
        {r.has_material
          ? `교안 ${r.material_count}개${r.material_page_count ? ` (${r.material_page_count}쪽)` : ''}: ${r.material_filenames.join(', ')}`
          : '교안 없음'}
      </div>
      {r.note && <p className="text-sm">메모: {r.note}</p>}
      {r.reject_reason && <p className="text-sm">반려 사유: {r.reject_reason}</p>}
      {pending && (
        <div className="flex flex-col gap-2 sm:flex-row">
          {!r.has_material && <AttachFiles requestId={r.id} />}
          <Button
            size="sm"
            onClick={() => approve.mutate()}
            disabled={approve.isPending || !r.has_material}
            title={r.has_material ? '' : '교안을 먼저 붙여 주세요'}
          >
            <Check />
            승인(강좌 열기)
          </Button>
          <Input
            className="sm:max-w-xs"
            placeholder="반려 사유 (적으면 반려 버튼이 켜집니다)"
            value={reason}
            onChange={(e) => setReason(e.target.value)}
          />
          <Button
            size="sm"
            variant="outline"
            onClick={() => reject.mutate()}
            disabled={reject.isPending || !reason.trim()}
          >
            <X />
            반려
          </Button>
        </div>
      )}
      {pending && !r.has_material && (
        <p className="text-xs text-muted-foreground">
          교안이 없어 아직 승인할 수 없습니다. 교안 PDF를 붙이면 승인 버튼이 켜집니다.
        </p>
      )}
      <ErrorText error={approve.error ?? reject.error} />
    </Card>
  )
}

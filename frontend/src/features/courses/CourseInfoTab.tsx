import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { api, type Schemas, unwrap } from '@/api/client'
import { ErrorText } from '@/components/States'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { useAuth } from '@/features/auth/useAuth'

/**
 * 강좌 정보: 강좌마다 하나인 공용 안내(수업 방식, 과제, 평가 비율 등). 관리자만 고친다.
 * 시험 정보는 여기 두지 않고 자료 탭 '시험 정보'에 파일로 올린다.
 */
export function CourseInfoTab({ course }: { course: Schemas['CourseOut'] }) {
  const { user } = useAuth()
  if (user?.role === 'admin') return <CourseInfoEditor course={course} />
  return (
    <div className="flex flex-col gap-4">
      <InfoBlock title="강좌 정보" text={course.info} />
      <p className="text-xs text-muted-foreground">
        이 내용은 관리자가 정리합니다. 시험 범위·일정 같은 시험 정보는 자료 탭의 '시험 정보'에서
        보고 올려 주세요.
      </p>
    </div>
  )
}

function InfoBlock({ title, text }: { title: string; text: string }) {
  return (
    <Card className="p-5">
      <div className="mb-2 text-sm font-semibold">{title}</div>
      {text.trim() ? (
        <p className="whitespace-pre-wrap text-sm">{text}</p>
      ) : (
        <p className="text-sm text-muted-foreground">아직 정리된 내용이 없습니다.</p>
      )}
    </Card>
  )
}

function CourseInfoEditor({ course }: { course: Schemas['CourseOut'] }) {
  const qc = useQueryClient()
  const [info, setInfo] = useState(course.info)
  const save = useMutation({
    mutationFn: () =>
      unwrap(
        api.PATCH('/api/v1/courses/{course_id}', {
          params: { path: { course_id: course.id } },
          body: { info },
        }),
      ),
    onSuccess: (data) => qc.setQueryData(['courses', course.id], data),
  })
  const changed = info !== course.info

  return (
    <div className="flex flex-col gap-4">
      <p className="text-sm text-muted-foreground">
        관리자만 고칠 수 있습니다. 모든 사용자에게 같은 내용이 보입니다. 시험 정보는 자료 탭 '시험 정보'에 파일로 올립니다.
      </p>
      <div className="grid gap-2">
        <Label htmlFor="info">강좌 정보</Label>
        <Textarea
          id="info"
          placeholder="수업 방식, 과제, 평가 비율 등"
          value={info}
          onChange={(e) => setInfo(e.target.value)}
        />
      </div>
      <ErrorText error={save.error} />
      <div className="flex items-center gap-3">
        <Button onClick={() => save.mutate()} disabled={!changed || save.isPending}>
          저장
        </Button>
        {save.isSuccess && !changed && (
          <span className="text-sm text-muted-foreground">저장했습니다</span>
        )}
      </div>
    </div>
  )
}

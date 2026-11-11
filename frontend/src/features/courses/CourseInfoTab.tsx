import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { api, type Schemas, unwrap } from '@/api/client'
import { ErrorText } from '@/components/States'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'

export function CourseInfoTab({ course }: { course: Schemas['CourseOut'] }) {
  const qc = useQueryClient()
  const [info, setInfo] = useState(course.info)
  const [examInfo, setExamInfo] = useState(course.exam_info)
  const save = useMutation({
    mutationFn: () =>
      unwrap(
        api.PATCH('/api/v1/courses/{course_id}', {
          params: { path: { course_id: course.id } },
          body: { info, exam_info: examInfo },
        }),
      ),
    onSuccess: (data) => qc.setQueryData(['courses', course.id], data),
  })
  const changed = info !== course.info || examInfo !== course.exam_info

  return (
    <div className="flex flex-col gap-4">
      <div className="grid gap-2">
        <Label htmlFor="info">강좌 정보</Label>
        <Textarea
          id="info"
          placeholder="수업 방식, 과제, 평가 비율 등"
          value={info}
          onChange={(e) => setInfo(e.target.value)}
        />
      </div>
      <div className="grid gap-2">
        <Label htmlFor="exam">시험 정보</Label>
        <Textarea
          id="exam"
          placeholder="시험 일정, 범위, 출제 유형(객관식/코드 작성 등), 선배 후기"
          value={examInfo}
          onChange={(e) => setExamInfo(e.target.value)}
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

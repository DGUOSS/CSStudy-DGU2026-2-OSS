import type { Schemas } from '@/api/client'

/** 판 관리 결과 안내 (쪽 내용 비교로 중복·새 판을 판단한다) */
export function resultText(r: Schemas['UploadOut']): string {
  if (r.action === 'duplicate') return '이미 같은 내용의 자료가 있어 새로 올리지 않았습니다.'
  const pages = `같은 쪽 ${r.pages_same}, 수정된 쪽 ${r.pages_modified}, 새 쪽 ${r.pages_new}`
  const moved = r.relinked_problems ? ` 문제 ${r.relinked_problems}개의 근거를 새 자료로 옮겼습니다.` : ''
  if (r.action === 'updated')
    return `기존 자료 ${(r.replaced_ids ?? []).length}개를 새 판으로 바꿨습니다 (${pages}).${moved}`
  return `새 자료로 올렸습니다 (${pages}).${moved}`
}

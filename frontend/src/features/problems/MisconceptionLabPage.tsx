import { useState } from 'react'
import { Link } from 'react-router'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader } from '@/components/ui/card'
import { cn } from '@/lib/utils'

type Confidence = '낮음' | '보통' | '높음'
type Step = 'first' | 'probe' | 'result'

const firstChoices = ['[007]', '[  7]']
const probeChoices = ['[042]', '[ 42]']

export function MisconceptionLabPage() {
  const [step, setStep] = useState<Step>('first')
  const [firstChoice, setFirstChoice] = useState<number | null>(null)
  const [confidence, setConfidence] = useState<Confidence | null>(null)
  const [probeChoice, setProbeChoice] = useState<number | null>(null)

  const reset = () => {
    setStep('first')
    setFirstChoice(null)
    setConfidence(null)
    setProbeChoice(null)
  }

  const firstWrong = firstChoice === 1
  const probeWrong = probeChoice === 1

  return (
    <main className="mx-auto flex min-h-screen max-w-3xl flex-col gap-6 px-4 py-10 sm:px-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-sm font-medium text-primary">기능 시범</p>
          <h1 className="mt-1 text-2xl font-bold">오개념 반례 실험실</h1>
          <p className="mt-2 text-sm text-muted-foreground">
            기초프로그래밍의 실제 샘플 문제를 바탕으로 만든 체험입니다. 답변은 저장되지 않습니다.
          </p>
        </div>
        <Link to="/" className="text-sm text-primary underline">
          동국 스터디로 돌아가기
        </Link>
      </div>

      <div className="flex gap-2 text-xs sm:text-sm" aria-label="진행 단계">
        {['1. 처음 판단', '2. 다른 상황', '3. 생각 정리'].map((label, index) => (
          <span
            key={label}
            className={cn(
              'flex-1 rounded-md border px-2 py-2 text-center',
              index === ['first', 'probe', 'result'].indexOf(step) &&
                'border-primary bg-primary/10 font-semibold text-primary',
            )}
          >
            {label}
          </span>
        ))}
      </div>

      {step === 'first' && (
        <Card>
          <CardHeader>
            <h2 className="text-lg font-semibold">이 코드의 출력 결과는?</h2>
            <pre className="rounded-md bg-muted p-4 text-sm">{'printf("[%03d]", 7);'}</pre>
          </CardHeader>
          <CardContent className="flex flex-col gap-5">
            <ChoiceGroup
              choices={firstChoices}
              selected={firstChoice}
              onSelect={setFirstChoice}
              label="첫 번째 문제의 답"
            />
            <fieldset className="flex flex-col gap-2">
              <legend className="mb-2 text-sm font-medium">내 답에 얼마나 확신하나요?</legend>
              <div className="flex flex-wrap gap-2">
                {(['낮음', '보통', '높음'] as const).map((value) => (
                  <Button
                    key={value}
                    type="button"
                    variant={confidence === value ? 'default' : 'outline'}
                    aria-pressed={confidence === value}
                    onClick={() => setConfidence(value)}
                  >
                    {value}
                  </Button>
                ))}
              </div>
            </fieldset>
            <Button
              className="self-end"
              disabled={firstChoice === null || confidence === null}
              onClick={() => setStep('probe')}
            >
              답 제출하고 다음 상황 보기
            </Button>
          </CardContent>
        </Card>
      )}

      {step === 'probe' && (
        <Card>
          <CardHeader>
            <h2 className="text-lg font-semibold">숫자를 바꿔서 다시 생각해 볼까요?</h2>
            <p className="text-sm text-muted-foreground">
              첫 답은 {firstChoices[firstChoice!]}였고, 확신도는 {confidence}이었습니다.
              결과 설명은 이 문제를 푼 뒤에 볼 수 있습니다.
            </p>
            <pre className="rounded-md bg-muted p-4 text-sm">{'printf("[%03d]", 42);'}</pre>
          </CardHeader>
          <CardContent className="flex flex-col gap-5">
            <ChoiceGroup
              choices={probeChoices}
              selected={probeChoice}
              onSelect={setProbeChoice}
              label="다른 상황에서의 답"
            />
            <Button
              className="self-end"
              disabled={probeChoice === null}
              onClick={() => setStep('result')}
            >
              두 답 비교하기
            </Button>
          </CardContent>
        </Card>
      )}

      {step === 'result' && (
        <Card>
          <CardHeader>
            <h2 className="text-lg font-semibold">두 상황을 비교해 봅시다</h2>
          </CardHeader>
          <CardContent className="flex flex-col gap-5 text-sm">
            <div className="grid gap-3 sm:grid-cols-2">
              <AnswerSummary
                title="처음 판단"
                chosen={firstChoices[firstChoice!]}
                answer={firstChoices[0]}
                correct={!firstWrong}
              />
              <AnswerSummary
                title="숫자를 바꾼 상황"
                chosen={probeChoices[probeChoice!]}
                answer={probeChoices[0]}
                correct={!probeWrong}
              />
            </div>
            <div className="rounded-md border-l-4 border-primary bg-muted p-4">
              <p className="font-semibold">
                {firstWrong && probeWrong
                  ? '0으로 채우는 규칙을 공백 채우기로 생각했을 가능성이 있습니다.'
                  : firstWrong
                    ? '처음 답은 틀렸지만, 다른 상황에서는 규칙을 적용했습니다. 한 번의 오답으로 오개념을 단정할 수 없습니다.'
                    : '처음 답은 맞았습니다. 다른 숫자에도 같은 규칙을 적용하는지 확인했습니다.'}
              </p>
              <p className="mt-2 leading-relaxed">
                %03d에서 3은 출력 폭, 0은 빈칸을 0으로 채우라는 뜻입니다.
                그래서 7은 007, 42는 042로 출력됩니다.
              </p>
            </div>
            <div className="rounded-md border p-4">
              <p className="font-medium">교안 근거</p>
              <blockquote className="mt-2 border-l-2 border-primary pl-3 text-muted-foreground">
                %03d : 필드 폭을 3칸 확보하고 오른쪽 정렬, 남은 자리는 0으로 채움
              </blockquote>
              <p className="mt-2 text-xs text-muted-foreground">
                기초프로그래밍 샘플 문제에 등록된 교안 문장입니다. 이 시범에는 PDF 원본과 페이지 번호가 연결되지 않았습니다.
              </p>
            </div>
            <p className="text-xs text-muted-foreground">
              이 시범은 점수나 숙련도를 변경하지 않습니다. 실제 기능에서는 다른 문제로 다시 확인해야 합니다.
            </p>
            <Button variant="outline" className="self-end" onClick={reset}>
              다시 체험하기
            </Button>
          </CardContent>
        </Card>
      )}
    </main>
  )
}

function ChoiceGroup({
  choices,
  selected,
  onSelect,
  label,
}: {
  choices: string[]
  selected: number | null
  onSelect: (index: number) => void
  label: string
}) {
  return (
    <div className="flex flex-col gap-2" role="radiogroup" aria-label={label}>
      {choices.map((choice, index) => (
        <button
          key={choice}
          type="button"
          role="radio"
          aria-checked={selected === index}
          onClick={() => onSelect(index)}
          className={cn(
            'rounded-md border px-4 py-3 text-left font-mono transition-colors hover:bg-accent',
            selected === index && 'border-primary bg-primary/10',
          )}
        >
          {choice}
        </button>
      ))}
    </div>
  )
}

function AnswerSummary({
  title,
  chosen,
  answer,
  correct,
}: {
  title: string
  chosen: string
  answer: string
  correct: boolean
}) {
  return (
    <div className="rounded-md border p-4">
      <p className="font-medium">{title}</p>
      <p className={cn('mt-2 font-mono', correct ? 'text-success' : 'text-destructive')}>
        내 답: {chosen} {correct ? '✓' : '✗'}
      </p>
      <p className="mt-1 font-mono">정답: {answer}</p>
    </div>
  )
}

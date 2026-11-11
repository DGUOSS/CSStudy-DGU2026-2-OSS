import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader } from '@/components/ui/card'
import { cn } from '@/lib/utils'

type Confidence = '낮음' | '보통' | '높음'
type Step = 'first' | 'probe' | 'result'

type Probe = {
  hypothesis: string
  question: string
  code: string
  choices: string[]
  answerIndex: number
  explanation: string
  practice: {
    code: string
    choices: string[]
    answerIndex: number
    explanation: string
  }
}

const firstChoices = ['[007]', '[  7]', '[0007]']
const probes: Record<number, Probe> = {
  0: {
    hypothesis: '처음 답은 맞았습니다. 다른 숫자에도 규칙을 적용하는지 확인합니다.',
    question: '숫자를 바꿔도 같은 규칙이 적용될까요?',
    code: 'printf("[%03d]", 42);',
    choices: ['[042]', '[ 42]'],
    answerIndex: 0,
    explanation: '42는 두 자리이므로 폭 3의 남은 한 칸을 0으로 채웁니다.',
    practice: {
      code: 'printf("[%04d]", 8);',
      choices: ['[0008]', '[   8]'],
      answerIndex: 0,
      explanation: '8은 한 자리이므로 부족한 세 칸을 0으로 채웁니다.',
    },
  },
  1: {
    hypothesis: '빈칸을 0 대신 공백으로 채운다고 생각했을 가능성이 있습니다.',
    question: '출력 폭을 4로 바꾸면 어떻게 될까요?',
    code: 'printf("[%04d]", 23);',
    choices: ['[  23]', '[0023]'],
    answerIndex: 1,
    explanation: '%04d는 총 4칸을 확보하고 부족한 두 칸을 0으로 채웁니다.',
    practice: {
      code: 'printf("[%05d]", 12);',
      choices: ['[   12]', '[00012]'],
      answerIndex: 1,
      explanation: '12는 두 자리이므로 부족한 세 칸을 0으로 채웁니다.',
    },
  },
  2: {
    hypothesis: '출력 폭을 숫자 앞에 더하는 0의 개수로 생각했을 가능성이 있습니다.',
    question: '숫자가 이미 출력 폭보다 길다면 어떻게 될까요?',
    code: 'printf("[%03d]", 1234);',
    choices: ['[0001234]', '[1234]'],
    answerIndex: 1,
    explanation: '폭 3은 최소 너비입니다. 이미 네 자리인 1234 앞에는 0을 추가하지 않습니다.',
    practice: {
      code: 'printf("[%02d]", 123);',
      choices: ['[123]', '[00123]'],
      answerIndex: 0,
      explanation: '123은 이미 최소 출력 폭 2보다 길어 0을 더하지 않습니다.',
    },
  },
}

function diagnosis(firstChoice: number, probeCorrect: boolean, confidence: Confidence) {
  if (firstChoice === 0) {
    return probeCorrect
      ? {
          title: '두 상황에서 규칙을 적용했습니다',
          detail: '이번 두 답은 맞았습니다. 다른 형식 지정자까지 이해했다고 단정할 수는 없습니다.',
        }
      : {
          title: '추가 확인이 필요합니다',
          detail: '첫 답은 맞았지만 다른 숫자에서는 규칙을 적용하지 못했습니다. 첫 정답만으로 이해를 확정하기 어렵습니다.',
        }
  }
  return probeCorrect
    ? {
        title: '다른 상황에서는 규칙을 적용했습니다',
        detail: '처음 답은 틀렸지만 확인 문제는 맞았습니다. 한 번의 오답으로 오개념을 확정할 수 없습니다.',
      }
    : {
        title: '이 생각을 다시 확인해 보세요',
        detail: `두 상황에서 같은 규칙을 잘못 적용했습니다. 처음 답에 대한 확신도는 '${confidence}'였습니다. 오개념 가능성이 있지만, 실제 진단에는 별도의 문제로 추가 확인이 필요합니다.`,
      }
}

export function MisconceptionLabPage() {
  const [step, setStep] = useState<Step>('first')
  const [firstChoice, setFirstChoice] = useState<number | null>(null)
  const [confidence, setConfidence] = useState<Confidence | null>(null)
  const [probeChoice, setProbeChoice] = useState<number | null>(null)
  const [practiceChoice, setPracticeChoice] = useState<number | null>(null)

  const reset = () => {
    setStep('first')
    setFirstChoice(null)
    setConfidence(null)
    setProbeChoice(null)
    setPracticeChoice(null)
  }

  const probe = firstChoice === null ? null : probes[firstChoice]
  const probeCorrect = probe !== null && probeChoice === probe.answerIndex
  const result = firstChoice !== null && confidence !== null
    ? diagnosis(firstChoice, probeCorrect, confidence)
    : null

  return (
    <main className="mx-auto flex min-h-screen max-w-3xl flex-col gap-6 px-4 py-10 sm:px-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-sm font-medium text-primary">기능 시범</p>
          <h1 className="mt-1 text-2xl font-bold">오개념 반례 실험실</h1>
          <p className="mt-2 text-sm text-muted-foreground">
            기초프로그래밍의 printf 형식 지정자를 활용한 시범 문제입니다. 답변은 저장되지 않습니다.
          </p>
        </div>
        <a href="https://dgu-study.vercel.app/" className="text-sm text-primary underline">
          동국 스터디로 돌아가기
        </a>
      </div>

      <div className="flex gap-2 text-xs sm:text-sm" aria-label="진행 단계">
        {['1. 처음 판단', '2. 확인 문제', '3. 생각 정리'].map((label, index) => (
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
              답 제출하고 확인 문제 보기
            </Button>
          </CardContent>
        </Card>
      )}

      {step === 'probe' && probe && (
        <Card>
          <CardHeader>
            <h2 className="text-lg font-semibold">{probe.question}</h2>
            <p className="text-sm text-muted-foreground">
              첫 답은 {firstChoices[firstChoice!]}였고, 확신도는 {confidence}이었습니다.
              결과 설명은 이 문제를 푼 뒤에 볼 수 있습니다.
            </p>
            <pre className="rounded-md bg-muted p-4 text-sm">{probe.code}</pre>
          </CardHeader>
          <CardContent className="flex flex-col gap-5">
            <ChoiceGroup
              choices={probe.choices}
              selected={probeChoice}
              onSelect={setProbeChoice}
              label="확인 문제의 답"
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

      {step === 'result' && probe && result && probeChoice !== null && (
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
                correct={firstChoice === 0}
              />
              <AnswerSummary
                title="확인 문제"
                chosen={probe.choices[probeChoice]}
                answer={probe.choices[probe.answerIndex]}
                correct={probeCorrect}
              />
            </div>
            <div className="rounded-md border-l-4 border-primary bg-muted p-4">
              <p className="font-semibold">{result.title}</p>
              <p className="mt-2 leading-relaxed">{result.detail}</p>
              <p className="mt-2 leading-relaxed">{probe.hypothesis}</p>
            </div>
            <div className="rounded-md border p-4">
              <p className="font-medium">규칙과 확인 문제 풀이</p>
              <p className="mt-2 leading-relaxed">
                %03d에서 3은 최소 출력 폭, 0은 부족한 자리를 0으로 채우라는 뜻입니다.
                그래서 7은 007로 출력됩니다. {probe.explanation}
              </p>
              <p className="mt-2 text-xs text-muted-foreground">
                이 시범은 교안 PDF 원본이나 페이지 번호와 연결되지 않았습니다.
              </p>
            </div>
            <div className="flex flex-col gap-3 rounded-md border p-4">
              <p className="font-medium">이제 직접 적용해 보기</p>
              <p className="text-muted-foreground">
                설명을 확인했으니 새 숫자에 규칙을 적용해 보세요. 이 문제는 진단 결과에 반영되지 않습니다.
              </p>
              <pre className="rounded-md bg-muted p-3 font-mono">{probe.practice.code}</pre>
              <ChoiceGroup
                choices={probe.practice.choices}
                selected={practiceChoice}
                onSelect={setPracticeChoice}
                label="복습 문제의 답"
                disabled={practiceChoice !== null}
              />
              {practiceChoice !== null && (
                <p aria-live="polite" className="rounded-md bg-muted p-3 leading-relaxed">
                  <strong>{practiceChoice === probe.practice.answerIndex ? '맞았습니다.' : '다시 복습해 보세요.'}</strong>{' '}
                  정답은 {probe.practice.choices[probe.practice.answerIndex]}입니다.{' '}
                  {probe.practice.explanation}
                </p>
              )}
            </div>
            <p className="text-xs text-muted-foreground">
              이 결과는 학습용 안내이며 점수·숙련도를 변경하지 않습니다.
            </p>
            <Button variant="outline" className="self-end" onClick={reset}>
              다른 답으로 다시 체험하기
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
  disabled = false,
}: {
  choices: string[]
  selected: number | null
  onSelect: (index: number) => void
  label: string
  disabled?: boolean
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
          disabled={disabled}
          className={cn(
            'rounded-md border px-4 py-3 text-left font-mono transition-colors hover:bg-accent disabled:cursor-default',
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

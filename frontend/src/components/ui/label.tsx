import type * as React from 'react'
import { cn } from '@/lib/utils'

export function Label({ className, ...props }: React.ComponentProps<'label'>) {
  return <label className={cn('ui-label text-sm font-medium leading-none', className)} {...props} />
}

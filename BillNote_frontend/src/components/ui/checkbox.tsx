import * as React from 'react'
import { CheckIcon } from 'lucide-react'

import { cn } from '@/lib/utils'

type CheckboxProps = Omit<React.ComponentPropsWithoutRef<'button'>, 'onChange' | 'role'> & {
  checked?: boolean
  defaultChecked?: boolean
  onCheckedChange?: (checked: boolean) => void
}

const Checkbox = React.forwardRef<HTMLButtonElement, CheckboxProps>(
  (
    {
      checked,
      defaultChecked = false,
      disabled = false,
      className,
      onClick,
      onCheckedChange,
      ...props
    },
    ref
  ) => {
    const isControlled = checked !== undefined
    const [uncontrolledChecked, setUncontrolledChecked] = React.useState(defaultChecked)
    const isChecked = isControlled ? checked : uncontrolledChecked

    const handleClick = (event: React.MouseEvent<HTMLButtonElement>) => {
      onClick?.(event)
      if (event.defaultPrevented || disabled) {
        return
      }

      const nextChecked = !isChecked

      if (!isControlled) {
        setUncontrolledChecked(nextChecked)
      }

      onCheckedChange?.(nextChecked)
    }

    return (
      <button
        {...props}
        ref={ref}
        type="button"
        role="checkbox"
        aria-checked={isChecked}
        data-slot="checkbox"
        data-state={isChecked ? 'checked' : 'unchecked'}
        data-disabled={disabled ? '' : undefined}
        disabled={disabled}
        className={cn(
          'peer border-input dark:bg-input/30 data-[state=checked]:bg-primary data-[state=checked]:text-primary-foreground dark:data-[state=checked]:bg-primary data-[state=checked]:border-primary focus-visible:border-ring focus-visible:ring-ring/50 aria-invalid:ring-destructive/20 dark:aria-invalid:ring-destructive/40 aria-invalid:border-destructive size-4 shrink-0 rounded-[4px] border shadow-xs transition-shadow outline-none focus-visible:ring-[3px] disabled:cursor-not-allowed disabled:opacity-50',
          className
        )}
        onClick={handleClick}
      >
        {isChecked ? (
          <span
            data-slot="checkbox-indicator"
            className="flex items-center justify-center text-current transition-none"
          >
            <CheckIcon className="size-3.5" />
          </span>
        ) : null}
      </button>
    )
  }
)

Checkbox.displayName = 'Checkbox'

export { Checkbox }

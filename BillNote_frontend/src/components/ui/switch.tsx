import * as React from 'react'

import { cn } from '@/lib/utils'

type SwitchProps = Omit<React.ComponentPropsWithoutRef<'button'>, 'onChange' | 'role'> & {
  checked?: boolean
  defaultChecked?: boolean
  onCheckedChange?: (checked: boolean) => void
}

const Switch = React.forwardRef<HTMLButtonElement, SwitchProps>(
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
        role="switch"
        aria-checked={isChecked}
        data-slot="switch"
        data-state={isChecked ? 'checked' : 'unchecked'}
        data-disabled={disabled ? '' : undefined}
        disabled={disabled}
        className={cn(
          'peer data-[state=checked]:bg-primary data-[state=unchecked]:bg-input focus-visible:border-ring focus-visible:ring-ring/50 dark:data-[state=unchecked]:bg-input/80 inline-flex h-[1.15rem] w-8 shrink-0 items-center rounded-full border border-transparent shadow-xs transition-all outline-none focus-visible:ring-[3px] disabled:cursor-not-allowed disabled:opacity-50',
          className
        )}
        onClick={handleClick}
      >
        <span
          data-slot="switch-thumb"
          data-state={isChecked ? 'checked' : 'unchecked'}
          className={cn(
            'bg-background dark:data-[state=unchecked]:bg-foreground dark:data-[state=checked]:bg-primary-foreground pointer-events-none block size-4 rounded-full ring-0 transition-transform data-[state=checked]:translate-x-[calc(100%-2px)] data-[state=unchecked]:translate-x-0'
          )}
        />
      </button>
    )
  }
)

Switch.displayName = 'Switch'

export { Switch }

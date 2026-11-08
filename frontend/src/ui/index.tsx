import { cloneElement, forwardRef, useId, type ButtonHTMLAttributes, type HTMLAttributes, type ReactElement, type ReactNode } from 'react'
import './ui.css'

// Base components. Styled only with --dvm-* tokens (ui.css), no dependencies, keyboard accessible.

const cx = (...c: (string | false | undefined)[]) => c.filter(Boolean).join(' ')

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & { variant?: 'filled' | 'outline' | 'ghost' }

/** Text button. `aria-pressed` gives the toggled look. */
export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button({ variant = 'outline', className, type = 'button', ...rest }, ref) {
  return <button ref={ref} type={type} className={cx('dvm-btn', `dvm-btn--${variant}`, className)} {...rest} />
})

type IconButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & { label: string }

/** Square icon button; `label` is its accessible name. */
export const IconButton = forwardRef<HTMLButtonElement, IconButtonProps>(function IconButton({ label, className, type = 'button', ...rest }, ref) {
  return <button ref={ref} type={type} aria-label={label} className={cx('dvm-icon-btn', className)} {...rest} />
})

type ChipProps = HTMLAttributes<HTMLSpanElement> & {
  kind?: 'tag' | 'replay' | 'signal'
  /** For kind="signal": the token that colours the border, e.g. "risk-3" or "ship-dark". */
  signal?: string
}

/** Small mono label: a neutral tag, the inverted-ink REPLAY chip, or a tag bordered in a signal colour. */
export const Chip = forwardRef<HTMLSpanElement, ChipProps>(function Chip({ kind = 'tag', signal, className, style, ...rest }, ref) {
  const sig = kind === 'signal' && signal ? { '--dvm-chip-signal': `var(--dvm-${signal})` } : undefined
  return <span ref={ref} className={cx('dvm-chip', `dvm-chip--${kind}`, className)} style={{ ...sig, ...style }} {...rest} />
})

/** Surface for drop-ins, windows and the login card: bg/panel, 1 px border/default, 4 px radius. */
export const Panel = forwardRef<HTMLDivElement, HTMLAttributes<HTMLDivElement>>(function Panel({ className, ...rest }, ref) {
  return <div ref={ref} className={cx('dvm-panel', className)} {...rest} />
})

export type LampState = 'on' | 'off' | 'na'
const lampText: Record<LampState, string> = { on: 'on', off: 'off', na: 'n/a' }

type LampProps = HTMLAttributes<HTMLSpanElement> & { state: LampState; text?: boolean }

/** Square indicator lamp with its state written out (never colour-only). `text={false}` draws the square alone. */
export const Lamp = forwardRef<HTMLSpanElement, LampProps>(function Lamp({ state, text = true, className, ...rest }, ref) {
  return (
    <span ref={ref} className={cx('dvm-lamp', className)} data-state={state} {...rest}>
      <i aria-hidden="true" />
      {text && lampText[state]}
    </span>
  )
})

type SwitchProps = Omit<ButtonHTMLAttributes<HTMLButtonElement>, 'onChange'> & {
  checked: boolean
  onChange?: (checked: boolean) => void
  label: ReactNode
  hint?: ReactNode
  /** Not available (no data): shows n/a and can't be switched. */
  unavailable?: boolean
}

/** A layers-panel row: lamp (filled = on), label with an optional mono hint; n/a is written out. */
export const Switch = forwardRef<HTMLButtonElement, SwitchProps>(function Switch({ checked, onChange, label, hint, unavailable, className, ...rest }, ref) {
  const state: LampState = unavailable ? 'na' : checked ? 'on' : 'off'
  return (
    <button
      ref={ref}
      type="button"
      role="switch"
      aria-checked={unavailable ? false : checked}
      aria-disabled={unavailable || undefined}
      className={cx('dvm-row', className)}
      data-state={state}
      onClick={() => !unavailable && onChange?.(!checked)}
      {...rest}
    >
      <Lamp state={state} text={false} />
      <span className="dvm-row__text">
        <span className="dvm-row__label">{label}</span>
        {hint && <span className="dvm-row__hint">{hint}</span>}
      </span>
      {state === 'na' && <span className="dvm-row__state" aria-hidden="true">{lampText[state]}</span>}   {/* the lamp already shows on and off */}
    </button>
  )
})

type TooltipProps = { content: ReactNode; side?: 'top' | 'bottom' | 'left' | 'right'; children: ReactElement<{ 'aria-describedby'?: string }> }

/** CSS-positioned tooltip shown on hover and keyboard focus; the child gets aria-describedby. */
export function Tooltip({ content, side = 'top', children }: TooltipProps) {
  const id = useId()
  return (
    <span className="dvm-tip" data-side={side}>
      {cloneElement(children, { 'aria-describedby': id })}
      <span role="tooltip" id={id} className="dvm-tip__body">{content}</span>
    </span>
  )
}

/** Keyboard key. */
export const Kbd = forwardRef<HTMLElement, HTMLAttributes<HTMLElement>>(function Kbd({ className, ...rest }, ref) {
  return <kbd ref={ref} className={cx('dvm-kbd', className)} {...rest} />
})

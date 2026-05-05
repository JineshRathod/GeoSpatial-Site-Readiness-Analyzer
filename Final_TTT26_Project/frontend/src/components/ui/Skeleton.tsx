export function Skeleton({ className = '' }: { className?: string }) {
  return (
    <div
      className={`animate-pulse rounded-lg bg-ui-border/35 ${className}`}
      aria-hidden
    />
  )
}

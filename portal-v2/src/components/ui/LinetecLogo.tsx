import { cn } from '../../lib/utils';

interface LinetecLogoProps {
  /** Visual variant — "full" shows the entire logo, "mark" shows a compact square version */
  variant?: 'full' | 'mark';
  /** Size preset — "sm" for Navbar (h-8), "md" for page headers (h-10), "lg" for login (h-14) */
  size?: 'sm' | 'md' | 'lg';
  /** When true, uses a white/light-backgrounded version suitable for dark hero sections */
  onDark?: boolean;
  className?: string;
}

const sizeClasses = {
  sm: 'h-8',
  md: 'h-10',
  lg: 'h-14',
} as const;

/**
 * Official Linetec Services logo. Renders the full wordmark by default.
 * The asset lives in /public/images so it's served as a static file — no
 * bundler transform, no CORS issues, and it works identically in dev and prod.
 */
export function LinetecLogo({
  variant = 'full',
  size = 'sm',
  onDark = false,
  className,
}: LinetecLogoProps) {
  return (
    <img
      src="/images/linetec-services-logo.png"
      alt="Linetec Services — A Centuri Company"
      className={cn(
        sizeClasses[size],
        'w-auto object-contain select-none',
        // Logo has a transparent background; on dark hero sections we add
        // a subtle white glow so the gray text stays legible.
        onDark && 'drop-shadow-[0_0_12px_rgba(255,255,255,0.25)]',
        variant === 'mark' && 'aspect-square object-cover object-left',
        className
      )}
      draggable={false}
    />
  );
}

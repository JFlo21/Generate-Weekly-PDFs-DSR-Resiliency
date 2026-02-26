import { useEffect, useRef } from 'react';
import { animate } from 'framer-motion';

interface AnimatedCounterProps {
  from?: number;
  to: number;
  duration?: number;
  className?: string;
}

export function AnimatedCounter({
  from = 0,
  to,
  duration = 1.2,
  className,
}: AnimatedCounterProps) {
  const ref = useRef<HTMLSpanElement>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const controls = animate(from, to, {
      duration,
      ease: [0.25, 0.1, 0.25, 1],
      onUpdate(value) {
        el.textContent = Math.round(value).toLocaleString();
      },
    });
    return () => controls.stop();
  }, [from, to, duration]);

  return (
    <span ref={ref} className={className}>
      {from}
    </span>
  );
}

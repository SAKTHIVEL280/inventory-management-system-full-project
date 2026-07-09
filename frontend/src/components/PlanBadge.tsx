/**
 * PlanBadge — color-coded subscription plan pill, consistent across the app.
 */
import { planStyle } from '../utils/planStyles';

interface PlanBadgeProps {
  plan?: string | null;
  size?: 'sm' | 'md' | 'lg';
  className?: string;
}

const SIZES: Record<NonNullable<PlanBadgeProps['size']>, string> = {
  sm: 'px-2 py-0.5 text-xs',
  md: 'px-2.5 py-1 text-xs',
  lg: 'px-3 py-1 text-sm',
};

export const PlanBadge = ({ plan, size = 'md', className = '' }: PlanBadgeProps) => {
  const label = (plan || '—').toUpperCase();
  return (
    <span className={`inline-flex items-center rounded-full font-bold uppercase tracking-wide ${SIZES[size]} ${planStyle(plan).badge} ${className}`}>
      {label}
    </span>
  );
};

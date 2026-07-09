/**
 * Shared subscription-plan visual styling — single source of truth so plan colors
 * are consistent everywhere (Dashboard badge, Super Admin tenant list, Plan
 * Configuration cards). FREE→Gray, SILVER→Silver, GOLD→Gold, PLATINUM→Violet.
 */
export type PlanKey = 'FREE' | 'SILVER' | 'GOLD' | 'PLATINUM';

export interface PlanStyle {
  /** Solid pill badge (text on filled background). */
  badge: string;
  /** Soft/subtle badge (tinted background). */
  soft: string;
  /** Border + tint for a plan card. */
  card: string;
  /** Accent header strip / bar background. */
  accent: string;
  /** Full gradient background for a card header (white text on top). */
  header: string;
  /** Material icon name representing the tier. */
  icon: string;
  /** Small status dot / swatch background. */
  dot: string;
  /** Emphasised text color. */
  text: string;
  /** Ring color used on hover/selected cards. */
  ring: string;
}

const STYLES: Record<PlanKey, PlanStyle> = {
  FREE: {
    badge: 'bg-neutral-200 text-neutral-800',
    soft: 'bg-neutral-100 text-neutral-700',
    card: 'border-neutral-200 bg-neutral-50',
    accent: 'bg-neutral-400',
    header: 'bg-gradient-to-br from-neutral-500 to-neutral-700',
    icon: 'star_outline',
    dot: 'bg-neutral-400',
    text: 'text-neutral-700',
    ring: 'ring-neutral-300',
  },
  SILVER: {
    badge: 'bg-slate-300 text-slate-900',
    soft: 'bg-slate-100 text-slate-700',
    card: 'border-slate-300 bg-slate-50',
    accent: 'bg-gradient-to-r from-slate-300 to-slate-400',
    header: 'bg-gradient-to-br from-slate-400 to-slate-600',
    icon: 'star_half',
    dot: 'bg-slate-400',
    text: 'text-slate-700',
    ring: 'ring-slate-400',
  },
  GOLD: {
    badge: 'bg-amber-300 text-amber-950',
    soft: 'bg-amber-100 text-amber-800',
    card: 'border-amber-300 bg-amber-50',
    accent: 'bg-gradient-to-r from-amber-300 to-yellow-400',
    header: 'bg-gradient-to-br from-amber-400 to-yellow-600',
    icon: 'star',
    dot: 'bg-amber-400',
    text: 'text-amber-800',
    ring: 'ring-amber-400',
  },
  PLATINUM: {
    badge: 'bg-violet-200 text-violet-900',
    soft: 'bg-violet-100 text-violet-800',
    card: 'border-violet-300 bg-violet-50',
    accent: 'bg-gradient-to-r from-violet-400 to-fuchsia-500',
    header: 'bg-gradient-to-br from-violet-500 to-fuchsia-600',
    icon: 'workspace_premium',
    dot: 'bg-violet-500',
    text: 'text-violet-800',
    ring: 'ring-violet-400',
  },
};

const FALLBACK: PlanStyle = STYLES.FREE;

export const planStyle = (plan?: string | null): PlanStyle => {
  const key = (plan || '').trim().toUpperCase() as PlanKey;
  return STYLES[key] ?? FALLBACK;
};

/** Convenience: the solid pill badge classes for a plan. */
export const planBadgeClass = (plan?: string | null): string => planStyle(plan).badge;

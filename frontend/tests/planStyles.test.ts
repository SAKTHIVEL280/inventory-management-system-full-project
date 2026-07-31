import { describe, it, expect } from 'vitest';
import { planStyle, planBadgeClass } from '../src/utils/planStyles';

describe('planStyle', () => {
  it('returns a distinct badge class per plan', () => {
    expect(planStyle('FREE').badge).toBeTypeOf('string');
    expect(planStyle('SILVER').badge).not.toBe(planStyle('GOLD').badge);
    expect(planStyle('PLATINUM').badge).toContain('violet');
  });

  it('is case-insensitive', () => {
    expect(planStyle('gold').badge).toBe(planStyle('GOLD').badge);
  });

  it('falls back to the FREE style for unknown / empty plans', () => {
    expect(planStyle('nonsense').badge).toBe(planStyle('FREE').badge);
    expect(planStyle(null).badge).toBe(planStyle('FREE').badge);
    expect(planStyle(undefined).badge).toBe(planStyle('FREE').badge);
  });

  it('planBadgeClass matches planStyle().badge', () => {
    expect(planBadgeClass('GOLD')).toBe(planStyle('GOLD').badge);
  });
});

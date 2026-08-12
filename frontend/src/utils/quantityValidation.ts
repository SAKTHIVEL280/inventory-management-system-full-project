// Whole-number quantity validation shared by the Product, Purchase Order, GRN and
// Sales forms. Physical stock is counted in whole units, so fractional quantities
// are rejected. Mirrors backend app/utils/quantity_validation.py.

export const WHOLE_QTY_MESSAGE = 'Quantity must be a whole number (decimals are not allowed)';

/** True when value is empty/whole; false when it carries a fractional part. */
export const isWholeQuantity = (value: number | string | null | undefined): boolean => {
  if (value === null || value === undefined || value === '') return true;
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return false;
  return Number.isInteger(numeric);
};

/**
 * Parse a raw input value to a whole number for controlled quantity inputs.
 * Non-numeric -> 0. Fractional input is truncated so the field can never hold a
 * decimal; submit-time validation still guards against any stray value.
 */
export const parseWholeQuantity = (raw: string): number => {
  const numeric = parseInt(raw, 10);
  return Number.isFinite(numeric) ? numeric : 0;
};

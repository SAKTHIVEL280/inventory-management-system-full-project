const DATE_INPUT_REGEX = /^(\d{4})-(\d{2})-(\d{2})$/;

export const toLocalDateInputValue = (date: Date): string => {
  const local = new Date(date);
  local.setMinutes(local.getMinutes() - local.getTimezoneOffset());
  return local.toISOString().split('T')[0];
};

export const todayLocalDateInputValue = (): string => toLocalDateInputValue(new Date());

export const todayUtcDateInputValue = (): string => new Date().toISOString().slice(0, 10);

export const dateInputValueAfterDays = (days: number): string => {
  const date = new Date();
  date.setDate(date.getDate() + days);
  return toLocalDateInputValue(date);
};

const parseDateInputValue = (dateInputValue: string): Date | null => {
  const match = DATE_INPUT_REGEX.exec(dateInputValue);
  if (!match) {
    return null;
  }

  const year = Number(match[1]);
  const month = Number(match[2]);
  const day = Number(match[3]);
  const parsed = new Date(year, month - 1, day);

  if (
    Number.isNaN(parsed.getTime()) ||
    parsed.getFullYear() !== year ||
    parsed.getMonth() !== month - 1 ||
    parsed.getDate() !== day
  ) {
    return null;
  }

  return parsed;
};

export const addDaysToDateInputValue = (dateInputValue: string, days: number): string => {
  const parsed = parseDateInputValue(dateInputValue);
  if (!parsed) {
    return dateInputValue;
  }

  parsed.setDate(parsed.getDate() + days);
  return toLocalDateInputValue(parsed);
};

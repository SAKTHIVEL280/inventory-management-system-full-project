export const emptyWhenZero = (value: number | null | undefined): number | '' => {
  if (value === null || value === undefined || value === 0) {
    return '';
  }
  return value;
};

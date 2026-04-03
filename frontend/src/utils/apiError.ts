export interface ApiFieldError {
  msg?: string;
  message?: string;
  loc?: Array<string | number>;
  type?: string;
  [key: string]: unknown;
}

export interface ApiObjectDetail {
  message?: string;
  error?: string;
  error_code?: string;
  [key: string]: unknown;
}

export type ApiDetail = string | ApiFieldError[] | ApiObjectDetail | undefined;

interface ApiLikeError {
  response?: {
    data?: {
      detail?: ApiDetail;
    };
  };
}

export const getApiDetail = (error: unknown): ApiDetail => {
  return (error as ApiLikeError)?.response?.data?.detail;
};

export const getApiDetailMessage = (detail: ApiDetail, fallback: string): string => {
  if (typeof detail === 'string' && detail.trim()) {
    return detail;
  }

  if (Array.isArray(detail)) {
    const messages = detail
      .map((d) => d.msg || d.message)
      .filter((m): m is string => Boolean(m && m.trim()));
    if (messages.length > 0) {
      return messages.join(', ');
    }
  }

  if (detail && typeof detail === 'object' && !Array.isArray(detail)) {
    if (typeof detail.message === 'string' && detail.message.trim()) {
      return detail.message;
    }
    if (typeof detail.error === 'string' && detail.error.trim()) {
      return detail.error;
    }
  }

  return fallback;
};

import axios from 'axios';
export function apiErrorMessage(error: unknown, fallback: string): string {
  if (axios.isAxiosError<{ detail?: unknown }>(error)) {
    const detail = error.response?.data?.detail;
    if (typeof detail === 'string') return detail;
    if (detail && typeof detail === 'object' && 'message' in detail && typeof detail.message === 'string') return detail.message;
  }
  return fallback;
}

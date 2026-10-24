// VITE_API_URL is the backend origin (optionally with a deployment path prefix).
// Keep HTTP and SSE on the same configured backend.
export const API_URL = `${(import.meta.env.VITE_API_URL || 'http://localhost:8000').replace(/\/+$/, '')}/api/v1`;

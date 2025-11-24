import axios from 'axios';

// Use environment variable if available, fallback to localhost for local dev
const API_URL = import.meta.env.VITE_API_URL 
  ? `${import.meta.env.VITE_API_URL}/api/v1`
  : 'http://localhost:8000/api/v1';

export const api = axios.create({
  baseURL: API_URL,
});

// Add interceptor to add token to requests
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// Add interceptor to handle 401s
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401 || error.response?.status === 403) {
      localStorage.removeItem('token');
      localStorage.removeItem('user');
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

export const loginUser = async (email: string, password: string) => {
  const formData = new FormData();
  formData.append('username', email);
  formData.append('password', password);
  const response = await axios.post(`${API_URL}/auth/token`, formData);
  return response.data;
};

export const getMe = async () => {
  const response = await api.get('/auth/me');
  return response.data;
};

export const registerUser = async (email: string, password: string) => {
  const response = await axios.post(`${API_URL}/auth/register`, { email, password });
  return response.data;
};

export const getBins = async () => {
  const response = await api.get('/bins/');
  return response.data;
};

export const createBin = async (name: string, description?: string) => {
  const response = await api.post('/bins/', { name, description });
  return response.data;
};

export const updateBin = async (binId: string, name?: string, description?: string) => {
  const response = await api.patch(`/bins/${binId}`, { name, description });
  return response.data;
};

export const deleteBin = async (binId: string) => {
  const response = await api.delete(`/bins/${binId}`);
  return response.data;
};

export const getBinFiles = async (binId: string) => {
  const response = await api.get(`/bins/${binId}/files`);
  return response.data;
};

export const deleteDocument = async (docId: string) => {
  const response = await api.delete(`/bins/documents/${docId}`);
  return response.data;
};

export const resyncBin = async (binId: string) => {
  const response = await api.post(`/bins/${binId}/resync`);
  return response.data;
};

export const uploadDocument = async (file: File, binId: string) => {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('bin_id', binId);
  
  const response = await api.post('/upload', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  });
  return response.data;
};

// --- Profiles API ---

export const getProfiles = async () => {
  const response = await api.get('/profiles/');
  return response.data;
};

export const getProfile = async (id: string) => {
  const response = await api.get(`/profiles/${id}`);
  return response.data;
};

export const createProfile = async (name: string, description: string, toneUrls: string[]) => {
  const response = await api.post('/profiles/', { name, description, tone_urls: toneUrls });
  return response.data;
};

export const updateProfile = async (id: string, data: { name?: string; description?: string; tone_urls?: string[]; style_dna?: any }) => {
  const response = await api.put(`/profiles/${id}`, data);
  return response.data;
};

export const deleteProfile = async (id: string) => {
  const response = await api.delete(`/profiles/${id}`);
  return response.data;
};

// --- Agent API ---

export const runAgent = async (payload: {
  topic: string;
  tone_urls?: string[];
  profile_id?: string;
  selected_bins: string[];
  target_domain?: string;
  use_local?: boolean;
  model_provider?: string;
  model_name?: string;
  style_profile?: any;
  research_sources?: string[]; // ['web', 'social', 'academic', 'internal']
}) => {
  // Note: This is now mostly used for testing, as the real app uses SSE via fetch/EventSource
  // But we might keep it for non-streaming calls if needed, or remove it.
  // The SSE implementation is in useAgentStream hook.
  // We'll update this to match the new schema just in case.
  const response = await api.post('/agent/stream', payload); 
  return response.data;
};

export const resumeAgent = async (threadId: string, approvedOutline: any[]) => {
  const response = await api.post('/agent/resume', {
    thread_id: threadId,
    approved_outline: approvedOutline,
  });
  return response.data;
};

export const analyzeStyle = async (urls: string[], useLocal: boolean = false) => {
  const response = await api.post('/agent/analyze-style', { urls, use_local: useLocal });
  return response.data;
};

export const getAgentState = async (threadId: string) => {
  const response = await api.get(`/agent/state/${threadId}`);
  return response.data;
};

// --- Threads API ---

export const getThreads = async (skip: number = 0, limit: number = 20) => {
  const response = await api.get(`/threads/?skip=${skip}&limit=${limit}`);
  return response.data;
};

export const getThread = async (threadId: string) => {
  const response = await api.get(`/threads/${threadId}`);
  return response.data;
};

import axios from 'axios';
import { API_URL } from './apiConfig';

// Use environment variable if available, fallback to localhost for local dev

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
    if (error.response?.status === 401) {
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

export const getAuthConfig = async (): Promise<{ allow_registration: boolean }> => {
  const response = await axios.get(`${API_URL}/auth/config`);
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

export const updateProfile = async (id: string, data: { name?: string; description?: string; tone_urls?: string[]; style_dna?: Record<string, unknown> }) => {
  const response = await api.put(`/profiles/${id}`, data);
  return response.data;
};

export const deleteProfile = async (id: string) => {
  const response = await api.delete(`/profiles/${id}`);
  return response.data;
};

// --- Agent API ---

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

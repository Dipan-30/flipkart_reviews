import api from './api';
import type { TokenResponse, User } from '../types/auth';

export const authService = {
  async register(data: any): Promise<TokenResponse> {
    const response = await api.post('/auth/register', data);
    return response.data;
  },

  async login(data: any): Promise<TokenResponse> {
    const response = await api.post('/auth/login', data);
    return response.data;
  },

  async getMe(): Promise<User> {
    const response = await api.get('/auth/me');
    return response.data;
  },

  async logout(): Promise<void> {
    await api.post('/auth/logout');
  }
};

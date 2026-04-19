import axios from 'axios';
import { VerificationResult } from '../types';

export interface GenerateResponse {
  image_b64: string;
  watermark_id: string;
  model?: string;
}

export const apiClient = axios.create({
  baseURL: '/',
});

export async function generateImage(prompt: string, modelId: string): Promise<GenerateResponse> {
  const { data } = await apiClient.post('/generate', { prompt, model: modelId });
  return data;
}

export async function verifyImage(file: File): Promise<VerificationResult> {
  const formData = new FormData();
  formData.append('file', file);
  const { data } = await apiClient.post('/verify', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return data;
}

export function downloadWatermarkedImage(watermarkId: string): void {
  window.open(`/download/${watermarkId}`, '_blank');
}

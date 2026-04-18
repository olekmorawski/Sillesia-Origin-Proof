import { VALID_IMAGE_TYPES } from '../constants';

export function isValidImageFile(file: File): boolean {
  return VALID_IMAGE_TYPES.includes(file.type);
}

export function getImageTypeLabel(type: string): string {
  return type === 'image/png' ? 'PNG' : type === 'image/jpeg' ? 'JPEG' : 'Image';
}

export function extractModelName(modelId: string): string {
  return modelId.split('/').pop() || modelId;
}

export function formatAddress(address: string, chars = 6): string {
  return `${address.slice(0, chars)}…${address.slice(-4)}`;
}

export function formatDate(dateString: string): string {
  return new Date(dateString).toLocaleString();
}

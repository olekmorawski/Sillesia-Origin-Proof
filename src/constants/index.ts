import { AIModel } from '../types';

export const PROGRESS_PHASES = [
  { label: 'Refining prompt', duration: 8000 },
  { label: 'Generating image', duration: 62000 },
  { label: 'Embedding watermark', duration: 10000 },
  { label: 'Anchoring on-chain', duration: Infinity },
];

export const MODELS: AIModel[] = [
  { id: 'black-forest-labs/flux.2-klein-4b', name: 'Flux.2 Klein', provider: 'Black Forest Labs' },
];

export const VALID_IMAGE_TYPES = ['image/png', 'image/jpeg'];

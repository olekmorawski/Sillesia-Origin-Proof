import { useReducer, Dispatch } from 'react';
import { Mode, VerificationResult, AIModel } from '../types';
import { MODELS } from '../constants';

export interface AppState {
  mode: Mode;
  imageB64: string | null;
  isLoading: boolean;
  status: string;
  watermarkId: string | null;
  verifyResult: VerificationResult | null;
  isDragging: boolean;
  selectedModel: AIModel;
  generatedModel: string | null;
}

export type AppAction =
  | { type: 'SET_MODE'; payload: Mode }
  | { type: 'SET_IMAGE'; payload: string | null }
  | { type: 'SET_LOADING'; payload: boolean }
  | { type: 'SET_STATUS'; payload: string }
  | { type: 'SET_WATERMARK_ID'; payload: string | null }
  | { type: 'SET_VERIFY_RESULT'; payload: VerificationResult | null }
  | { type: 'SET_DRAGGING'; payload: boolean }
  | { type: 'SET_SELECTED_MODEL'; payload: AIModel }
  | { type: 'SET_GENERATED_MODEL'; payload: string | null }
  | { type: 'RESET_GENERATE' }
  | { type: 'RESET_VERIFY' };

function appReducer(state: AppState, action: AppAction): AppState {
  switch (action.type) {
    case 'SET_MODE':
      return { ...state, mode: action.payload };
    case 'SET_IMAGE':
      return { ...state, imageB64: action.payload };
    case 'SET_LOADING':
      return { ...state, isLoading: action.payload };
    case 'SET_STATUS':
      return { ...state, status: action.payload };
    case 'SET_WATERMARK_ID':
      return { ...state, watermarkId: action.payload };
    case 'SET_VERIFY_RESULT':
      return { ...state, verifyResult: action.payload };
    case 'SET_DRAGGING':
      return { ...state, isDragging: action.payload };
    case 'SET_SELECTED_MODEL':
      return { ...state, selectedModel: action.payload };
    case 'SET_GENERATED_MODEL':
      return { ...state, generatedModel: action.payload };
    case 'RESET_GENERATE':
      return { ...state, imageB64: null, watermarkId: null, generatedModel: null };
    case 'RESET_VERIFY':
      return { ...state, verifyResult: null };
    default:
      return state;
  }
}

const initialState: AppState = {
  mode: 'generate',
  imageB64: null,
  isLoading: false,
  status: '',
  watermarkId: null,
  verifyResult: null,
  isDragging: false,
  selectedModel: MODELS[0],
  generatedModel: null,
};

export function useAppState(): [AppState, Dispatch<AppAction>] {
  return useReducer(appReducer, initialState);
}

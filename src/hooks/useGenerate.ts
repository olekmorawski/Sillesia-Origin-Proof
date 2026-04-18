import { useCallback, Dispatch } from 'react';
import { generateImage } from '../utils/api';
import { PROGRESS_PHASES } from '../constants';
import { AppAction } from './useAppState';

export function useGenerate(dispatch: Dispatch<AppAction>) {
  const handleGenerate = useCallback(
    async (prompt: string, modelId: string) => {
      dispatch({ type: 'SET_LOADING', payload: true });
      dispatch({ type: 'SET_IMAGE', payload: null });
      dispatch({ type: 'SET_WATERMARK_ID', payload: null });

      let phaseIndex = 0;
      dispatch({ type: 'SET_STATUS', payload: PROGRESS_PHASES[0].label });

      const interval = setInterval(() => {
        phaseIndex++;
        if (phaseIndex < PROGRESS_PHASES.length - 1) {
          dispatch({ type: 'SET_STATUS', payload: PROGRESS_PHASES[phaseIndex].label });
        }
      }, 10000);

      try {
        const data = await generateImage(prompt, modelId);
        dispatch({ type: 'SET_IMAGE', payload: data.image_b64 });
        dispatch({ type: 'SET_WATERMARK_ID', payload: data.watermark_id });
        dispatch({ type: 'SET_GENERATED_MODEL', payload: data.model || modelId });
      } catch (err) {
        console.error('Generate error:', err);
      } finally {
        clearInterval(interval);
        dispatch({ type: 'SET_LOADING', payload: false });
        dispatch({ type: 'SET_STATUS', payload: '' });
      }
    },
    [dispatch]
  );

  return { handleGenerate };
}

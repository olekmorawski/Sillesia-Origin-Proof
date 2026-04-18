import { useCallback, Dispatch } from 'react';
import { verifyImage, downloadWatermarkedImage } from '../utils/api';
import { isValidImageFile } from '../utils/file';
import { AppAction } from './useAppState';

export function useVerify(dispatch: Dispatch<AppAction>) {
  const handleVerify = useCallback(
    async (file: File) => {
      if (!isValidImageFile(file)) {
        console.error('Invalid image file');
        return;
      }

      dispatch({ type: 'SET_LOADING', payload: true });
      dispatch({ type: 'SET_VERIFY_RESULT', payload: null });
      dispatch({ type: 'SET_STATUS', payload: 'Verifying provenance' });

      try {
        const data = await verifyImage(file);
        dispatch({ type: 'SET_VERIFY_RESULT', payload: data });
      } catch (err) {
        console.error('Verify error:', err);
      } finally {
        dispatch({ type: 'SET_LOADING', payload: false });
        dispatch({ type: 'SET_STATUS', payload: '' });
      }
    },
    [dispatch]
  );

  const handleDownload = useCallback(
    (watermarkId: string) => {
      downloadWatermarkedImage(watermarkId);
    },
    []
  );

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      dispatch({ type: 'SET_DRAGGING', payload: false });
      const file = e.dataTransfer.files[0];
      if (file && isValidImageFile(file)) {
        handleVerify(file);
      }
    },
    [dispatch, handleVerify]
  );

  return { handleVerify, handleDownload, handleDrop };
}

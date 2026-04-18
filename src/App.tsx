import React, { useRef } from 'react';
import { useAppState } from '../../../Origin Proof/src/hooks/useAppState';
import { useGenerate } from '../../../Origin Proof/src/hooks/useGenerate';
import { useVerify } from '../../../Origin Proof/src/hooks/useVerify';
import { Navigation } from './components/Navigation';
import { GenerateView } from './components/Generate/GenerateView';
import { VerifyView } from './components/Verify/VerifyView';

export default function App() {
  const [state, dispatch] = useAppState();
  const { handleGenerate } = useGenerate(dispatch);
  const { handleVerify, handleDownload, handleDrop } = useVerify(dispatch);
  const fileInputRef = useRef<HTMLInputElement>(null);

  return (
    <div className="h-screen w-screen bg-[#0a0a0a] flex flex-col relative overflow-hidden font-sans">
      <Navigation
        currentMode={state.mode}
        onModeChange={(mode) => dispatch({ type: 'SET_MODE', payload: mode })}
        dispatch={dispatch}
      />

      <main className="flex-1 relative flex items-center justify-center">
        {state.mode === 'generate' ? (
          <GenerateView
            imageB64={state.imageB64}
            isLoading={state.isLoading}
            status={state.status}
            watermarkId={state.watermarkId}
            generatedModel={state.generatedModel}
            selectedModel={state.selectedModel}
            onModelChange={(model) => dispatch({ type: 'SET_SELECTED_MODEL', payload: model })}
            onGenerate={handleGenerate}
            onDownload={() => state.watermarkId && handleDownload(state.watermarkId)}
          />
        ) : (
          <VerifyView
            verifyResult={state.verifyResult}
            isLoading={state.isLoading}
            isDragging={state.isDragging}
            fileInputRef={fileInputRef}
            onVerify={handleVerify}
            onDragEnter={() => dispatch({ type: 'SET_DRAGGING', payload: true })}
            onDragLeave={() => dispatch({ type: 'SET_DRAGGING', payload: false })}
            onDrop={handleDrop}
            onReset={() => dispatch({ type: 'SET_VERIFY_RESULT', payload: null })}
          />
        )}
      </main>
    </div>
  );
}
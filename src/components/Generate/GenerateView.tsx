import React from 'react';
import { AIModel } from '../../../../../Origin Proof/src/types';
import { ImageDisplay } from './ImageDisplay';
import { PromptBar } from './PromptBar';

interface GenerateViewProps {
  imageB64: string | null;
  isLoading: boolean;
  status: string;
  watermarkId: string | null;
  generatedModel: string | null;
  selectedModel: AIModel;
  onModelChange: (model: AIModel) => void;
  onGenerate: (prompt: string, modelId: string) => void;
  onDownload: () => void;
}

export function GenerateView({
  imageB64,
  isLoading,
  status,
  watermarkId,
  generatedModel,
  selectedModel,
  onModelChange,
  onGenerate,
  onDownload,
}: GenerateViewProps) {
  const handlePromptSubmit = (prompt: string) => {
    onGenerate(prompt, selectedModel.id);
  };

  return (
    <>
      <ImageDisplay
        imageB64={imageB64}
        isLoading={isLoading}
        status={status}
        generatedModel={generatedModel}
        watermarkId={watermarkId}
        onDownload={onDownload}
      />
      <PromptBar
        selectedModel={selectedModel}
        isLoading={isLoading}
        onModelChange={onModelChange}
        onSubmit={handlePromptSubmit}
      />
    </>
  );
}

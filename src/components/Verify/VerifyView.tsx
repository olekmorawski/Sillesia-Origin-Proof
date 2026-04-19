import React from 'react';
import { VerificationResult } from '../../types';
import { UploadZone } from './UploadZone';
import { ResultDisplay } from './ResultDisplay';

interface VerifyViewProps {
  verifyResult: VerificationResult | null;
  isLoading: boolean;
  isDragging: boolean;
  fileInputRef: React.RefObject<HTMLInputElement>;
  onVerify: (file: File) => void;
  onDragEnter: () => void;
  onDragLeave: () => void;
  onDrop: (e: React.DragEvent) => void;
  onReset: () => void;
}

export function VerifyView({
  verifyResult,
  isLoading,
  isDragging,
  fileInputRef,
  onVerify,
  onDragEnter,
  onDragLeave,
  onDrop,
  onReset,
}: VerifyViewProps) {
  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    onDragEnter();
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      fileInputRef.current?.click();
    }
  };

  return (
    <div className="flex flex-col items-center gap-8 w-full max-w-2xl px-6">
      {!verifyResult ? (
        <UploadZone
          isLoading={isLoading}
          isDragging={isDragging}
          fileInputRef={fileInputRef}
          onDragOver={handleDragOver}
          onDragLeave={onDragLeave}
          onDrop={onDrop}
          onClick={() => fileInputRef.current?.click()}
          onFileSelect={onVerify}
          onKeyDown={handleKeyDown}
        />
      ) : (
        <ResultDisplay verifyResult={verifyResult} onReset={onReset} />
      )}
    </div>
  );
}

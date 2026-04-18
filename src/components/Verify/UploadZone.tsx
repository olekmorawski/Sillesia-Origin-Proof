import React from 'react';
import { Upload, FileSearch } from 'lucide-react';

interface UploadZoneProps {
  isLoading: boolean;
  isDragging: boolean;
  fileInputRef: React.RefObject<HTMLInputElement>;
  onDragOver: (e: React.DragEvent) => void;
  onDragLeave: (e: React.DragEvent) => void;
  onDrop: (e: React.DragEvent) => void;
  onClick: () => void;
  onFileSelect: (file: File) => void;
  onKeyDown: (e: React.KeyboardEvent) => void;
}

export function UploadZone({
  isLoading,
  isDragging,
  fileInputRef,
  onDragOver,
  onDragLeave,
  onDrop,
  onClick,
  onFileSelect,
  onKeyDown,
}: UploadZoneProps) {
  return (
    <div
      role="button"
      tabIndex={0}
      onDragOver={onDragOver}
      onDragLeave={onDragLeave}
      onDrop={onDrop}
      onClick={onClick}
      onKeyDown={onKeyDown}
      className={`w-full aspect-[4/3] rounded-3xl border-2 border-dashed transition-all cursor-pointer flex flex-col items-center justify-center gap-6 ${
        isDragging
          ? 'border-white bg-white/[0.05]'
          : 'border-white/[0.1] hover:border-white/[0.2] bg-white/[0.01]'
      }`}
    >
      <div
        className={`p-6 rounded-2xl backdrop-blur-sm ${isLoading ? 'animate-pulse' : ''} ${
          isDragging ? 'bg-white/10' : 'bg-white/[0.03]'
        }`}
      >
        {isLoading ? (
          <FileSearch size={48} className="text-white" />
        ) : (
          <Upload size={48} className="text-white/30" />
        )}
      </div>
      <div className="text-center">
        <p className="text-lg font-medium text-white/80">Drop PNG or JPEG to Verify</p>
        <p className="text-sm text-white/30 mt-1">Check cryptographic provenance</p>
      </div>
      <input
        ref={fileInputRef}
        type="file"
        accept="image/png,image/jpeg"
        className="hidden"
        onChange={(e) => e.target.files?.[0] && onFileSelect(e.target.files[0])}
      />
      <span className="text-xs uppercase tracking-widest text-white/40 hover:text-white/60 transition-colors">
        or click to browse
      </span>
    </div>
  );
}

import React from 'react';
import { Loader2, ImageIcon, Download } from 'lucide-react';
import { extractModelName } from '../../../../../Origin Proof/src/utils/file';

interface ImageDisplayProps {
  imageB64: string | null;
  isLoading: boolean;
  status: string;
  generatedModel: string | null;
  watermarkId: string | null;
  onDownload: () => void;
}

export function ImageDisplay({
  imageB64,
  isLoading,
  status,
  generatedModel,
  watermarkId,
  onDownload,
}: ImageDisplayProps) {
  return (
    <div className="w-full h-full flex items-center justify-center p-20">
      {imageB64 ? (
        <div className="relative animate-in fade-in duration-700">
          <img
            src={`data:image/png;base64,${imageB64}`}
            alt="Generated AI Art"
            className="max-h-[80vh] max-w-[80vw] object-contain rounded-lg shadow-2xl"
          />
          {/* Metadata Badge */}
          <div className="absolute top-4 left-4 px-3 py-1.5 rounded-md bg-black/60 backdrop-blur-md border border-white/10 text-[10px] font-medium tracking-widest text-white/70 uppercase">
            {generatedModel ? extractModelName(generatedModel) : 'Flux.2 Pro'} • Base Sepolia
          </div>
          {/* Download Button */}
          {watermarkId && (
            <button
              onClick={onDownload}
              className="absolute bottom-4 right-4 flex items-center gap-2 px-4 py-2 rounded-lg bg-white/10 backdrop-blur-md border border-white/20 text-sm font-medium text-white hover:bg-white/20 transition-all"
            >
              <Download size={16} />
              Download
            </button>
          )}
        </div>
      ) : (
        <div className="flex flex-col items-center gap-6 text-white/10">
          {isLoading ? (
            <>
              <Loader2 size={48} className="animate-spin" />
              <p className="text-sm font-medium tracking-widest uppercase text-white/40">
                {status || 'Processing...'}
              </p>
            </>
          ) : (
            <>
              <ImageIcon size={64} strokeWidth={1} />
              <p className="text-sm uppercase tracking-[0.2em]">Ready to generate</p>
            </>
          )}
        </div>
      )}
    </div>
  );
}

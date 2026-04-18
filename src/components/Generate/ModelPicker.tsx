import React from 'react';
import { ChevronDown, CheckCircle2, Settings2 } from 'lucide-react';
import { AIModel } from '../../../../../Origin Proof/src/types';
import { MODELS } from '../../../../../Origin Proof/src/constants';

interface ModelPickerProps {
  selectedModel: AIModel;
  isOpen: boolean;
  isLoading: boolean;
  onToggle: (open: boolean) => void;
  onSelectModel: (model: AIModel) => void;
}

export function ModelPicker({
  selectedModel,
  isOpen,
  isLoading,
  onToggle,
  onSelectModel,
}: ModelPickerProps) {
  return (
    <>
      <button
        type="button"
        onClick={() => onToggle(!isOpen)}
        disabled={isLoading}
        className="flex items-center gap-2 px-3 py-2 rounded-lg bg-white/[0.05] border border-white/[0.1] text-sm text-white/70 hover:text-white hover:bg-white/[0.1] transition-all"
      >
        <Settings2 size={14} />
        <span className="max-w-[120px] truncate">{selectedModel.name}</span>
        <ChevronDown size={14} className={`transition-transform ${isOpen ? 'rotate-180' : ''}`} />
      </button>

      {isOpen && (
        <div className="absolute bottom-full left-0 mb-2 w-64 rounded-xl bg-[#1a1a1a] border border-white/[0.1] shadow-2xl overflow-hidden animate-in fade-in slide-in-from-bottom-2 duration-200">
          <div className="p-2">
            <p className="text-[10px] text-white/30 uppercase tracking-wider px-3 py-1">
              Select Model
            </p>
            {MODELS.map((model) => (
              <button
                key={model.id}
                type="button"
                onClick={() => {
                  onSelectModel(model);
                  onToggle(false);
                }}
                className={`w-full flex items-center gap-3 px-3 py-2 rounded-lg text-left transition-all ${
                  selectedModel.id === model.id
                    ? 'bg-white/10 text-white'
                    : 'text-white/50 hover:bg-white/[0.05] hover:text-white'
                }`}
              >
                <div className="flex-1">
                  <p className="text-sm font-medium">{model.name}</p>
                  <p className="text-[10px] text-white/30">{model.provider}</p>
                </div>
                {selectedModel.id === model.id && (
                  <CheckCircle2 size={14} className="text-white/50" />
                )}
              </button>
            ))}
          </div>
        </div>
      )}
    </>
  );
}

import React, { useState } from 'react';
import { Sparkles } from 'lucide-react';
import { AIModel } from '../../../../../Origin Proof/src/types';
import { ModelPicker } from './ModelPicker';

interface PromptBarProps {
  selectedModel: AIModel;
  isLoading: boolean;
  onModelChange: (model: AIModel) => void;
  onSubmit: (prompt: string) => void;
}

export function PromptBar({
  selectedModel,
  isLoading,
  onModelChange,
  onSubmit,
}: PromptBarProps) {
  const [prompt, setPrompt] = useState('');
  const [showModelPicker, setShowModelPicker] = useState(false);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (prompt.trim() && !isLoading) {
      onSubmit(prompt.trim());
      setPrompt('');
    }
  };

  return (
    <div className="absolute bottom-10 left-1/2 -translate-x-1/2 w-[80%] max-w-2xl">
      <form
        onSubmit={handleSubmit}
        className="rounded-2xl p-2 flex items-center gap-2 backdrop-blur-xl bg-white/[0.03] border border-white/[0.08] shadow-2xl transition-all focus-within:ring-1 focus-within:ring-white/20 relative"
      >
        <ModelPicker
          selectedModel={selectedModel}
          isOpen={showModelPicker}
          isLoading={isLoading}
          onToggle={setShowModelPicker}
          onSelectModel={onModelChange}
        />

        <input
          type="text"
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          disabled={isLoading}
          placeholder="Describe your image..."
          className="flex-1 bg-transparent border-none focus:ring-0 text-white placeholder:text-white/20 px-4 py-3 text-base"
        />
        <button
          type="submit"
          disabled={isLoading || !prompt.trim()}
          className="bg-white text-black p-3 rounded-xl hover:scale-105 active:scale-95 disabled:opacity-30 disabled:scale-100 transition-all"
        >
          <Sparkles size={20} />
        </button>
      </form>
    </div>
  );
}

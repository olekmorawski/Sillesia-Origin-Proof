import React, { Dispatch } from 'react';
import { Sparkles, Shield } from 'lucide-react';
import { Mode } from '../types';
import { AppAction } from '../hooks';

interface NavigationProps {
  currentMode: Mode;
  onModeChange: (mode: Mode) => void;
  dispatch: Dispatch<AppAction>;
}

export function Navigation({ currentMode, onModeChange, dispatch }: NavigationProps) {
  const handleGenerateClick = () => {
    dispatch({ type: 'SET_MODE', payload: 'generate' });
    dispatch({ type: 'SET_VERIFY_RESULT', payload: null });
    onModeChange('generate');
  };

  const handleVerifyClick = () => {
    dispatch({ type: 'SET_MODE', payload: 'verify' });
    dispatch({ type: 'SET_IMAGE', payload: null });
    onModeChange('verify');
  };

  return (
    <nav className="absolute top-0 left-0 right-0 z-50 flex justify-between items-center px-6 py-5">
      <div className="text-xl font-bold tracking-[0.15em] uppercase text-white/90">
        Origin<span className="text-white/40">.Proof</span>
      </div>

      <div className="flex gap-1 p-1 rounded-full bg-white/[0.03] border border-white/[0.08] backdrop-blur-sm">
        <button
          onClick={handleGenerateClick}
          className={`px-5 py-2 rounded-full text-sm font-medium transition-all duration-300 flex items-center gap-2 ${
            currentMode === 'generate'
              ? 'bg-white text-black'
              : 'text-white/50 hover:text-white hover:bg-white/[0.05]'
          }`}
        >
          <Sparkles size={16} />
          <span className="tracking-wide">Generate</span>
        </button>
        <button
          onClick={handleVerifyClick}
          className={`px-5 py-2 rounded-full text-sm font-medium transition-all duration-300 flex items-center gap-2 ${
            currentMode === 'verify'
              ? 'bg-white text-black'
              : 'text-white/50 hover:text-white hover:bg-white/[0.05]'
          }`}
        >
          <Shield size={16} />
          <span className="tracking-wide">Verify</span>
        </button>
      </div>

      <div className="w-20" />
    </nav>
  );
}

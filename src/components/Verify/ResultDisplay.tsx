import React from 'react';
import { Loader2, CheckCircle2, XCircle, ExternalLink, Link as LinkIcon } from 'lucide-react';
import { VerificationResult } from '../../types';
import { extractModelName, formatAddress, formatDate } from '../../utils/file';
import { useTrustlessVerify } from '../../hooks/useTrustlessVerify';

interface ResultDisplayProps {
  verifyResult: VerificationResult;
  onReset: () => void;
}

export function ResultDisplay({ verifyResult, onReset }: ResultDisplayProps) {
  const isPending = verifyResult.status === 'pending';
  const isVerified = verifyResult.verified;
  const trustless = useTrustlessVerify();

  const canTrustless =
    isVerified &&
    !!verifyResult.short_id &&
    verifyResult.uploaded_phash != null &&
    !!verifyResult.contract_address;

  const runTrustless = () => {
    if (!canTrustless) return;
    trustless.verifyOnChain(
      verifyResult.short_id!,
      verifyResult.uploaded_phash!,
      verifyResult.contract_address!,
    );
  };

  return (
    <div className="w-full glass rounded-3xl p-8 animate-in zoom-in-95 duration-300">
      {/* Header */}
      <div className="flex items-start justify-between mb-8">
        <div className="flex items-center gap-5">
          {isPending ? (
            <div className="w-14 h-14 rounded-full bg-yellow-500/20 flex items-center justify-center shrink-0">
              <Loader2 size={32} className="text-yellow-400 animate-spin" />
            </div>
          ) : isVerified ? (
            <div className="w-14 h-14 rounded-full bg-green-500/20 flex items-center justify-center shrink-0">
              <CheckCircle2 size={32} className="text-green-500" />
            </div>
          ) : (
            <div className="w-14 h-14 rounded-full bg-red-500/20 flex items-center justify-center shrink-0">
              <XCircle size={32} className="text-red-500" />
            </div>
          )}
          <div>
            {isPending ? (
              <>
                <h2 className="text-2xl font-bold tracking-tight text-white">Anchoring…</h2>
                <p className="text-xs text-yellow-400/60 mt-1">
                  {verifyResult.message || 'Blockchain registration in progress. Try again shortly.'}
                </p>
              </>
            ) : isVerified ? (
              <>
                <p className="text-xs text-green-400/70 uppercase tracking-[0.15em] font-medium mb-1">
                  Yes, AI Generated
                </p>
                <h2 className="text-2xl font-bold tracking-tight text-white">
                  {extractModelName(verifyResult.generation?.model ?? '')}
                </h2>
                {verifyResult.integrity === 'transformed' && (
                  <p className="text-xs text-yellow-400/70 mt-1">
                    Modified copy — screenshot, crop, or re-encode detected
                  </p>
                )}
              </>
            ) : (
              <>
                <h2 className="text-2xl font-bold tracking-tight text-white">Not Verified</h2>
                <p className="text-xs text-white/40 mt-1">No provenance record found for this image.</p>
              </>
            )}
          </div>
        </div>
        <button
          onClick={onReset}
          className="text-xs uppercase tracking-widest hover:text-white text-white/40 transition-colors shrink-0 mt-1"
        >
          Reset
        </button>
      </div>

      {/* Verified: generation metadata */}
      {isVerified && verifyResult.generation && (
        <div className="grid grid-cols-2 gap-3 mb-4">
          <div className="bg-white/[0.03] rounded-2xl p-4 border border-white/[0.05]">
            <p className="text-[10px] text-white/30 uppercase font-bold mb-1 tracking-wider">
              Generated
            </p>
            <p className="text-sm text-white/80">
              {verifyResult.generation.generated_at
                ? formatDate(verifyResult.generation.generated_at)
                : 'N/A'}
            </p>
          </div>
          <div className="bg-white/[0.03] rounded-2xl p-4 border border-white/[0.05]">
            <p className="text-[10px] text-white/30 uppercase font-bold mb-1 tracking-wider">
              Registered by
            </p>
            <p className="text-sm text-white/80 truncate font-mono">
              {verifyResult.on_chain?.registrant
                ? formatAddress(verifyResult.on_chain.registrant)
                : 'N/A'}
            </p>
          </div>
          {verifyResult.generation.prompt && (
            <div className="col-span-2 bg-white/[0.03] rounded-2xl p-4 border border-white/[0.05]">
              <p className="text-[10px] text-white/30 uppercase font-bold mb-1 tracking-wider">
                Prompt
              </p>
              <p className="text-sm text-white/80">{verifyResult.generation.prompt}</p>
            </div>
          )}
        </div>
      )}

      {/* Semantic fingerprint + ZK badges */}
      {isVerified && (verifyResult.semantic_fingerprint || verifyResult.zk_proof_valid != null) && (
        <div className="flex flex-wrap gap-2 mb-4">
          {verifyResult.semantic_fingerprint && (
            <div
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium border ${
                verifyResult.semantic_fingerprint.match
                  ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-400'
                  : 'bg-orange-500/10 border-orange-500/20 text-orange-400'
              }`}
            >
              <span>{verifyResult.semantic_fingerprint.match ? '◉' : '○'}</span>
              Semantic fingerprint{' '}
              {Math.round(verifyResult.semantic_fingerprint.correlation * 100)}% match
            </div>
          )}
          {verifyResult.zk_proof_valid != null && (
            <div
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium border ${
                verifyResult.zk_proof_valid
                  ? 'bg-violet-500/10 border-violet-500/20 text-violet-400'
                  : 'bg-white/5 border-white/10 text-white/30'
              }`}
            >
              <span>{verifyResult.zk_proof_valid ? '◉' : '○'}</span>
              ZK proof {verifyResult.zk_proof_valid ? 'valid' : 'not verified'}
            </div>
          )}
        </div>
      )}

      {/* On-chain link — label changes for tampered copies */}
      {verifyResult.on_chain?.explorer_url && (
        <a
          href={verifyResult.on_chain.explorer_url}
          target="_blank"
          rel="noreferrer"
          className="flex items-center justify-center gap-2 w-full py-4 bg-white text-black rounded-2xl font-medium hover:opacity-90 transition-opacity"
        >
          {verifyResult.integrity === 'transformed'
            ? 'View Original Registration on BaseScan'
            : 'View on BaseScan'}
          <ExternalLink size={16} />
        </a>
      )}

      {/* Trustless on-chain re-check — hits the contract directly via viem */}
      {canTrustless && (
        <div className="mt-3">
          <button
            onClick={runTrustless}
            disabled={trustless.loading}
            className="flex items-center justify-center gap-2 w-full py-3 border border-white/15 text-white/80 rounded-2xl text-sm font-medium hover:bg-white/5 transition-colors disabled:opacity-50"
          >
            {trustless.loading ? (
              <>
                <Loader2 size={16} className="animate-spin" />
                Reading contract…
              </>
            ) : (
              <>
                <LinkIcon size={16} />
                Verify on-chain (no backend)
              </>
            )}
          </button>

          {trustless.error && (
            <p className="text-xs text-red-400/80 mt-2 font-mono break-all">
              {trustless.error}
            </p>
          )}

          {trustless.result && (
            <div className="mt-3 bg-black/40 border border-white/[0.08] rounded-2xl p-4 text-[11px] font-mono text-white/70 space-y-1.5">
              <p className="text-[10px] text-white/30 uppercase tracking-widest mb-2">
                Base Sepolia · block {trustless.result.blockNumber}
              </p>
              <p>
                <span className="text-white/40">contract</span>{' '}
                <span className="text-white/80">
                  {formatAddress(trustless.result.contractAddress)}
                </span>
              </p>
              <p>
                <span className="text-white/40">watermarkId</span>{' '}
                <span className="text-white/80 break-all">
                  {trustless.result.watermarkId.slice(0, 18)}…
                </span>
              </p>
              <p>
                <span className="text-white/40">uploadedPHash</span>{' '}
                <span className="text-white/80">{trustless.result.uploadedPHash}</span>
              </p>
              <p className="pt-1.5 border-t border-white/[0.06]">
                <span className="text-white/40">isDerivative →</span>{' '}
                <span
                  className={
                    trustless.result.isDerivative
                      ? 'text-emerald-400 font-bold'
                      : 'text-red-400 font-bold'
                  }
                >
                  {String(trustless.result.isDerivative)}
                </span>{' '}
                <span className="text-white/40">distance</span>{' '}
                <span className="text-white/80">{trustless.result.distance}/64</span>
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

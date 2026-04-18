import { useCallback, useState } from 'react';
import { createPublicClient, http, keccak256, toHex } from 'viem';
import { baseSepolia } from 'viem/chains';
import { REGISTRY_ABI, RPC_URL } from '../constants/contract';

export interface TrustlessResult {
  isDerivative: boolean;
  distance: number;
  blockNumber: string;
  contractAddress: string;
  watermarkId: string;
  uploadedPHash: string;
}

export interface TrustlessState {
  loading: boolean;
  error: string | null;
  result: TrustlessResult | null;
}

export function useTrustlessVerify() {
  const [state, setState] = useState<TrustlessState>({
    loading: false,
    error: null,
    result: null,
  });

  const verifyOnChain = useCallback(
    async (shortId: string, uploadedPHash: number, contractAddress: string) => {
      setState({ loading: true, error: null, result: null });

      try {
        if (!contractAddress || !contractAddress.startsWith('0x')) {
          throw new Error('Missing contract address from backend');
        }

        const client = createPublicClient({
          chain: baseSepolia,
          transport: http(RPC_URL),
        });

        const watermarkId = keccak256(toHex(shortId));
        const phash = BigInt(uploadedPHash);

        const [blockNumber, readResult] = await Promise.all([
          client.getBlockNumber(),
          client.readContract({
            address: contractAddress as `0x${string}`,
            abi: REGISTRY_ABI,
            functionName: 'verifyDerivative',
            args: [watermarkId, phash, 15],
          }),
        ]);

        const [isDerivative, distance] = readResult as [boolean, number];

        setState({
          loading: false,
          error: null,
          result: {
            isDerivative,
            distance: Number(distance),
            blockNumber: blockNumber.toString(),
            contractAddress,
            watermarkId,
            uploadedPHash: phash.toString(),
          },
        });
      } catch (err) {
        setState({
          loading: false,
          error: err instanceof Error ? err.message : String(err),
          result: null,
        });
      }
    },
    []
  );

  const reset = useCallback(() => {
    setState({ loading: false, error: null, result: null });
  }, []);

  return { ...state, verifyOnChain, reset };
}

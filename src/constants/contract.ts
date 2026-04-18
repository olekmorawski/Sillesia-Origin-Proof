export const RPC_URL = 'https://sepolia.base.org';

export const REGISTRY_ABI = [
  {
    type: 'function',
    name: 'verifyDerivative',
    stateMutability: 'view',
    inputs: [
      { name: 'watermarkId',   type: 'bytes32' },
      { name: 'uploadedPHash', type: 'uint64'  },
      { name: 'threshold',     type: 'uint8'   },
    ],
    outputs: [
      { name: 'isDerivative', type: 'bool'  },
      { name: 'distance',     type: 'uint8' },
    ],
  },
] as const;

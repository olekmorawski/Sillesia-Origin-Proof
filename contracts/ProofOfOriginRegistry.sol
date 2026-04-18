// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/// @dev Interface for the ezkl-generated EVM verifier contract (Verifier.sol).
interface IVerifier {
    function verify(
        bytes calldata encoded,
        uint256[] calldata instances
    ) external view returns (bool);
}

contract ProofOfOriginRegistry {
    address   public owner;
    IVerifier public verifier;

    struct Record {
        bytes32 imageHash;
        uint64  perceptualHash;
        bool    proofVerifiedOnChain;
        uint256 timestamp;
        address creator;
    }

    mapping(bytes32 => bool)   public placeholderExists;
    mapping(bytes32 => Record) public records;
    mapping(bytes32 => bool)   public exists;

    event PlaceholderCreated(
        bytes32 indexed watermarkId,
        address         creator,
        uint256         timestamp
    );

    event Registered(
        bytes32 indexed watermarkId,
        bytes32         imageHash,
        uint64          perceptualHash,
        bool            proofVerifiedOnChain,
        uint256         timestamp,
        address         creator
    );

    event VerifierUpdated(address indexed previous, address indexed next);

    constructor(address _verifier) {
        owner    = msg.sender;
        verifier = IVerifier(_verifier);
    }

    function setVerifier(address _verifier) external {
        require(msg.sender == owner, "Not owner");
        emit VerifierUpdated(address(verifier), _verifier);
        verifier = IVerifier(_verifier);
    }

    /// @notice Reserve a slot before generation completes.
    ///         Call this as the first ARQ worker step, before the crash window opens.
    function createPlaceholder(bytes32 watermarkId) external {
        require(!exists[watermarkId], "Already registered");
        require(!placeholderExists[watermarkId], "Placeholder exists");
        placeholderExists[watermarkId] = true;
        emit PlaceholderCreated(watermarkId, msg.sender, block.timestamp);
    }

    /// @notice Complete a previously reserved registration.
    ///         Idempotent: second call reverts with "Already registered" — safe for ARQ retry.
    function completeRegistration(
        bytes32            watermarkId,
        bytes32            imageHash,
        uint64             perceptualHash,
        bytes     calldata zkProof,
        uint256[] calldata zkInstances
    ) external {
        require(placeholderExists[watermarkId], "No placeholder");
        require(!exists[watermarkId], "Already registered");

        bool proofVerified = false;
        if (zkProof.length > 0 && address(verifier) != address(0)) {
            proofVerified = verifier.verify(zkProof, zkInstances);
            require(proofVerified, "ZK proof invalid");
        }

        records[watermarkId] = Record({
            imageHash:            imageHash,
            perceptualHash:       perceptualHash,
            proofVerifiedOnChain: proofVerified,
            timestamp:            block.timestamp,
            creator:              msg.sender
        });
        exists[watermarkId] = true;

        emit Registered(
            watermarkId, imageHash, perceptualHash,
            proofVerified, block.timestamp, msg.sender
        );
    }

    function lookup(bytes32 watermarkId)
        external view
        returns (bytes32, uint64, bool, uint256, address)
    {
        require(exists[watermarkId], "Not registered");
        Record memory r = records[watermarkId];
        return (r.imageHash, r.perceptualHash, r.proofVerifiedOnChain, r.timestamp, r.creator);
    }

    function verifyDerivative(
        bytes32 watermarkId,
        uint64  uploadedPHash,
        uint8   threshold
    ) external view returns (bool isDerivative, uint8 distance) {
        require(exists[watermarkId], "Not registered");
        uint64 reg = records[watermarkId].perceptualHash;
        distance     = _popcount(uploadedPHash ^ reg);
        isDerivative = distance <= threshold;
    }

    function _popcount(uint64 x) internal pure returns (uint8 count) {
        while (x != 0) { count += uint8(x & 1); x >>= 1; }
    }
}

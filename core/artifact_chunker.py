"""
AutoDev Artifact Chunker (Phase 4 - Differential Artifact Synchronization)
Implements FastCDC (Fast Content-Defined Chunking) and deterministic chunking
for content-addressed storage and differential artifact transfer.
"""

from dataclasses import dataclass, field
import hashlib
import os
from typing import List, Optional, Generator

# Deterministic Gear Hash 256-entry lookup table for FastCDC
GEAR_TABLE = [
    0x8a9b0fbc, 0x32b91845, 0x8aad88b9, 0xac637953, 0xa5183350, 0x47781b08, 0x1f945763, 0x1a7a0b58,
    0x406d3923, 0x3cb7eb8f, 0x07f436d8, 0x6e9f9bb6, 0x939c362d, 0x22878bf0, 0x51b22e11, 0xb6aa0b0e,
    0x616a6982, 0xd0f507b5, 0xa7019808, 0xb0df46ca, 0xed0c6488, 0xa4b1965e, 0x5a6d36e8, 0x904a4347,
    0x0bb038ee, 0x356230bf, 0x56a42217, 0x2f6027c9, 0x334d7d13, 0xb9b8849b, 0x7a63bb8b, 0xa78696ab,
    0x6516a244, 0x3328e185, 0x981548e6, 0xbb3e6f9a, 0x8a556857, 0x76b88c4b, 0x5e5b62b1, 0xd986a489,
    0x192d6e3e, 0x7793d56d, 0x72a5a542, 0x1a0525ee, 0x1612403e, 0xdfe2d3c9, 0x4f128e57, 0x20886c9d,
    0x54625b0b, 0xb6441548, 0x054a9386, 0x93309a47, 0x8430a911, 0xa31eaec8, 0xcbe92b74, 0xa2c6486c,
    0x6be04620, 0x90c74d82, 0x25f8266d, 0xc1039868, 0x973a9c7b, 0x5638c4d2, 0x1a21e428, 0x7f4a4781,
    0xa3c8d197, 0x13d80eb8, 0x3922d56a, 0x9597799b, 0x6e788c88, 0x5e45a278, 0x7ef4d9cf, 0x12b57577,
    0x2c68e1aa, 0x157b8559, 0xd6c7cf6d, 0x117462c1, 0x6e9196b6, 0xa2634d28, 0xbb327c52, 0x1bb2b157,
    0x39c0bc98, 0x3454b5df, 0x05f817ea, 0x7be49852, 0x3b6be1a8, 0xb0e80811, 0x6f91c9a6, 0x269d784a,
    0x72a3962d, 0x68377be8, 0x6644f12b, 0x48bb7a04, 0x98a1396a, 0x7cf20c9e, 0x68b92b6a, 0x7b629b37,
    0x26330919, 0xa7a4f9b8, 0xd888876c, 0x5b9229f3, 0x5a18355a, 0x11b5e28a, 0x6b44a29a, 0x4e6b19a8,
    0x95669b33, 0xdc58045d, 0x68427f7a, 0x3784157e, 0x7c7be4ea, 0x794625b6, 0xb9b8849b, 0x11d8e137,
    0x58249829, 0x192d6e3e, 0x3c9657b8, 0x92556857, 0xa2634d28, 0x5e5b62b1, 0x56a42217, 0x7a63bb8b,
    0x1bb2b157, 0x334d7d13, 0x4f128e57, 0x20886c9d, 0x6be04620, 0x90c74d82, 0xcbe92b74, 0xa2c6486c,
    0x981548e6, 0xbb3e6f9a, 0x8a556857, 0x76b88c4b, 0x5e5b62b1, 0xd986a489, 0x192d6e3e, 0x7793d56d,
    0x72a5a542, 0x1a0525ee, 0x1612403e, 0xdfe2d3c9, 0x4f128e57, 0x20886c9d, 0x54625b0b, 0xb6441548,
    0x054a9386, 0x93309a47, 0x8430a911, 0xa31eaec8, 0xcbe92b74, 0xa2c6486c, 0x6be04620, 0x90c74d82,
    0x25f8266d, 0xc1039868, 0x973a9c7b, 0x5638c4d2, 0x1a21e428, 0x7f4a4781, 0xa3c8d197, 0x13d80eb8,
    0x3922d56a, 0x9597799b, 0x6e788c88, 0x5e45a278, 0x7ef4d9cf, 0x12b57577, 0x2c68e1aa, 0x157b8559,
    0xd6c7cf6d, 0x117462c1, 0x6e9196b6, 0xa2634d28, 0xbb327c52, 0x1bb2b157, 0x39c0bc98, 0x3454b5df,
    0x05f817ea, 0x7be49852, 0x3b6be1a8, 0xb0e80811, 0x6f91c9a6, 0x269d784a, 0x72a3962d, 0x68377be8,
    0x6644f12b, 0x48bb7a04, 0x98a1396a, 0x7cf20c9e, 0x68b92b6a, 0x7b629b37, 0x26330919, 0xa7a4f9b8,
    0xd888876c, 0x5b9229f3, 0x5a18355a, 0x11b5e28a, 0x6b44a29a, 0x4e6b19a8, 0x95669b33, 0xdc58045d,
    0x68427f7a, 0x3784157e, 0x7c7be4ea, 0x794625b6, 0xb9b8849b, 0x11d8e137, 0x58249829, 0x192d6e3e,
    0x3c9657b8, 0x92556857, 0xa2634d28, 0x5e5b62b1, 0x56a42217, 0x7a63bb8b, 0x1bb2b157, 0x334d7d13,
    0x4f128e57, 0x20886c9d, 0x6be04620, 0x90c74d82, 0xcbe92b74, 0xa2c6486c, 0x981548e6, 0xbb3e6f9a,
    0x8a556857, 0x76b88c4b, 0x5e5b62b1, 0xd986a489, 0x192d6e3e, 0x7793d56d, 0x72a5a542, 0x1a0525ee,
    0x1612403e, 0xdfe2d3c9, 0x4f128e57, 0x20886c9d, 0x54625b0b, 0xb6441548, 0x054a9386, 0x93309a47,
    0x8430a911, 0xa31eaec8, 0xcbe92b74, 0xa2c6486c, 0x6be04620, 0x90c74d82, 0x25f8266d, 0xc1039868,
    0x973a9c7b, 0x5638c4d2, 0x1a21e428, 0x7f4a4781, 0xa3c8d197, 0x13d80eb8, 0x3922d56a, 0x9597799b,
]


@dataclass
class ChunkInfo:
    """Represents a discrete content-addressed chunk with digest and slice offsets."""
    digest: str
    size_bytes: int
    offset: int
    index: int
    data: Optional[bytes] = None


class ArtifactChunker:
    """
    FastCDC Content-Defined Chunking implementation.
    Produces content-dependent boundary cuts with average target size while respecting
    strict min and max boundary guarantees.
    """

    def __init__(
        self,
        min_size: int = 4096,
        target_size: int = 16384,
        max_size: int = 65536,
    ) -> None:
        if not (min_size <= target_size <= max_size):
            raise ValueError(f"Invalid chunk sizes: min ({min_size}) <= target ({target_size}) <= max ({max_size})")
        self.min_size = min_size
        self.target_size = target_size
        self.max_size = max_size

        # Compute mask based on target size
        # e.g., target 16KB (2^14) -> mask with 14 bits
        bits = max(8, int(target_size).bit_length() - 1)
        self.mask_normal = (1 << bits) - 1
        # Asymmetric mask for sub-target region to normalize distribution
        self.mask_small = (1 << (bits + 1)) - 1

    def chunk_bytes(self, data: bytes, include_data: bool = False) -> List[ChunkInfo]:
        """
        Partition a byte buffer into content-defined chunks using FastCDC.
        """
        if not data:
            # Explicit handling of empty artifact
            digest = hashlib.sha256(b"").hexdigest()
            return [ChunkInfo(digest=digest, size_bytes=0, offset=0, index=0, data=b"" if include_data else None)]

        chunks: List[ChunkInfo] = []
        n = len(data)
        offset = 0
        chunk_index = 0

        while offset < n:
            remaining = n - offset
            if remaining <= self.min_size:
                # Last remaining tail chunk
                chunk_bytes = data[offset:]
                digest = hashlib.sha256(chunk_bytes).hexdigest()
                chunks.append(
                    ChunkInfo(
                        digest=digest,
                        size_bytes=len(chunk_bytes),
                        offset=offset,
                        index=chunk_index,
                        data=chunk_bytes if include_data else None,
                    )
                )
                break

            # FastCDC Cutpoint search
            cut = self._find_cutpoint(data, offset, remaining)
            chunk_bytes = data[offset : offset + cut]
            digest = hashlib.sha256(chunk_bytes).hexdigest()
            chunks.append(
                ChunkInfo(
                    digest=digest,
                    size_bytes=len(chunk_bytes),
                    offset=offset,
                    index=chunk_index,
                    data=chunk_bytes if include_data else None,
                )
            )
            offset += cut
            chunk_index += 1

        return chunks

    def _find_cutpoint(self, data: bytes, offset: int, length: int) -> int:
        """Find the FastCDC cutpoint within bounds [min_size, min(max_size, length)]."""
        max_chunk = min(self.max_size, length)
        if max_chunk <= self.min_size:
            return max_chunk

        fingerprint = 0
        i = self.min_size

        # Sub-target region uses higher density mask
        target_boundary = min(self.target_size, max_chunk)
        while i < target_boundary:
            b = data[offset + i]
            fingerprint = ((fingerprint << 1) + GEAR_TABLE[b]) & 0xFFFFFFFF
            if (fingerprint & self.mask_small) == 0:
                return i + 1
            i += 1

        # Region above target size uses normal mask
        while i < max_chunk:
            b = data[offset + i]
            fingerprint = ((fingerprint << 1) + GEAR_TABLE[b]) & 0xFFFFFFFF
            if (fingerprint & self.mask_normal) == 0:
                return i + 1
            i += 1

        return max_chunk

    def chunk_file(self, file_path: str, include_data: bool = False) -> List[ChunkInfo]:
        """Read a file and partition it into chunks."""
        with open(file_path, "rb") as f:
            data = f.read()
        return self.chunk_bytes(data, include_data=include_data)

    @staticmethod
    def reconstruct_file(chunks_data: List[bytes], output_path: str, expected_sha256: Optional[str] = None) -> str:
        """
        Reconstruct a file from ordered chunk byte buffers and verify its whole-file digest.
        """
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        hasher = hashlib.sha256()

        temp_path = f"{output_path}.tmp.{os.getpid()}"
        try:
            with open(temp_path, "wb") as f:
                for chunk in chunks_data:
                    f.write(chunk)
                    hasher.update(chunk)

            actual_sha256 = hasher.hexdigest()
            if expected_sha256 and actual_sha256.lower() != expected_sha256.lower():
                raise ValueError(f"Reconstructed artifact SHA-256 mismatch: expected {expected_sha256}, got {actual_sha256}")

            # Atomic replace
            if os.path.exists(output_path):
                os.remove(output_path)
            os.rename(temp_path, output_path)
            return actual_sha256
        finally:
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except OSError:
                    pass

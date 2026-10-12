"""
Differential Artifact Synchronization Edge Case Tests (Phase 8.3)
Exercises FastCDC boundaries on 1-byte edits, CAS directory prefixing,
resumable transfer state, and garbage collection metrics.
"""

import hashlib
import os
import tempfile
import pytest

from core.artifact_chunker import ArtifactChunker, ChunkInfo
from core.artifact_chunk_store import ArtifactChunkStore, ChunkIntegrityError
from core.artifact_sync_protocol import (
    ChunkMetadata,
    ChunkManifest,
    ChunkTransferMessage,
)
from core.artifact_transfer_manager import ArtifactTransferManager
from core.artifact_gc import ArtifactGarbageCollector


class TestArtifactSyncEdgeCases:
    def test_one_byte_modification_preserves_most_chunks(self):
        chunker = ArtifactChunker(min_size=256, target_size=512, max_size=1024)
        # 10KB payload
        data_v1 = b"".join(f"DataLine #{i:04d} - Standard repetitive pattern stream\n".encode("utf-8") for i in range(250))
        chunks_v1 = chunker.chunk_bytes(data_v1)

        # Modify 1 byte in the middle
        mid = len(data_v1) // 2
        data_v2 = data_v1[:mid] + b"X" + data_v1[mid+1:]
        chunks_v2 = chunker.chunk_bytes(data_v2)

        v1_digests = {c.digest for c in chunks_v1}
        v2_digests = {c.digest for c in chunks_v2}

        # Content-defined boundaries mean majority of chunks are identical
        shared_chunks = v1_digests.intersection(v2_digests)
        assert len(shared_chunks) >= len(chunks_v1) - 2

    def test_cas_directory_structure_and_prefixes(self, tmp_path):
        store = ArtifactChunkStore(storage_root=str(tmp_path / "cas"))
        data = b"Sample binary chunk payload"
        digest = hashlib.sha256(data).hexdigest()

        store.put_chunk(digest, data)

        prefix = digest[:2]
        expected_file = tmp_path / "cas" / "sha256" / prefix / f"{digest}.chunk"
        assert expected_file.is_file()
        assert expected_file.read_bytes() == data

    def test_resumable_transfer_midway_interruption(self, tmp_path):
        sender_store = ArtifactChunkStore(storage_root=str(tmp_path / "sender"))
        receiver_store = ArtifactChunkStore(storage_root=str(tmp_path / "receiver"))
        chunker = ArtifactChunker(min_size=256, target_size=512, max_size=1024)

        sender_mgr = ArtifactTransferManager(chunk_store=sender_store, chunker=chunker)
        receiver_mgr = ArtifactTransferManager(chunk_store=receiver_store, chunker=chunker, staging_dir=str(tmp_path / "staging"))

        src_file = tmp_path / "multi_chunk_file.bin"
        data_payload = b"".join(f"ResumableBlock_{i:04d}_Data\n".encode("utf-8") * 10 for i in range(25))
        src_file.write_bytes(data_payload)

        manifest, _ = sender_mgr.create_manifest_for_file(str(src_file), artifact_id="resumable-art")
        neg = receiver_mgr.negotiate_incoming_transfer(manifest)
        assert len(neg.missing_chunk_digests) > 1

        # Transfer only the first chunk (simulating network disconnection)
        first_digest = neg.missing_chunk_digests[0]
        data1 = sender_store.get_chunk(first_digest)
        receiver_mgr.receive_chunk(ChunkTransferMessage.from_bytes("resumable-art", first_digest, 0, data1))

        assert receiver_mgr.is_transfer_ready("resumable-art") is False

        # Resume transfer: client re-negotiates
        resume_neg = receiver_mgr.negotiate_incoming_transfer(manifest)
        # Receiver already has first chunk!
        assert first_digest not in resume_neg.missing_chunk_digests
        assert resume_neg.existing_chunk_count == 1

        # Send remaining chunks
        for d in resume_neg.missing_chunk_digests:
            d_bytes = sender_store.get_chunk(d)
            receiver_mgr.receive_chunk(ChunkTransferMessage.from_bytes("resumable-art", d, 0, d_bytes))

        assert receiver_mgr.is_transfer_ready("resumable-art") is True
        dest = tmp_path / "completed.bin"
        ack = receiver_mgr.reconstruct_artifact("resumable-art", str(dest))
        assert ack.status == "completed"
        assert dest.read_bytes() == data_payload

    def test_chunk_transfer_message_base64_roundtrip(self):
        raw = b"\x00\x01\x02\xFF\xFE\xFD\x10\x20\x30"
        msg = ChunkTransferMessage.from_bytes("art-10", "sha256digest", 3, raw)
        assert msg.get_data() == raw

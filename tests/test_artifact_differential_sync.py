"""
Unit and Integration Tests for Differential Artifact Synchronization, FastCDC & CAS (Phase 4 & Phase 8.3)
"""

import os
import hashlib
import tempfile
import pytest

from core.artifact_chunker import ArtifactChunker, ChunkInfo
from core.artifact_chunk_store import (
    ArtifactChunkStore,
    ChunkStoreError,
    StorageQuotaExceededError,
    ChunkIntegrityError,
)
from core.artifact_sync_protocol import (
    ChunkMetadata,
    ChunkManifest,
    ChunkSyncNegotiationRequest,
    ChunkSyncNegotiationResponse,
    ChunkTransferMessage,
    ChunkSyncAck,
)
from core.artifact_transfer_manager import (
    TransferSession,
    ArtifactTransferManager,
)
from core.artifact_gc import ArtifactGarbageCollector, GCReport


class TestArtifactChunkerFastCDC:
    def test_chunk_empty_bytes(self):
        chunker = ArtifactChunker()
        chunks = chunker.chunk_bytes(b"")
        assert len(chunks) == 1
        assert chunks[0].size_bytes == 0
        assert chunks[0].digest == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"

    def test_chunk_small_file_single_chunk(self):
        chunker = ArtifactChunker(min_size=1024, target_size=4096, max_size=8192)
        small_data = b"AutoDev v2.4 FastCDC Deterministic Chunking Test Data Payload" * 10
        chunks = chunker.chunk_bytes(small_data, include_data=True)
        assert len(chunks) == 1
        assert chunks[0].size_bytes == len(small_data)
        assert chunks[0].data == small_data

    def test_chunk_large_file_and_reconstruction(self):
        chunker = ArtifactChunker(min_size=1024, target_size=2048, max_size=4096)
        # 32KB payload
        data = b"".join(f"Block #{i:04d} - Content data segment with entropy variations...\n".encode("utf-8") * 20 for i in range(50))
        chunks = chunker.chunk_bytes(data, include_data=True)

        assert len(chunks) > 1
        # Check boundary invariant
        for c in chunks[:-1]:  # all except last tail chunk
            assert chunker.min_size <= c.size_bytes <= chunker.max_size

        # Reconstruct
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp_path = tmp.name

        try:
            chunks_data = [c.data for c in chunks]
            actual_sha = chunker.reconstruct_file(chunks_data, tmp_path)
            with open(tmp_path, "rb") as f:
                reconstructed_data = f.read()
            assert reconstructed_data == data
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    def test_deterministic_chunking_identical_cuts(self):
        chunker = ArtifactChunker(min_size=512, target_size=1024, max_size=2048)
        data = b"Deterministic testing block string for FastCDC\n" * 50
        c1 = chunker.chunk_bytes(data)
        c2 = chunker.chunk_bytes(data)

        assert len(c1) == len(c2)
        assert [c.digest for c in c1] == [c.digest for c in c2]
        assert [c.size_bytes for c in c1] == [c.size_bytes for c in c2]

    def test_reconstruction_mismatched_sha256_raises(self, tmp_path):
        chunker = ArtifactChunker()
        dest = tmp_path / "bad_recon.bin"
        with pytest.raises(ValueError, match="mismatch"):
            chunker.reconstruct_file([b"hello world"], str(dest), expected_sha256="0"*64)


class TestArtifactChunkStoreCAS:
    def test_put_get_and_deduplication(self, tmp_path):
        store = ArtifactChunkStore(storage_root=str(tmp_path / "cas"))
        data = b"Unique immutable chunk content 1234567890"
        digest = hashlib.sha256(data).hexdigest()

        # Store chunk
        stored = store.put_chunk(digest, data)
        assert stored is True
        assert store.has_chunk(digest) is True

        # Retrieve and verify integrity
        retrieved = store.get_chunk(digest)
        assert retrieved == data

        # Storing again is deduplicated
        stored2 = store.put_chunk(digest, data)
        assert stored2 is True
        assert len(store.list_chunks()) == 1

    def test_put_chunk_integrity_mismatch_fails_closed(self, tmp_path):
        store = ArtifactChunkStore(storage_root=str(tmp_path / "cas"))
        data = b"Corrupted chunk bytes"
        wrong_digest = "0" * 64

        with pytest.raises(ChunkIntegrityError):
            store.put_chunk(wrong_digest, data)

    def test_storage_quota_enforcement(self, tmp_path):
        # 100 byte quota
        store = ArtifactChunkStore(storage_root=str(tmp_path / "cas"), storage_quota_bytes=100)
        data = b"A" * 60
        d1 = hashlib.sha256(data).hexdigest()
        store.put_chunk(d1, data)

        # Storing another 60 bytes exceeds 100 bytes quota
        data2 = b"B" * 60
        d2 = hashlib.sha256(data2).hexdigest()
        with pytest.raises(StorageQuotaExceededError):
            store.put_chunk(d2, data2)

    def test_path_traversal_prevention(self, tmp_path):
        store = ArtifactChunkStore(storage_root=str(tmp_path / "cas"))
        with pytest.raises(ValueError, match="Invalid SHA-256"):
            store.put_chunk("../../etc/passwd", b"malicious")

    def test_delete_chunk_and_get_stats(self, tmp_path):
        store = ArtifactChunkStore(storage_root=str(tmp_path / "cas"))
        data = b"Deletable chunk"
        d = hashlib.sha256(data).hexdigest()
        store.put_chunk(d, data)

        stats_before = store.get_stats()
        assert stats_before["chunk_count"] == 1
        assert stats_before["total_bytes"] == len(data)

        deleted = store.delete_chunk(d)
        assert deleted is True
        assert store.has_chunk(d) is False


class TestDifferentialTransferManager:
    def test_negotiate_and_transfer_missing_chunks_only(self, tmp_path):
        sender_store = ArtifactChunkStore(storage_root=str(tmp_path / "sender_cas"))
        receiver_store = ArtifactChunkStore(storage_root=str(tmp_path / "receiver_cas"))

        chunker = ArtifactChunker(min_size=512, target_size=1024, max_size=2048)
        sender_mgr = ArtifactTransferManager(chunk_store=sender_store, chunker=chunker)
        receiver_mgr = ArtifactTransferManager(chunk_store=receiver_store, chunker=chunker, staging_dir=str(tmp_path / "staging"))

        # Create sample file
        sample_file = tmp_path / "artifact_v1.bin"
        content = b"Sample artifact binary file content...\n" * 100
        sample_file.write_bytes(content)

        # Sender creates manifest
        manifest, chunk_infos = sender_mgr.create_manifest_for_file(str(sample_file), artifact_id="art-001")
        assert len(manifest.chunks) > 0

        # Receiver negotiates: initially all chunks are missing
        neg_resp = receiver_mgr.negotiate_incoming_transfer(manifest)
        assert len(neg_resp.missing_chunk_digests) == len(manifest.chunks)
        assert neg_resp.existing_chunk_count == 0

        # Transfer missing chunks
        for missing_digest in neg_resp.missing_chunk_digests:
            chunk_data = sender_store.get_chunk(missing_digest)
            msg = ChunkTransferMessage.from_bytes(
                artifact_id="art-001",
                chunk_digest=missing_digest,
                chunk_index=0,
                data=chunk_data,
            )
            receiver_mgr.receive_chunk(msg)

        assert receiver_mgr.is_transfer_ready("art-001") is True

        # Reconstruct on receiver
        dest_file = tmp_path / "reconstructed_artifact.bin"
        ack = receiver_mgr.reconstruct_artifact("art-001", str(dest_file))
        assert ack.status == "completed"
        assert ack.whole_sha256_verified is True
        assert dest_file.read_bytes() == content

        # Now test differential sync on a slightly modified version (1 modified chunk)
        modified_content = content + b"\nAppended new patch block!"
        sample_v2 = tmp_path / "artifact_v2.bin"
        sample_v2.write_bytes(modified_content)

        manifest_v2, _ = sender_mgr.create_manifest_for_file(str(sample_v2), artifact_id="art-002")
        neg_v2 = receiver_mgr.negotiate_incoming_transfer(manifest_v2)

        # Most chunks should already exist on receiver!
        assert neg_v2.existing_chunk_count > 0
        assert len(neg_v2.missing_chunk_digests) < len(manifest_v2.chunks)

    def test_chunk_manifest_serialization_roundtrip(self):
        meta = [ChunkMetadata(digest="a"*64, size_bytes=100, offset=0, index=0)]
        m = ChunkManifest(artifact_id="art-ser", total_size_bytes=100, whole_sha256="b"*64, chunks=meta)
        d = m.to_dict()
        m_rec = ChunkManifest.from_dict(d)
        assert m_rec.artifact_id == "art-ser"
        assert len(m_rec.chunks) == 1
        assert m_rec.chunks[0].digest == "a"*64


class TestArtifactGarbageCollector:
    def test_collect_orphans_prunes_unreferenced(self, tmp_path):
        store = ArtifactChunkStore(storage_root=str(tmp_path / "cas"))
        c1_data = b"Chunk 1 referenced"
        c2_data = b"Chunk 2 orphaned"
        d1 = hashlib.sha256(c1_data).hexdigest()
        d2 = hashlib.sha256(c2_data).hexdigest()

        store.put_chunk(d1, c1_data)
        store.put_chunk(d2, c2_data)

        # Active manifest only references c1
        manifest = ChunkManifest(
            artifact_id="art-live",
            total_size_bytes=len(c1_data),
            whole_sha256=d1,
            chunks=[ChunkMetadata(digest=d1, size_bytes=len(c1_data), offset=0, index=0)],
        )

        gc = ArtifactGarbageCollector(store)
        # Dry run
        dry_report = gc.collect_orphans(active_manifests=[manifest], dry_run=True)
        assert dry_report.unreferenced_chunks == 1
        assert dry_report.referenced_chunks == 1
        assert store.has_chunk(d2) is True  # still present

        # Actual run
        real_report = gc.collect_orphans(active_manifests=[manifest], dry_run=False)
        assert real_report.unreferenced_chunks == 1
        assert store.has_chunk(d1) is True  # preserved
        assert store.has_chunk(d2) is False  # pruned

    def test_gc_with_protected_digests(self, tmp_path):
        store = ArtifactChunkStore(storage_root=str(tmp_path / "cas"))
        data = b"Protected uncommitted chunk"
        d = hashlib.sha256(data).hexdigest()
        store.put_chunk(d, data)

        gc = ArtifactGarbageCollector(store)
        report = gc.collect_orphans(active_manifests=[], protected_digests={d}, dry_run=False)
        assert report.unreferenced_chunks == 0
        assert store.has_chunk(d) is True

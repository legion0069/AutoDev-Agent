"""
test_artifact_sync.py - Unit tests for ArtifactSyncManager and CAS sync (v2.9)
"""

import pytest
import shutil
import tempfile
from pathlib import Path
from core.cluster.artifact_sync import ArtifactSyncManager, SyncStatus


def test_artifact_store_and_sha256_digest():
    temp_dir = tempfile.mkdtemp()
    try:
        sync = ArtifactSyncManager(node_id="worker-01", storage_root=temp_dir)
        content = "def calculate_speedup(p, n):\n    return 1 / ((1 - p) + (p / n))\n"

        entry = sync.store_artifact(
            artifact_id="art_amdahl",
            relative_path="src/amdahl.py",
            content=content,
            content_type="text/x-python",
        )

        assert entry.artifact_id == "art_amdahl"
        assert entry.size_bytes == len(content.encode("utf-8"))
        assert len(entry.sha256) == 64
        assert entry.sync_status == SyncStatus.SYNCED

        # Verify disk file written
        disk_file = Path(temp_dir) / "src/amdahl.py"
        assert disk_file.exists()
        assert sync.get_artifact_text("art_amdahl") == content

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_incremental_delta_sync():
    temp1 = tempfile.mkdtemp()
    temp2 = tempfile.mkdtemp()
    try:
        node1 = ArtifactSyncManager(node_id="node-01", storage_root=temp1)
        node2 = ArtifactSyncManager(node_id="node-02", storage_root=temp2)

        node1.store_artifact("art_01", "file1.txt", "Hello from Node 1")
        node1.store_artifact("art_02", "file2.txt", "Common data")
        node2.store_artifact("art_02", "file2.txt", "Common data")

        # Delta from node1 to node2: only art_01 should be missing in node2
        manifest1 = node1.export_manifest_dict()
        delta = node2.compute_sync_delta(manifest1)
        assert delta == ["art_01"]

        # Perform sync
        report = node2.sync_from_remote(
            remote_node_id="node-01",
            remote_manifest=manifest1,
            fetch_blob_callback=lambda art_id: node1.get_artifact_content(art_id),
        )

        assert report.synced_count == 1
        assert "art_01" in report.synced_artifacts
        assert node2.get_artifact_text("art_01") == "Hello from Node 1"

    finally:
        shutil.rmtree(temp1, ignore_errors=True)
        shutil.rmtree(temp2, ignore_errors=True)

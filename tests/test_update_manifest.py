"""Tests for scripts/update_manifest.py"""
import hashlib
import tempfile
import shutil
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))

import pytest


@pytest.fixture
def repo_root():
    """Get the repository root directory."""
    return Path(__file__).resolve().parents[1]


def test_update_manifest_can_import():
    """Test that update_manifest.py can be imported."""
    import update_manifest
    # Should import without errors


def test_update_manifest_has_expected_variables():
    """Test that update_manifest.py defines expected variables."""
    import update_manifest
    assert hasattr(update_manifest, 'root')
    assert hasattr(update_manifest, 'files')


def test_sha256_computation():
    """Test SHA256 hash computation matches expected format."""
    # Create a temporary file with known content
    with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
        f.write('test content\n')
        temp_path = Path(f.name)
    
    try:
        # Compute hash
        computed_hash = hashlib.sha256(temp_path.read_bytes()).hexdigest()
        
        # Verify format (64 hex characters)
        assert len(computed_hash) == 64
        assert all(c in '0123456789abcdef' for c in computed_hash)
        
        # Verify it matches known hash for this content
        expected_hash = hashlib.sha256(b'test content\n').hexdigest()
        assert computed_hash == expected_hash
    finally:
        temp_path.unlink()


def test_update_manifest_excludes_git():
    """Test that .git directory is excluded from file list."""
    import update_manifest
    
    # Check that no file in the list has .git in its path
    for file_path in update_manifest.files:
        rel_path = file_path.relative_to(update_manifest.root)
        assert '.git' not in rel_path.parts


def test_update_manifest_excludes_pycache():
    """Test that __pycache__ directory is excluded."""
    import update_manifest
    
    for file_path in update_manifest.files:
        rel_path = file_path.relative_to(update_manifest.root)
        assert '__pycache__' not in rel_path.parts


def test_update_manifest_excludes_sha256sums():
    """Test that SHA256SUMS itself is excluded from the list."""
    import update_manifest
    
    for file_path in update_manifest.files:
        assert file_path.name != 'SHA256SUMS'


def test_sha256sums_file_format(repo_root):
    """Test that generated SHA256SUMS has correct format."""
    sha256sums = repo_root / 'SHA256SUMS'
    if not sha256sums.exists():
        pytest.skip("SHA256SUMS not yet generated")
    
    content = sha256sums.read_text()
    lines = [line for line in content.splitlines() if line.strip()]
    
    for line in lines:
        # Format should be: <64-char-hash><space><space><filename>
        parts = line.split('  ', 1)
        assert len(parts) == 2, f"Invalid line format: {line}"
        
        hash_part, filename = parts
        assert len(hash_part) == 64, f"Invalid hash length: {hash_part}"
        assert all(c in '0123456789abcdef' for c in hash_part), f"Invalid hash chars: {hash_part}"
        assert filename, "Empty filename"


def test_update_manifest_creates_sorted_output(repo_root):
    """Test that the file list is sorted."""
    sha256sums = repo_root / 'SHA256SUMS'
    if not sha256sums.exists():
        pytest.skip("SHA256SUMS not yet generated")
    
    content = sha256sums.read_text()
    lines = content.splitlines()
    filenames = [line.split('  ', 1)[1] for line in lines if '  ' in line]
    
    # Verify files are sorted
    assert filenames == sorted(filenames), "Files in SHA256SUMS should be sorted"

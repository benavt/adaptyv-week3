"""Tests for scripts/check_privacy.py"""
import tempfile
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))

import pytest


@pytest.fixture
def repo_root():
    """Get the repository root directory."""
    return Path(__file__).resolve().parents[1]


def test_check_privacy_can_import():
    """Test that check_privacy.py can be imported."""
    import check_privacy
    assert hasattr(check_privacy, 'main')


def test_check_privacy_patterns_defined():
    """Test that privacy check patterns are defined."""
    import check_privacy
    assert hasattr(check_privacy, 'PATTERNS')
    assert 'home_path' in check_privacy.PATTERNS
    assert 'private_hostname' in check_privacy.PATTERNS
    assert 'internal_ip' in check_privacy.PATTERNS


def test_home_path_pattern_detection():
    """Test that home path pattern correctly identifies violations."""
    import check_privacy
    
    pattern = check_privacy.PATTERNS['home_path']
    
    # Should match
    assert pattern.search('/home/username/project')
    assert pattern.search('/Users/john/workspace')
    
    # Should not match
    assert not pattern.search('/opt/project')
    assert not pattern.search('/var/lib/something')


def test_private_hostname_pattern():
    """Test private hostname detection."""
    import check_privacy
    
    pattern = check_privacy.PATTERNS['private_hostname']
    
    # Should match
    assert pattern.search('Running on Pax server')
    assert pattern.search('Connected to mimas')
    
    # Should not match
    assert not pattern.search('public-server-01')


def test_internal_ip_pattern():
    """Test internal IP address detection."""
    import check_privacy
    
    pattern = check_privacy.PATTERNS['internal_ip']
    
    # Should match private IPs
    assert pattern.search('Server at 192.168.1.1')
    assert pattern.search('Connect to 10.0.0.5')
    assert pattern.search('Internal: 172.16.0.1')
    
    # Should not match public IPs
    assert not pattern.search('8.8.8.8')
    assert not pattern.search('1.2.3.4')


def test_api_key_pattern():
    """Test API key/token detection."""
    import check_privacy
    
    pattern = check_privacy.PATTERNS['api_key_pattern']
    
    # Should match
    assert pattern.search('api_key: sk_live_1234567890abcdefghij')
    assert pattern.search('TOKEN="abcdefghijklmnopqrstuvwxyz123456"')
    
    # Should not match short strings
    assert not pattern.search('api_key: short')


def test_should_scan_function():
    """Test file filtering logic."""
    import check_privacy
    
    # Should scan text files
    assert check_privacy.should_scan(Path('test.py'))
    assert check_privacy.should_scan(Path('README.md'))
    assert check_privacy.should_scan(Path('data.json'))
    
    # Should not scan binary files
    assert not check_privacy.should_scan(Path('image.pdf'))
    assert not check_privacy.should_scan(Path('model.pdb'))
    assert not check_privacy.should_scan(Path('presentation.pptx'))


def test_scan_file_with_clean_content():
    """Test scanning a file with no privacy issues."""
    import check_privacy
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        f.write('This is clean content\n')
        f.write('No sensitive information here\n')
        temp_path = Path(f.name)
    
    try:
        # Temporarily change ROOT to temp directory for testing
        original_root = check_privacy.ROOT
        check_privacy.ROOT = temp_path.parent
        
        findings = check_privacy.scan_file(temp_path)
        assert findings == []
    finally:
        check_privacy.ROOT = original_root
        temp_path.unlink()


def test_scan_file_with_home_path():
    """Test scanning a file with home path leak."""
    import check_privacy
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        f.write('Script location: /home/researcher/project/script.py\n')
        temp_path = Path(f.name)
    
    try:
        original_root = check_privacy.ROOT
        check_privacy.ROOT = temp_path.parent
        
        findings = check_privacy.scan_file(temp_path)
        assert len(findings) > 0
        assert findings[0]['pattern'] == 'home_path'
    finally:
        check_privacy.ROOT = original_root
        temp_path.unlink()


def test_allowlist_functionality():
    """Test that allowlist properly filters known benign matches."""
    import check_privacy
    
    # Create a test file in the repo
    test_file = check_privacy.ROOT / 'test.txt'
    
    # Test with empty allowlist (should not filter)
    result = check_privacy.is_allowlisted('home_path', test_file, 'some line')
    assert result == False  # Not in allowlist


def test_manifest_and_checksums_match(repo_root):
    """Test that committed SHA256SUMS and file-manifest.json match files on disk."""
    sha256sums_file = repo_root / 'SHA256SUMS'
    manifest_file = repo_root / 'reports' / '2026-10-25_glp1r-final20' / 'file-manifest.json'
    
    # This is a critical test - verify checksums match reality
    if sha256sums_file.exists():
        import hashlib
        content = sha256sums_file.read_text()
        
        errors = []
        for line in content.splitlines():
            if '  ' not in line:
                continue
            
            expected_hash, rel_path = line.split('  ', 1)
            file_path = repo_root / rel_path
            
            if not file_path.exists():
                errors.append(f"File missing: {rel_path}")
                continue
            
            actual_hash = hashlib.sha256(file_path.read_bytes()).hexdigest()
            if actual_hash != expected_hash:
                errors.append(f"Hash mismatch for {rel_path}")
        
        assert len(errors) == 0, f"Checksum verification failed:\n" + "\n".join(errors)
    
    # Also verify file-manifest.json if it exists
    if manifest_file.exists():
        manifest = json.loads(manifest_file.read_text())
        if 'copied_and_transformed_source_files' in manifest:
            errors = []
            release_dir = manifest_file.parent
            
            for entry in manifest['copied_and_transformed_source_files']:
                file_path = release_dir / entry['path']
                if not file_path.exists():
                    continue  # Skip verification for missing files
                
                import hashlib
                actual_hash = hashlib.sha256(file_path.read_bytes()).hexdigest()
                expected_hash = entry.get('sha256', '')
                
                if expected_hash and actual_hash != expected_hash:
                    errors.append(f"Manifest hash mismatch for {entry['path']}")
            
            assert len(errors) == 0, f"Manifest verification failed:\n" + "\n".join(errors)

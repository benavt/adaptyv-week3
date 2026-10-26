"""Tests for scripts/verify_release.py"""
import json
import hashlib
from pathlib import Path
import sys

# Add scripts directory to path for imports
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))

import pytest


@pytest.fixture
def repo_root():
    """Get the repository root directory."""
    return Path(__file__).resolve().parents[1]


@pytest.fixture
def release_dir(repo_root):
    """Get the release directory."""
    return repo_root / 'reports' / '2026-10-25_glp1r-final20'


def test_release_directory_exists(release_dir):
    """Test that the release directory exists."""
    assert release_dir.exists(), f"Release directory not found: {release_dir}"
    assert release_dir.is_dir(), f"Release path is not a directory: {release_dir}"


def test_required_files_exist(release_dir):
    """Test that all required files exist in the release."""
    required_files = [
        'provenance.json',
        'submission.csv',
        'final20.fasta',
        'file-manifest.json',
        'figure-provenance.json',
        'GLP1R_Week3_Final20_Final_Writeup.pdf',
    ]
    
    for filename in required_files:
        file_path = release_dir / filename
        assert file_path.exists(), f"Required file missing: {filename}"


def test_provenance_json_structure(release_dir):
    """Test that provenance.json has the expected structure."""
    provenance_file = release_dir / 'provenance.json'
    assert provenance_file.exists()
    
    with provenance_file.open() as f:
        data = json.load(f)
    
    assert 'records' in data, "provenance.json missing 'records' key"
    assert isinstance(data['records'], list), "'records' should be a list"
    assert len(data['records']) > 0, "'records' should not be empty"


def test_submission_csv_structure(release_dir):
    """Test that submission.csv has the expected structure."""
    import csv
    
    submission_file = release_dir / 'submission.csv'
    assert submission_file.exists()
    
    with submission_file.open() as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    
    assert len(rows) == 20, f"Expected 20 rows, got {len(rows)}"
    assert list(rows[0].keys()) == ['name', 'sequence', 'molecule_class']
    assert all(r['molecule_class'] == 'single_chain' for r in rows)


def test_fasta_format(release_dir):
    """Test that final20.fasta is properly formatted."""
    fasta_file = release_dir / 'final20.fasta'
    assert fasta_file.exists()
    
    content = fasta_file.read_text()
    lines = [line for line in content.splitlines() if line.strip()]
    
    # Should have headers and sequences
    headers = [line for line in lines if line.startswith('>')]
    sequences = [line for line in lines if not line.startswith('>')]
    
    assert len(headers) == 20, f"Expected 20 FASTA headers, got {len(headers)}"
    assert len(sequences) >= 20, f"Expected at least 20 sequence lines, got {len(sequences)}"


def test_models_directory_structure(release_dir):
    """Test that models directory has expected structure."""
    models_dir = release_dir / 'models'
    assert models_dir.exists() and models_dir.is_dir()
    
    # Should have exactly 20 model directories
    model_dirs = [d for d in models_dir.iterdir() if d.is_dir()]
    assert len(model_dirs) == 20, f"Expected 20 model directories, got {len(model_dirs)}"
    
    # Each model directory should have required files
    for model_dir in model_dirs:
        assert (model_dir / 'confidence.json').exists(), f"Missing confidence.json in {model_dir.name}"


def test_scores_directory_structure(release_dir):
    """Test that scores directory has expected structure."""
    scores_dir = release_dir / 'scores'
    assert scores_dir.exists() and scores_dir.is_dir()
    
    # Should have exactly 20 score files
    score_files = list(scores_dir.glob('*.json'))
    assert len(score_files) == 20, f"Expected 20 score files, got {len(score_files)}"


def test_verify_release_can_import():
    """Test that verify_release.py can be imported without errors."""
    import verify_release
    assert hasattr(verify_release, 'main')


def test_verify_release_has_required_functions():
    """Test that verify_release.py has required functions."""
    import verify_release
    assert callable(verify_release.main)
    assert callable(verify_release.sha)
    assert callable(verify_release.rows)

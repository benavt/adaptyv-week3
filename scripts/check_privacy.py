#!/usr/bin/env python3
"""Scan committed text files for private infrastructure details that shouldn't be public.

This script looks for:
- Absolute home paths like /home/<user>/ or /Users/<user>/
- Private hostnames (built from fragments to avoid literal strings in repo)
- Internal IP addresses (private ranges)
- Potential tokens or API keys (common patterns)

Exits with code 1 if potential leaks are found, 0 if clean.
With --report-only flag, always exits with 0 (for CI reporting).

Scanning capabilities:
- PDF text content (via pdftotext) and embedded attachments (via pdfdetach)
- Office Open XML files (.docx, .xlsx, .pptx) - scans internal XML
- Archive members (.zip, .tar, .gz, .bz2, .npz) - extracts and scans contents
- Plain text files
- Case-insensitive pattern matching including embedded forms
"""
import re
import json
import sys
import argparse
import subprocess
import tempfile
import zipfile
import tarfile
import gzip
import bz2
import shutil
from pathlib import Path
from typing import List, Dict, Optional

ROOT = Path(__file__).resolve().parents[1]

# Build private hostname patterns from fragments (never store literally in repo)
# Fragment list format: [(prefix, suffix), ...] to avoid literal reconstruction
_HOSTNAME_FRAGMENTS = [
    ('p', 'ax'),      # private cluster name
    ('mim', 'as'),    # private compute name
]

def _build_hostname_pattern():
    """Build hostname pattern from fragments at runtime."""
    hostnames = [''.join(frag) for frag in _HOSTNAME_FRAGMENTS]
    return re.compile(r'(?:' + '|'.join(hostnames) + r')(?=\W|_|$)', re.IGNORECASE)

# Patterns to detect potential leaks (all case-insensitive for comprehensive coverage)
PATTERNS = {
    'home_path': re.compile(r'/(?:home|users)/[a-zA-Z0-9_-]+/', re.IGNORECASE),
    'private_hostname': _build_hostname_pattern(),
    'internal_ip': re.compile(r'\b(?:10\.\d{1,3}\.\d{1,3}\.\d{1,3}|172\.(?:1[6-9]|2[0-9]|3[01])\.\d{1,3}\.\d{1,3}|192\.168\.\d{1,3}\.\d{1,3})\b'),
    'api_key_pattern': re.compile(r'(?:api[_-]?key|token|secret|password)\s*[:=]\s*["\']?([a-zA-Z0-9_\-]{20,})["\']?', re.IGNORECASE),
}

# Allowlist for known benign matches
# Format: (pattern_name, file_pattern, line_content_substring)
ALLOWLIST = [
    # Example: ('home_path', 'README.md', 'Example: /home/user/workspace')
    # Add specific allowlist entries here after verification
]

# Global tracking for PDF tool availability
_PDF_TOOLS_CHECKED = False
_PDF_TOOLS_AVAILABLE = False


def should_skip_path(path: Path) -> bool:
    """Determine if a file path should be explicitly excluded from scanning.
    
    Only skips specific files by explicit PATH, never by extension alone.
    """
    # Get relative path
    try:
        rel_path = path.relative_to(ROOT)
    except ValueError:
        rel_path = path
    
    rel_path_str = str(rel_path)
    
    # Skip only specific files that contain patterns for testing/implementation
    skip_files = {
        'scripts/check_privacy.py',  # Contains fragment patterns
        'tests/test_check_privacy.py',  # Contains test patterns
    }
    
    if rel_path_str in skip_files:
        return True
    
    # Skip git internals and cache directories by path component
    skip_path_components = {'.git', '__pycache__', '.venv', 'node_modules', '.pytest_cache'}
    if any(part in skip_path_components for part in rel_path.parts):
        return True
    
    return False


def should_skip_credentials_check(path: Path) -> bool:
    """Check if file should skip credential pattern checks (protein sequences look like keys)."""
    # Skip credential checks for biological sequence and structure files
    skip_cred_extensions = {'.fasta', '.a3m', '.pdb', '.cif', '.csv'}
    return path.suffix.lower() in skip_cred_extensions


def check_pdf_tools_available() -> bool:
    """Check if PDF extraction tools are available."""
    global _PDF_TOOLS_CHECKED, _PDF_TOOLS_AVAILABLE
    
    if _PDF_TOOLS_CHECKED:
        return _PDF_TOOLS_AVAILABLE
    
    _PDF_TOOLS_CHECKED = True
    
    # Check for pdftotext
    try:
        subprocess.run(['pdftotext', '-v'], capture_output=True, timeout=5)
        pdftotext_ok = True
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pdftotext_ok = False
    
    # Check for pdfdetach
    try:
        subprocess.run(['pdfdetach', '-h'], capture_output=True, timeout=5)
        pdfdetach_ok = True
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pdfdetach_ok = False
    
    _PDF_TOOLS_AVAILABLE = pdftotext_ok and pdfdetach_ok
    return _PDF_TOOLS_AVAILABLE


def extract_pdf_text(pdf_path: Path) -> str:
    """Extract text from PDF using pdftotext, including attachments.
    
    Raises RuntimeError if PDF tools are not available.
    """
    if not check_pdf_tools_available():
        raise RuntimeError(
            f"PDF tools (pdftotext/pdfdetach) not available but PDF found: {pdf_path}\n"
            "Install poppler-utils: sudo apt-get install poppler-utils"
        )
    
    text_parts = []
    
    # Extract main PDF text
    try:
        result = subprocess.run(
            ['pdftotext', '-layout', str(pdf_path), '-'],
            capture_output=True,
            text=True,
            timeout=30
        )
        if result.returncode == 0:
            text_parts.append(result.stdout)
    except subprocess.TimeoutExpired:
        pass  # Timed out, skip this PDF
    
    # Extract embedded attachments
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        try:
            subprocess.run(
                ['pdfdetach', '-saveall', '-o', str(tmppath), str(pdf_path)],
                capture_output=True,
                timeout=30
            )
            # Scan extracted files
            for attachment in tmppath.iterdir():
                if attachment.is_file():
                    try:
                        text_parts.append(attachment.read_text(encoding='utf-8', errors='ignore'))
                    except Exception:
                        pass
        except subprocess.TimeoutExpired:
            pass  # Timed out
    
    return '\n'.join(text_parts)


def extract_office_xml(office_path: Path) -> str:
    """Extract text from Office Open XML files (.docx, .xlsx, .pptx)."""
    text_parts = []
    
    try:
        with zipfile.ZipFile(office_path, 'r') as zf:
            # Scan all XML files in the archive
            for name in zf.namelist():
                if name.endswith('.xml'):
                    try:
                        content = zf.read(name).decode('utf-8', errors='ignore')
                        text_parts.append(content)
                    except Exception:
                        pass
    except Exception:
        pass  # Not a valid zip or Office file
    
    return '\n'.join(text_parts)


def extract_archive_contents(archive_path: Path) -> str:
    """Extract and scan contents of archive files (.zip, .npz, .tar, .gz, .bz2).
    
    Uses text detection heuristic to skip binary content.
    """
    text_parts = []
    
    try:
        # Handle ZIP files (including .npz which are ZIP-based)
        if archive_path.suffix.lower() in {'.zip', '.npz'}:
            with zipfile.ZipFile(archive_path, 'r') as zf:
                for name in zf.namelist():
                    try:
                        content = zf.read(name)
                        if looks_like_text(content):
                            text = content.decode('utf-8', errors='ignore')
                            text_parts.append(text)
                    except Exception:
                        pass
        
        # Handle TAR files
        elif archive_path.suffix.lower() in {'.tar'}:
            with tarfile.open(archive_path, 'r') as tf:
                for member in tf.getmembers():
                    if member.isfile():
                        try:
                            f = tf.extractfile(member)
                            if f:
                                content = f.read()
                                if looks_like_text(content):
                                    text = content.decode('utf-8', errors='ignore')
                                    text_parts.append(text)
                        except Exception:
                            pass
        
        # Handle gzip files
        elif archive_path.suffix.lower() == '.gz':
            with gzip.open(archive_path, 'rb') as f:
                try:
                    content = f.read()
                    if looks_like_text(content):
                        text = content.decode('utf-8', errors='ignore')
                        text_parts.append(text)
                except Exception:
                    pass
        
        # Handle bz2 files
        elif archive_path.suffix.lower() == '.bz2':
            with bz2.open(archive_path, 'rb') as f:
                try:
                    content = f.read()
                    if looks_like_text(content):
                        text = content.decode('utf-8', errors='ignore')
                        text_parts.append(text)
                except Exception:
                    pass
    
    except Exception:
        pass  # Archive couldn't be opened or is corrupted
    
    return '\n'.join(text_parts)


def is_allowlisted(pattern_name: str, file_path: Path, line: str) -> bool:
    """Check if a match is in the allowlist."""
    try:
        rel_path = str(file_path.relative_to(ROOT))
    except ValueError:
        # Path is not relative to ROOT (e.g., in tests)
        rel_path = str(file_path)
    
    for allow_pattern, allow_file, allow_content in ALLOWLIST:
        if pattern_name == allow_pattern:
            if allow_file in rel_path and allow_content in line:
                return True
    return False


def scan_content(content: str, file_path: Path, skip_credentials: bool = False) -> List[Dict]:
    """Scan text content for privacy issues."""
    findings = []
    lines = content.splitlines()
    
    # Get relative path for reporting
    try:
        rel_file_path = str(file_path.relative_to(ROOT))
    except ValueError:
        # Path is not relative to ROOT (e.g., in tests)
        rel_file_path = str(file_path)
    
    for line_num, line in enumerate(lines, 1):
        for pattern_name, pattern in PATTERNS.items():
            # Skip credential checks for biological files
            if skip_credentials and pattern_name == 'api_key_pattern':
                continue
                
            matches = pattern.finditer(line)
            for match in matches:
                if not is_allowlisted(pattern_name, file_path, line):
                    findings.append({
                        'file': rel_file_path,
                        'line': line_num,
                        'pattern': pattern_name,
                        'match': match.group(0),
                        'context': line.strip()[:100]  # First 100 chars
                    })
    
    return findings


def looks_like_text(content: bytes) -> bool:
    """Heuristic to determine if content looks like text vs binary data.
    
    Returns True if content appears to be text, False if likely binary.
    """
    if len(content) == 0:
        return False
    
    # Try UTF-8 decode
    try:
        text = content.decode('utf-8')
    except UnicodeDecodeError:
        # If it can't decode at all as UTF-8, check with errors='ignore'
        text = content.decode('utf-8', errors='ignore')
        # If too many bytes were skipped, it's probably binary
        if len(text) < len(content) * 0.8:  # More than 20% non-UTF8 bytes
            return False
    
    if len(text) == 0:
        return False
    
    # Count problematic characters
    # Null bytes are strong indicator of binary
    null_bytes = text.count('\x00')
    if null_bytes > len(text) * 0.01:  # More than 1% null bytes
        return False
    
    # Count other control characters (excluding common whitespace)
    control_chars = sum(1 for c in text if ord(c) < 32 and c not in '\n\r\t')
    
    # If more than 10% control characters, likely binary
    if control_chars > len(text) * 0.10:
        return False
    
    # Check for high-bit characters (often seen in binary data)
    high_bit = sum(1 for c in text if ord(c) > 127)
    if high_bit > len(text) * 0.30:  # More than 30% high-bit chars
        return False
    
    return True


def try_decode_as_text(file_path: Path) -> Optional[str]:
    """Try to decode a file as text. Returns None if it appears to be binary."""
    try:
        content = file_path.read_bytes()
        
        if looks_like_text(content):
            # Decode (using errors='ignore' if needed)
            try:
                return content.decode('utf-8')
            except UnicodeDecodeError:
                return content.decode('utf-8', errors='ignore')
        else:
            return None
    
    except Exception:
        return None


def scan_file(file_path: Path) -> List[Dict]:
    """Scan a single file for privacy issues."""
    findings = []
    
    # Check if path should be skipped
    if should_skip_path(file_path):
        return findings
    
    skip_credentials = should_skip_credentials_check(file_path)
    
    try:
        # Handle PDF files
        if file_path.suffix.lower() == '.pdf':
            content = extract_pdf_text(file_path)
            if content:
                findings.extend(scan_content(content, file_path, skip_credentials))
        
        # Handle Office Open XML files
        elif file_path.suffix.lower() in {'.docx', '.xlsx', '.pptx'}:
            content = extract_office_xml(file_path)
            if content:
                findings.extend(scan_content(content, file_path, skip_credentials))
        
        # Handle archive files - scan their contents
        elif file_path.suffix.lower() in {'.zip', '.npz', '.tar', '.gz', '.bz2'}:
            content = extract_archive_contents(file_path)
            if content:
                findings.extend(scan_content(content, file_path, skip_credentials))
        
        # Skip truly opaque binary formats by extension
        elif file_path.suffix.lower() in {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.ico',
                                           '.pyc', '.so', '.dylib', '.dll', '.exe', '.bin'}:
            return findings
        
        # For everything else, try to decode as text
        else:
            content = try_decode_as_text(file_path)
            if content:
                findings.extend(scan_content(content, file_path, skip_credentials))
            
    except Exception as e:
        # Re-raise RuntimeError for missing PDF tools
        if isinstance(e, RuntimeError) and 'PDF tools' in str(e):
            raise
        # Skip other files that can't be read
        pass
    
    return findings


def main():
    """Scan all relevant files in the repository."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report-only', action='store_true',
                        help='Report findings but exit with 0 (for CI)')
    args = parser.parse_args()
    
    all_findings = []
    
    # Scan all files in the repository
    for file_path in ROOT.rglob('*'):
        if file_path.is_file():
            findings = scan_file(file_path)
            all_findings.extend(findings)
    
    if all_findings:
        print("⚠️  Privacy check found potential infrastructure leaks:\n")
        print(json.dumps(all_findings, indent=2))
        print(f"\n❌ Found {len(all_findings)} potential leak(s) across {len(set(f['file'] for f in all_findings))} file(s)")
        print("\nReview these findings and either:")
        print("1. Remove sensitive data from the files")
        print("2. Add allowlist entries in scripts/check_privacy.py if these are false positives")
        
        if args.report_only:
            print("\n(Running in report-only mode, not failing)")
            return 0
        return 1
    else:
        print("✅ Privacy check passed: No infrastructure leaks detected")
        return 0


if __name__ == '__main__':
    sys.exit(main())

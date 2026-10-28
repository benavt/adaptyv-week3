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
import shutil
from pathlib import Path
from typing import List, Dict

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


def should_skip_path(path: Path) -> bool:
    """Determine if a file path should be explicitly excluded from scanning."""
    # Skip git internals, cache directories, tests, and the scripts directory itself
    # (tests and scripts contain example patterns for testing purposes)
    skip_parts = {'.git', '__pycache__', '.venv', '_private', 'node_modules', 'tests'}
    if any(part in skip_parts for part in path.parts):
        return True
    
    # Skip the check_privacy.py script itself (contains fragment patterns)
    if path.name == 'check_privacy.py':
        return True
    
    return False


def should_skip_credentials_check(path: Path) -> bool:
    """Check if file should skip credential pattern checks (protein sequences look like keys)."""
    # Skip credential checks for biological sequence and structure files
    skip_cred_extensions = {'.fasta', '.a3m', '.pdb', '.cif', '.csv'}
    return path.suffix.lower() in skip_cred_extensions


def extract_pdf_text(pdf_path: Path) -> str:
    """Extract text from PDF using pdftotext, including attachments."""
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
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass  # pdftotext not available or timed out
    
    # Extract embedded attachments
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        try:
            # Extract all attachments
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
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass  # pdfdetach not available or timed out
    
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


def is_allowlisted(pattern_name: str, file_path: Path, line: str) -> bool:
    """Check if a match is in the allowlist."""
    rel_path = str(file_path.relative_to(ROOT))
    for allow_pattern, allow_file, allow_content in ALLOWLIST:
        if pattern_name == allow_pattern:
            if allow_file in rel_path and allow_content in line:
                return True
    return False


def scan_content(content: str, file_path: Path, skip_credentials: bool = False) -> List[Dict]:
    """Scan text content for privacy issues."""
    findings = []
    lines = content.splitlines()
    
    for line_num, line in enumerate(lines, 1):
        for pattern_name, pattern in PATTERNS.items():
            # Skip credential checks for biological files
            if skip_credentials and pattern_name == 'api_key_pattern':
                continue
                
            matches = pattern.finditer(line)
            for match in matches:
                if not is_allowlisted(pattern_name, file_path, line):
                    findings.append({
                        'file': str(file_path.relative_to(ROOT)),
                        'line': line_num,
                        'pattern': pattern_name,
                        'match': match.group(0),
                        'context': line.strip()[:100]  # First 100 chars
                    })
    
    return findings


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
        
        # Handle text files
        else:
            # Skip binary files by extension
            skip_binary_extensions = {
                '.jpg', '.png', '.gif', '.pyc', '.so', '.dylib', 
                '.exe', '.bin', '.gz', '.zip', '.tar', '.bz2'
            }
            if file_path.suffix.lower() in skip_binary_extensions:
                return findings
            
            # Try to read as text
            content = file_path.read_text(encoding='utf-8', errors='ignore')
            findings.extend(scan_content(content, file_path, skip_credentials))
            
    except Exception as e:
        # Skip files that can't be read
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

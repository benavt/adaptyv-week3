#!/usr/bin/env python3
"""Scan committed text files for private infrastructure details that shouldn't be public.

This script looks for:
- Absolute home paths like /home/<user>/ or /Users/<user>/
- Private hostnames (e.g. Pax, mimas)
- Internal IP addresses (private ranges)
- Potential tokens or API keys (common patterns)

Exits with code 1 if potential leaks are found, 0 if clean.
With --report-only flag, always exits with 0 (for CI reporting).
"""
import re
import json
import sys
import argparse
from pathlib import Path
from typing import List, Dict, Tuple

ROOT = Path(__file__).resolve().parents[1]

# Patterns to detect potential leaks (all case-insensitive for comprehensive coverage)
PATTERNS = {
    'home_path': re.compile(r'/(?:home|users)/[a-zA-Z0-9_-]+/', re.IGNORECASE),
    'private_hostname': re.compile(r'(?:pax|mimas)(?=\W|_|$)', re.IGNORECASE),
    'internal_ip': re.compile(r'\b(?:10\.\d{1,3}\.\d{1,3}\.\d{1,3}|172\.(?:1[6-9]|2[0-9]|3[01])\.\d{1,3}\.\d{1,3}|192\.168\.\d{1,3}\.\d{1,3})\b'),
    'api_key_pattern': re.compile(r'(?:api[_-]?key|token|secret|password)\s*[:=]\s*["\']?([a-zA-Z0-9_\-]{20,})["\']?', re.IGNORECASE),
}

# Allowlist for known benign matches
# Format: (pattern_name, file_pattern, line_content_substring)
ALLOWLIST = [
    # Example: ('home_path', 'README.md', 'Example: /home/user/workspace')
    # Add specific allowlist entries here after verification
]


def should_scan(path: Path) -> bool:
    """Determine if a file should be scanned for privacy issues."""
    # Skip binary files and non-text extensions
    skip_extensions = {
        '.pdf', '.pptx', '.jpg', '.png', '.gif', '.cif', '.pdb',
        '.pyc', '.so', '.dylib', '.exe', '.bin', '.gz', '.zip',
    }
    
    if path.suffix.lower() in skip_extensions:
        return False
    
    # Skip git internals, cache directories, tests, and the scripts directory itself
    # (tests and scripts contain example patterns for testing purposes)
    skip_parts = {'.git', '__pycache__', '.venv', '_private', 'node_modules', 'tests'}
    if any(part in skip_parts for part in path.parts):
        return False
    
    # Skip the check_privacy.py script itself (contains example patterns)
    if path.name == 'check_privacy.py':
        return False
    
    # Only scan text-like files
    text_extensions = {
        '.py', '.md', '.txt', '.json', '.csv', '.yaml', '.yml',
        '.sh', '.bash', '.fasta', '.rst', '.toml', '.ini', '.cfg',
    }
    
    # Scan if has text extension or no extension (like scripts)
    return path.suffix.lower() in text_extensions or (path.is_file() and not path.suffix)


def is_allowlisted(pattern_name: str, file_path: Path, line: str) -> bool:
    """Check if a match is in the allowlist."""
    rel_path = str(file_path.relative_to(ROOT))
    for allow_pattern, allow_file, allow_content in ALLOWLIST:
        if pattern_name == allow_pattern:
            if allow_file in rel_path and allow_content in line:
                return True
    return False


def scan_file(file_path: Path) -> List[Dict]:
    """Scan a single file for privacy issues."""
    findings = []
    
    try:
        # Try to read as text
        content = file_path.read_text(encoding='utf-8', errors='ignore')
        lines = content.splitlines()
        
        for line_num, line in enumerate(lines, 1):
            for pattern_name, pattern in PATTERNS.items():
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
    except Exception as e:
        # Skip files that can't be read as text
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
        if file_path.is_file() and should_scan(file_path):
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

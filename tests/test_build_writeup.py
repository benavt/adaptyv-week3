"""Tests for scripts/build_writeup.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))

import pytest

# Check if reportlab is available
try:
    import reportlab
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False

pytestmark = pytest.mark.skipif(
    not REPORTLAB_AVAILABLE,
    reason="reportlab not installed (not required for lightweight CI)"
)


@pytest.fixture
def repo_root():
    """Get the repository root directory."""
    return Path(__file__).resolve().parents[1]


@pytest.fixture
def release_dir(repo_root):
    """Get the release directory."""
    return repo_root / 'reports' / '2026-10-25_glp1r-final20'


def test_build_writeup_has_required_modules():
    """Test that required modules are defined."""
    import build_writeup
    assert hasattr(build_writeup, 'ROOT')
    assert hasattr(build_writeup, 'inline')


def test_inline_function_escapes_html():
    """Test that inline() properly escapes HTML."""
    import build_writeup
    
    # Test basic HTML escaping
    assert '&lt;' in build_writeup.inline('<tag>')
    assert '&gt;' in build_writeup.inline('<tag>')
    assert '&amp;' in build_writeup.inline('a & b')


def test_inline_function_handles_bold():
    """Test that inline() converts markdown bold to HTML."""
    import build_writeup
    
    result = build_writeup.inline('**bold text**')
    assert '<b>bold text</b>' in result


def test_inline_function_handles_links():
    """Test that inline() converts markdown links to HTML."""
    import build_writeup
    
    result = build_writeup.inline('[link text](https://example.com)')
    assert 'link href="https://example.com"' in result
    assert 'link text' in result


@pytest.mark.skipif(not REPORTLAB_AVAILABLE, reason="reportlab not installed")
def test_manuscript_file_exists(release_dir):
    """Test that manuscript.md exists."""
    manuscript = release_dir / 'manuscript.md'
    assert manuscript.exists(), "manuscript.md not found"


@pytest.mark.skipif(not REPORTLAB_AVAILABLE, reason="reportlab not installed")
def test_manuscript_has_content(release_dir):
    """Test that manuscript.md has content."""
    manuscript = release_dir / 'manuscript.md'
    content = manuscript.read_text()
    assert len(content) > 100, "manuscript.md appears to be empty or too short"
    assert content.strip(), "manuscript.md is empty"


def test_build_writeup_page_dimensions():
    """Test that W constant is defined for page layout."""
    import build_writeup
    assert hasattr(build_writeup, 'W')
    assert isinstance(build_writeup.W, (int, float))
    assert build_writeup.W > 0


def test_build_writeup_styles_defined():
    """Test that PDF styles are properly configured."""
    import build_writeup
    assert hasattr(build_writeup, 'styles')
    
    required_styles = ['BodyReview', 'TitleReview', 'H2Review', 'CodeReview']
    for style_name in required_styles:
        assert style_name in build_writeup.styles, f"Missing style: {style_name}"


@pytest.mark.skipif(not REPORTLAB_AVAILABLE, reason="reportlab not installed")
def test_generated_pdf_exists(release_dir):
    """Test that the generated PDF exists."""
    pdf_path = release_dir / 'GLP1R_Week3_Final20_Final_Writeup.pdf'
    assert pdf_path.exists(), "Generated PDF not found"
    assert pdf_path.stat().st_size > 1000, "PDF file is too small"


@pytest.mark.skipif(not REPORTLAB_AVAILABLE, reason="reportlab not installed")
def test_pdf_is_valid_format(release_dir):
    """Test that the PDF has valid PDF header."""
    pdf_path = release_dir / 'GLP1R_Week3_Final20_Final_Writeup.pdf'
    if not pdf_path.exists():
        pytest.skip("PDF not yet generated")
    
    # Read first few bytes to check PDF header
    with pdf_path.open('rb') as f:
        header = f.read(5)
    
    assert header == b'%PDF-', "File does not have valid PDF header"


def test_build_writeup_argument_parser():
    """Test that argparse is configured."""
    import build_writeup
    assert hasattr(build_writeup, 'parser')
    assert hasattr(build_writeup, 'args')


def test_footer_function_exists():
    """Test that footer function is defined."""
    import build_writeup
    assert hasattr(build_writeup, 'footer')
    assert callable(build_writeup.footer)

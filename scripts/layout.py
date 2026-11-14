"""Repository-relative paths shared by tooling; callers own the checkout root."""
from pathlib import Path

GENERATED = Path('internal/generatedgo')
GENERATED_CODE = GENERATED / 'code'
BENCHMARKS = Path('benchmarks')
FIXTURES = Path('tests/fixtures')
MODULE_MARKERS = (BENCHMARKS / 'go.mod', Path('docs/reviews/go.mod'))

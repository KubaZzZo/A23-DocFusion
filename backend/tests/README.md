# Backend Tests

## Structure

```
backend/tests/
├── conftest.py                      # Pytest configuration
├── test_golden_evaluation.py        # Golden data evaluation tests
├── test_files/                      # Test input files
│   ├── sample.txt
│   └── sample.md
└── golden_data/                     # Expected outputs
    └── entity_extraction_golden.json
```

## Golden Test Data

Golden tests verify core functionality against known-good outputs:

- **Entity Extraction**: `entity_extraction_golden.json` defines expected entities for each test file
- **Recall Threshold**: Default 80% recall required (configurable per case)
- **Format Coverage**: Tests .txt and .md parsing

## Running Tests

```bash
# Run all backend tests
pytest backend/tests/

# Run only golden tests
pytest backend/tests/test_golden_evaluation.py

# Run with verbose output
pytest backend/tests/ -v

# Run specific test case
pytest backend/tests/test_golden_evaluation.py::test_entity_extraction_golden[sample.txt]
```

## Adding New Golden Cases

1. Add test file to `test_files/`
2. Add expected output to `golden_data/entity_extraction_golden.json`:

```json
{
  "input_file": "your_file.txt",
  "expected_entities": [
    {"type": "person", "value": "张三"},
    {"type": "date", "value": "2024-01-01"}
  ],
  "min_recall": 0.8,
  "description": "Test case description"
}
```

## CI Integration

These tests should run in CI pipeline to catch regressions:

```yaml
# .github/workflows/test.yml example
- name: Run golden tests
  run: pytest backend/tests/test_golden_evaluation.py --tb=short
```

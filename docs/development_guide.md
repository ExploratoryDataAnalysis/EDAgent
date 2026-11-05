# EDAgent Development & Testing Guide

This guide describes development workflows, coding standards, testing instructions, and validation procedures for contributors to EDAgent.

---

## 1. Development Principles

1. **Deterministic Computation First**:
   - Never write code where LLMs predict or hallucinate numbers. Every statistic, mean, quantile, or percentage must be calculated by the Python/DuckDB engine.
2. **Strict Schema Validation**:
   - All client inputs, API payloads, and AI tool plans must be validated using Pydantic v2 schemas and matched against the dataset column inventory before execution.
3. **No Raw Data in LLM Prompts**:
   - Only pass column names, inferred semantic roles, descriptive statistics, and anonymized/sanitized small previews (max 5 rows) to external LLM providers.
4. **Transparent & Reproducible Results**:
   - Every `AnalysisResult` must preserve the exact code snippet, row counts (examined vs. used), missing value treatment, and assumption warnings.

---

## 2. Running Automated Tests

The testing suite uses `pytest` and benchmarks known statistical properties on test fixtures located in `data/samples/`.

### 2.1 Run All Backend Tests
```bash
python -m pytest backend/tests -v
```

### 2.2 Run Specific Test Suites
```bash
# Run baseline profiler tests
python -m pytest backend/tests/test_baseline.py -k test_profiler_engine_on_known_dataset

# Run security and SSRF tests
python -m pytest backend/tests/test_baseline.py -k test_ssrf_security_guardrail
```

### 2.3 Test Coverage Report
```bash
python -m pytest backend/tests --cov=backend/app --cov-report=term-missing
```

---

## 3. Code Quality & Linting

We maintain strict formatting and type checking:

### 3.1 Python Backend
```bash
# Lint with Ruff
ruff check backend/

# Format with Ruff
ruff format backend/

# Type check with Mypy
mypy backend/app
```

### 3.2 TypeScript Frontend
```bash
cd frontend
# Check TypeScript types
npm run build

# Lint JavaScript & TypeScript
npm run lint
```

---

## 4. Extending the Analysis Tool Catalogue

To add a new analytical operation to EDAgent:

1. **Register the Operation in Schema**:
   - Update `AnalysisOperationEnum` in `backend/app/schemas/analysis.py`.
2. **Define Metadata & Parameters**:
   - Register the tool in `ToolCatalogue.OPERATIONS_METADATA` within `backend/app/services/analysis/catalogue.py`. Specify required parameters, optional parameters, and compatible semantic roles (`measure`, `category`, `datetime`).
3. **Implement the Compute Routine**:
   - Implement the calculation in `backend/app/services/analysis/` ensuring:
     - Missing values are explicitly counted and reported.
     - Sample size is recorded.
     - Outlier or assumption warnings are emitted.
     - Reproducible code string is returned.
4. **Add Plotly Visualization Spec**:
   - Add chart generator to `backend/app/services/visualization/`.
5. **Add Benchmark Test**:
   - Write a unit test in `backend/tests/` asserting the operation's output against a dataset with known answers.

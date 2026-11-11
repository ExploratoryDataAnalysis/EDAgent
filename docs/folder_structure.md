# Legacy EDA prototype folder structure

This layout describes the original root prototype. See the [environment setup guide](environment_setup.md) for the active nested application.

This document defines the physical directory layout, module boundaries, and separation of concerns across the frontend and backend codebases.

```
EDA-Dashboard/
├── .env.example                     # Environment configuration template
├── .gitignore                       # Git ignore policies (Python, Node, data, exports)
├── docker-compose.yml               # Multi-container orchestration (Postgres, Redis, Web, Worker)
├── README.md                        # Project landing page and architectural index
│
├── docs/                            # Architectural and development documentation
│   ├── architecture.md              # System architecture, request lifecycle, compute tiers
│   ├── folder_structure.md          # Directory tree and module boundary specification
│   ├── database_schema.md           # ER diagrams, table definitions, and migrations
│   ├── api_specification.md         # REST API contracts, routes, and JSON schemas
│   ├── environment_setup.md         # Environment setup instructions (Python, Node, Docker)
│   ├── development_guide.md         # Developer instructions, testing commands, code styles
│   ├── implementation_plan.md       # Roadmap for subsequent implementation phases (0 - 6)
│   └── risks_and_decisions.md       # Risk mitigation log and architectural decision records
│
├── data/                            # Storage mounts and test fixtures
│   ├── samples/                     # Test datasets with known statistical answers
│   │   └── baseline_benchmark.csv   # Reference dataset (exact duplicates, outliers, injections)
│   ├── uploads/                     # Local storage mount for uploaded user datasets
│   └── exports/                     # Local storage mount for generated PDF reports and bundles
│
├── backend/                         # FastAPI & Python Analytics Core
│   ├── pyproject.toml               # Python project configuration & pytest settings
│   ├── requirements.txt             # Production dependencies
│   ├── requirements-dev.txt         # Development & testing dependencies
│   │
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                  # FastAPI application entrypoint & middleware setup
│   │   │
│   │   ├── api/                     # REST API Routing
│   │   │   ├── __init__.py
│   │   │   └── v1/
│   │   │       ├── __init__.py
│   │   │       ├── router.py        # v1 Router aggregator
│   │   │       └── endpoints/       # Domain route handlers
│   │   │           ├── health.py    # Health check & diagnostics
│   │   │           ├── auth.py      # Registration & authentication
│   │   │           ├── datasets.py  # File upload & URL ingestion
│   │   │           ├── profiling.py # Automatic EDA profiler triggers & fetching
│   │   │           ├── analysis.py  # Statistical computation execution
│   │   │           ├── chat.py      # AI conversational interface
│   │   │           ├── reports.py   # PDF & HTML report generation
│   │   │           └── jobs.py      # Background task polling & cancellation
│   │   │
│   │   ├── core/                    # Core Infrastructure
│   │   │   ├── __init__.py
│   │   │   ├── config.py            # Typed settings via Pydantic
│   │   │   ├── database.py          # SQLAlchemy async/sync database session manager
│   │   │   ├── security.py          # SSRF validator, CSV sanitizer, prompt filter
│   │   │   └── storage.py           # Pluggable storage abstraction (LocalStorage / S3)
│   │   │
│   │   ├── models/                  # SQLAlchemy ORM Entities
│   │   │   ├── __init__.py          # Exports all models for Alembic migrations
│   │   │   ├── base.py              # Base model with UUID primary keys & timestamps
│   │   │   ├── user.py              # User entity
│   │   │   ├── dataset.py           # Dataset & DatasetMetadata entities
│   │   │   ├── session.py           # AnalysisSession entity
│   │   │   ├── analysis.py          # AnalysisRequest & AnalysisResult entities
│   │   │   ├── report.py            # GeneratedReport entity
│   │   │   └── job.py               # BackgroundJob entity
│   │   │
│   │   ├── schemas/                 # Pydantic Schemas (API Contracts)
│   │   │   ├── __init__.py
│   │   │   ├── common.py            # Generic APIResponse envelope & pagination
│   │   │   ├── user.py              # User & JWT schemas
│   │   │   ├── dataset.py           # Upload, URL import & preview schemas
│   │   │   ├── profiler.py          # Baseline profiler & column summary schemas
│   │   │   ├── analysis.py          # Tool catalogue & structured plan schemas
│   │   │   ├── chat.py              # Conversational analysis & clarification schemas
│   │   │   ├── report.py            # Report generation configuration schemas
│   │   │   └── job.py               # Task status & progress schemas
│   │   │
│   │   ├── services/                # Business Logic & Computational Engines
│   │   │   ├── __init__.py
│   │   │   ├── ingestion/           # File validation, delimiter sniffing, sheet extraction
│   │   │   ├── profiler/            # Deterministic statistics, duplicate & missingness checks
│   │   │   ├── analysis/            # Controlled analysis tool catalogue & execution
│   │   │   ├── ai/                  # AI orchestrator, prompts, plan extractor
│   │   │   ├── visualization/       # Plotly chart specification builder
│   │   │   ├── export/              # PDF report composition & CSV/XLSX bundles
│   │   │   └── jobs/                # Celery worker configuration & task definitions
│   │   │
│   │   └── repositories/            # Data Access Layer
│   │       ├── __init__.py
│   │       └── base.py              # Generic asynchronous CRUD repository
│   │
│   └── tests/                       # Automated Test Suite
│       ├── __init__.py
│       ├── conftest.py              # Pytest fixtures and test paths
│       └── test_baseline.py         # Phase 0 baseline correctness tests
│
└── frontend/                        # React + TypeScript Web Client
    ├── package.json                 # Node dependencies (React 18, Vite, Plotly, Tailwind)
    ├── tsconfig.json                # Strict TypeScript configuration
    ├── vite.config.ts               # Vite configuration with API proxy
    │
    └── src/
        ├── types/                   # TypeScript interfaces matching backend Pydantic schemas
        │   └── index.ts
        ├── services/                # HTTP API Client & Endpoint Wrappers
        │   ├── apiClient.ts         # Axios instance with interceptors
        │   ├── datasetService.ts    # Upload, preview, and profiling service
        │   ├── analysisService.ts   # Plan execution and result service
        │   ├── chatService.ts       # Conversational analysis service
        │   └── reportService.ts     # PDF report generation service
        ├── pages/                   # Top-level screen views
        │   ├── HomePage.tsx         # Welcome screen, product vision & format guidelines
        │   ├── UploadPage.tsx       # Drag-and-drop file ingestion & preview
        │   ├── OverviewPage.tsx     # Profiler dashboard (KPIs, columns, quality checks)
        │   ├── WorkspacePage.tsx    # 3-part interactive analysis workspace
        │   ├── ReportBuilderPage.tsx# Section picker & PDF export generator
        │   └── HistoryPage.tsx      # Past analysis sessions and datasets
        ├── components/              # Modular UI Components
        │   ├── ui/                  # Primitives (buttons, inputs, modals, cards)
        │   ├── layout/              # Navbar, sidebar, containers
        │   ├── upload/              # File dropzone, progress bar, sheet selector
        │   ├── profiler/            # Metric cards, missingness bars, quality badges
        │   ├── workspace/           # Column drawer, code inspector, data table
        │   ├── chat/                # Message history, clarification bubbles
        │   ├── charts/              # Plotly chart canvas wrapper
        │   └── reports/             # Report previewer & section checklist
        ├── hooks/                   # Custom React state hooks
        └── utils/                   # Formatting, numeric helpers & validation
```

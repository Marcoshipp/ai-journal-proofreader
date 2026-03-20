# AI Journal Proofreader (Backend)

This is the FastAPI backend for the AI Journal Proofreader application. It uses `uv` for lightning-fast Python dependency management.

## Installation

We use [uv](https://github.com/astral-sh/uv) to manage Python dependencies.

**Step 1. Install uv** (if you haven't already):
```bash
# macOS / Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

**Step 2. Install project dependencies**:
Navigate into the `backend/` directory and run:
```bash
uv sync
```
*This command will automatically create a virtual environment (`.venv/`) and intelligently install all packages locked inside the `uv.lock` file so everyone has the exact same versions.*

## Running the Server

To start the FastAPI development server:

```bash
uv run python main.py
```

The API will be available at `http://localhost:8000/api`.

*(Alternatively, you can manually activate the environment with `source .venv/bin/activate` or `.venv\\Scripts\\activate` on Windows, and simply run `python main.py`.)*

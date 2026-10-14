# Plastic Leakage Prevention — Starter Project

This starter provides a small FastAPI backend using synthetic example data. It is meant to prove the first workflow, not to make real-world pollution predictions.

## Requirements
- Windows 10/11
- Python 3.10 or newer
- VS Code (recommended)

## Run on Windows PowerShell

1. Extract this ZIP.
2. Open the extracted `plastic_leakage_starter` folder in VS Code.
3. Open Terminal → New Terminal.
4. Run:

```powershell
cd backend
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
uvicorn main:app --reload
```

If PowerShell blocks activation, run this for the current terminal only, then activate again:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

If `py` is not recognized, install Python from https://www.python.org/downloads/ and select “Add Python to PATH” during installation.

## Test the API
- Home: http://127.0.0.1:8000/
- Interactive API docs: http://127.0.0.1:8000/docs
- Network data: http://127.0.0.1:8000/api/network

In `/docs`, open `POST /api/hotspots`, click **Try it out**, and use:

```json
{
  "rainfall": "heavy",
  "top_k": 5
}
```

Try `light`, `moderate`, and `heavy` to compare rankings.

## Important
- All included locations and values are fictional sample data.
- The score is a transparent starter heuristic, not a validated scientific model.
- Before real use, replace the sample network with verified drainage data, define flow assumptions, incorporate cleanup history, validate predictions against field observations, and restrict CORS/database secrets before deployment.
- Docker is not used.

# Core Opus Backend

Python/FastAPI backend for the Core Opus platform.

## Virtualenv setup

### Windows

Windows users should prefer a short external venv path to avoid path-length failures with packages like `litellm`.

Recommended:

```powershell
cd backend
py -m venv C:\venvs\coreopus-backend
$env:BACKEND_VENV_PATH = "C:\venvs\coreopus-backend"
& "$env:BACKEND_VENV_PATH\Scripts\python.exe" -m pip install --upgrade pip setuptools wheel
& "$env:BACKEND_VENV_PATH\Scripts\python.exe" -m pip install -r requirements.txt
```

Fallback:

```powershell
cd backend
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip setuptools wheel
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### macOS / Linux

```bash
cd backend
python3 -m venv .venv
./.venv/bin/python -m pip install --upgrade pip setuptools wheel
./.venv/bin/python -m pip install -r requirements.txt
```

`BACKEND_VENV_PATH` works the same way as on Windows if you'd rather keep the venv outside the repo:

```bash
python3 -m venv ~/venvs/coreopus-backend
export BACKEND_VENV_PATH=~/venvs/coreopus-backend
"$BACKEND_VENV_PATH/bin/python" -m pip install --upgrade pip setuptools wheel
"$BACKEND_VENV_PATH/bin/python" -m pip install -r requirements.txt
```

## Running locally

### Windows

Use the helper script so the repo resolves `BACKEND_VENV_PATH` first and `backend\.venv` second:

```powershell
cd backend
.\scripts\Start-Backend.ps1
```

If you only want to resolve the Python interpreter:

```powershell
cd backend
.\scripts\Get-BackendPython.ps1
```

Manual run:

```powershell
cd backend
$py = .\scripts\Get-BackendPython.ps1
& $py -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

### macOS / Linux

Same resolution order (`BACKEND_VENV_PATH` first, then `backend/.venv`), via the POSIX equivalents:

```bash
cd backend
./scripts/start-backend.sh
```

If you only want to resolve the Python interpreter:

```bash
cd backend
./scripts/get-backend-python.sh
```

Manual run:

```bash
cd backend
py=$(./scripts/get-backend-python.sh)
"$py" -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

## Environment note

`BACKEND_VENV_PATH` is optional but recommended on Windows, and works the same way on macOS/Linux if you want the venv outside the repo. Example:

```powershell
$env:BACKEND_VENV_PATH = "C:\venvs\coreopus-backend"
```

```bash
export BACKEND_VENV_PATH=~/venvs/coreopus-backend
```

That keeps the virtualenv outside the repo and avoids long nested install paths.

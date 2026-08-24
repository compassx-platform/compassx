# Quickstart Guide

This guide walks you through setting up and running the CompassX platform locally using the **`local-dev`** profile.

---

## Clone the Repository

Clone the project repository to your local workstation:

=== "HTTPS"
    ```bash
    git clone https://github.com/compassx-platform/compassx.git
    cd compassx
    ```

=== "SSH"
    ```bash
    git clone git@github.com:compassx-platform/compassx.git
    cd compassx
    ```

---

## Configure Environment Variables

Copy the example environment configuration to `.env`:

=== "macOS / Linux"
    ```bash
    cp .env.example .env
    ```

=== "Windows (PowerShell)"
    ```powershell
    Copy-Item .env.example .env
    ```

> [!NOTE]
> The default values in `.env.example` are pre-configured to work out of the box with the `local-dev` Docker Compose profile.

---

## Start Infrastructure Services

Start the core backing services (PostgreSQL, Redis, MinIO, Airflow, Enterprise Gateway) via Docker Compose:

```bash
docker compose --profile local-dev up -d
```

Verify that all containers are healthy:
```bash
docker compose --profile local-dev ps
```

---

## Run the Backend (FastAPI)

Navigate to the `backend/` directory, set up your Python virtual environment, install dependencies, and start the server:

=== "macOS / Linux"
    ```bash
    cd backend
    python3 -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt
    python -m uvicorn app.main:app --reload --port 8000
    ```

=== "Windows (PowerShell)"
    ```powershell
    cd backend
    python -m venv .venv
    .venv\Scripts\Activate.ps1
    pip install -r requirements.txt
    python -m uvicorn app.main:app --reload --port 8000
    ```

The backend API and interactive docs will now be available at:
- API Base: `http://localhost:8000`
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

---

## Run the Frontend (React + Vite)

In a separate terminal, start the frontend development server:

```bash
cd frontend
npm install
npm run dev
```

Open your browser and navigate to `http://localhost:5173`.

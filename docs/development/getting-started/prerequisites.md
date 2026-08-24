# System Prerequisites

Before developing or running CompassX, ensure your workstation meets the following hardware and software requirements.

---

## Software Dependencies

| Requirement | Minimum Version | Recommended Version | Purpose |
| :--- | :--- | :--- | :--- |
| **Docker Desktop / Engine** | `24.0+` | `26.0+` | Runs backing databases, message queues, and compute containers. |
| **Docker Compose** | `v2.20+` | `v2.27+` | Multi-container orchestration for `local-dev` profiles. |
| **Python** | `3.11` | `3.11.9+` | Backend FastAPI service, CLI tools, and data processing. |
| **Node.js & npm** | Node `18.0+` / npm `9.0+` | Node `20 LTS` | Frontend React + Vite application build and runtime. |
| **Git** | `2.30+` | Latest | Version control and submodules. |

---

## Operating System Notes

### macOS
- Ensure Docker Desktop is allocated at least **4 CPU cores** and **8 GB RAM** in Docker Settings > Resources.
- If using Docker Desktop on macOS, enable:
  > **Settings > Advanced > Allow the default Docker socket to be used**.

### Windows
- Use **WSL 2 (Windows Subsystem for Linux)** backend for Docker Desktop for optimal filesystem and networking performance.
- When running PowerShell scripts, ensure Execution Policy allows running scripts in your current session:
  ```powershell
  Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process
  ```

### Linux (Ubuntu / Debian / RHEL)
- Ensure your user is added to the `docker` group to run Docker commands without `sudo`:
  ```bash
  sudo usermod -aG docker $USER
  ```

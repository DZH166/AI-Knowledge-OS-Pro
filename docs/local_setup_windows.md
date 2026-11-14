# Local Windows Setup Notes

This file is for this machine only. README stays portable for GitHub and new computers.

Known local tools:
- Python virtual environment: `<VENV>`
- Node.js: `<NODE_HOME>`
- Qdrant binary: `<QDRANT_HOME>\qdrant.exe`
- Pytest temp root: workspace relative `.pytest_tmp`

Useful commands:
```powershell
Start-Process -FilePath '<QDRANT_HOME>\qdrant.exe' -WorkingDirectory '<QDRANT_HOME>' -WindowStyle Hidden
& '<VENV>\Scripts\python.exe' -m alembic upgrade head
& '<VENV>\Scripts\python.exe' -m uvicorn app.main:app --app-dir backend --reload --host 127.0.0.1 --port 8000
$env:PATH='<NODE_HOME>;'+$env:PATH
& '<NODE_HOME>\corepack.cmd' npm run dev --prefix frontend
```

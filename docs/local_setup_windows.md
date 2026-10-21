# Local Windows Setup Notes

This file is for this machine only. README stays portable for GitHub and new computers.

Known local tools:
- Python virtual environment: `E:\AIKnowledgeOSProVenv`
- Node.js: `E:\NodeJS`
- Qdrant binary: `E:\Qdrant\qdrant.exe`
- Pytest temp root: workspace relative `.pytest_tmp`

Useful commands:
```powershell
Start-Process -FilePath 'E:\Qdrant\qdrant.exe' -WorkingDirectory 'E:\Qdrant' -WindowStyle Hidden
& 'E:\AIKnowledgeOSProVenv\Scripts\python.exe' -m alembic upgrade head
& 'E:\AIKnowledgeOSProVenv\Scripts\python.exe' -m uvicorn app.main:app --app-dir backend --reload --host 127.0.0.1 --port 8000
$env:PATH='E:\NodeJS;'+$env:PATH
& 'E:\NodeJS\corepack.cmd' npm run dev --prefix frontend
```

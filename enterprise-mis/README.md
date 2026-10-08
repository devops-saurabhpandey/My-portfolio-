# Enterprise MIS & Analytics Platform

Portfolio-grade business reporting platform using FastAPI, MySQL, JavaScript, Docker and GitHub Actions.

## Features
- KPI dashboard API
- CSV sales-data ingestion
- Admin / Manager / Viewer roles
- Audit-log model
- MySQL schema
- Docker deployment
- Automated tests and CI

## Run
```bash
python -m venv .venv
pip install -r requirements.txt
uvicorn app.main:app --reload
```
Open `http://127.0.0.1:8000/docs` for Swagger.

This is a portfolio implementation, not a claimed production client deployment.

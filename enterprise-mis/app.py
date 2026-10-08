from csv import DictReader
from io import StringIO

from fastapi import FastAPI, File, HTTPException, UploadFile

app = FastAPI(title="Enterprise MIS & Analytics API", version="1.1.0")

ROLES = {"ADMIN", "MANAGER", "VIEWER"}


@app.get("/health")
def health():
    return {"status": "ok", "service": "enterprise-mis-api"}


@app.get("/api/v1/kpis")
def kpis():
    revenue = 125000.0
    orders = 500
    return {
        "revenue": revenue,
        "orders": orders,
        "customers": 320,
        "average_order_value": revenue / orders,
        "data_source": "sample"
    }


@app.post("/api/v1/sales/import")
async def import_sales(file: UploadFile = File(...)):
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files are supported")

    raw = await file.read()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="CSV must be UTF-8 encoded")

    rows = list(DictReader(StringIO(text)))
    required = {"sale_date", "customer", "amount"}
    if not rows or not required.issubset(rows[0].keys()):
        raise HTTPException(
            status_code=400,
            detail="CSV must contain sale_date, customer and amount columns"
        )

    valid_rows = []
    for row in rows:
        try:
            amount = float(row["amount"])
            if not row["sale_date"] or not row["customer"] or amount < 0:
                raise ValueError
            valid_rows.append({
                "sale_date": row["sale_date"],
                "customer": row["customer"],
                "amount": amount
            })
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail="Invalid sales row")

    return {
        "status": "validated",
        "rows_received": len(valid_rows),
        "rows": valid_rows[:5],
        "message": "CSV validated successfully; database persistence is the next layer."
    }


@app.get("/api/v1/roles")
def roles():
    return {"roles": sorted(ROLES), "permissions": {
        "ADMIN": ["read", "write", "import", "audit"],
        "MANAGER": ["read", "import"],
        "VIEWER": ["read"]
    }}

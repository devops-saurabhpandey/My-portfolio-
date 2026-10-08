import os
from csv import DictReader
from datetime import datetime, timedelta, timezone
from io import StringIO
from typing import Annotated

import pymysql
from fastapi import Depends, FastAPI, File, HTTPException, UploadFile, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt

app = FastAPI(title="Enterprise MIS & Analytics API", version="1.3.0")

SECRET_KEY = os.getenv("MIS_SECRET_KEY", "development-only-change-me")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

DATABASE_CONFIG = {
    "host": os.getenv("DB_HOST", "db"),
    "port": int(os.getenv("DB_PORT", "3306")),
    "user": os.getenv("DB_USER", "mis_user"),
    "password": os.getenv("DB_PASSWORD", "mis_password"),
    "database": os.getenv("DB_NAME", "enterprise_mis"),
    "cursorclass": pymysql.cursors.DictCursor,
    "autocommit": True,
}

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")
ROLES = {"ADMIN", "MANAGER", "VIEWER"}

DEMO_USERS = {
    "admin": {"password": "admin-demo", "role": "ADMIN"},
    "manager": {"password": "manager-demo", "role": "MANAGER"},
    "viewer": {"password": "viewer-demo", "role": "VIEWER"},
}


def db_connection():
    try:
        return pymysql.connect(**DATABASE_CONFIG)
    except pymysql.MySQLError as exc:
        raise HTTPException(status_code=503, detail="Database unavailable") from exc


def create_access_token(username: str, role: str):
    expires = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    return jwt.encode({"sub": username, "role": role, "exp": expires}, SECRET_KEY, algorithm=ALGORITHM)


def current_user(token: Annotated[str, Depends(oauth2_scheme)]):
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        role = payload.get("role")
        if not username or role not in ROLES:
            raise credentials_error
        return {"username": username, "role": role}
    except JWTError:
        raise credentials_error


def require_roles(*allowed_roles: str):
    def checker(user: Annotated[dict, Depends(current_user)]):
        if user["role"] not in allowed_roles:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return user
    return checker


def write_audit(username: str, action: str, resource: str, details: str):
    connection = db_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO audit_logs (username, action, resource, details) VALUES (%s, %s, %s, %s)",
                (username, action, resource, details),
            )
    finally:
        connection.close()


@app.get("/health")
def health():
    return {"status": "ok", "service": "enterprise-mis-api"}


@app.post("/api/v1/auth/login")
def login(form: Annotated[OAuth2PasswordRequestForm, Depends()]):
    user = DEMO_USERS.get(form.username)
    if not user or user["password"] != form.password:
        raise HTTPException(status_code=401, detail="Incorrect username or password")
    token = create_access_token(form.username, user["role"])
    try:
        write_audit(form.username, "LOGIN", "auth", "Successful demo login")
    except HTTPException:
        pass
    return {
        "access_token": token,
        "token_type": "bearer",
        "role": user["role"],
        "demo_only": True,
    }


@app.get("/api/v1/me")
def me(user: Annotated[dict, Depends(current_user)]):
    return user


@app.get("/api/v1/kpis")
def kpis(user: Annotated[dict, Depends(require_roles("ADMIN", "MANAGER", "VIEWER"))]):
    connection = db_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT COALESCE(SUM(amount), 0) AS revenue, COUNT(*) AS orders, "
                "COUNT(DISTINCT customer) AS customers FROM sales"
            )
            row = cursor.fetchone()
    finally:
        connection.close()

    orders = int(row["orders"])
    revenue = float(row["revenue"])
    return {
        "revenue": revenue,
        "orders": orders,
        "customers": int(row["customers"]),
        "average_order_value": revenue / orders if orders else 0,
        "data_source": "mysql",
        "visible_to": user["role"],
    }


@app.post("/api/v1/sales/import")
async def import_sales(
    file: UploadFile = File(...),
    user: Annotated[dict, Depends(require_roles("ADMIN", "MANAGER"))] = None,
):
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
        raise HTTPException(status_code=400, detail="CSV must contain sale_date, customer and amount columns")

    connection = db_connection()
    inserted = 0
    try:
        with connection.cursor() as cursor:
            for row in rows:
                try:
                    sale_date = datetime.strptime(row["sale_date"], "%Y-%m-%d").date()
                    amount = float(row["amount"])
                    customer = row["customer"].strip()
                    if not customer or amount < 0:
                        raise ValueError
                except (TypeError, ValueError):
                    connection.rollback()
                    raise HTTPException(status_code=400, detail="Invalid sales row")

                cursor.execute(
                    "INSERT INTO sales (sale_date, customer, amount, source) VALUES (%s, %s, %s, %s)",
                    (sale_date, customer, amount, "csv"),
                )
                inserted += 1
        write_audit(user["username"], "IMPORT", "sales", f"Imported {inserted} rows")
    finally:
        connection.close()

    return {"status": "imported", "rows_imported": inserted, "imported_by": user["username"]}


@app.get("/api/v1/audit-logs")
def audit_logs(user: Annotated[dict, Depends(require_roles("ADMIN"))]):
    connection = db_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT id, username, action, resource, details, created_at "
                "FROM audit_logs ORDER BY id DESC LIMIT 100"
            )
            rows = cursor.fetchall()
    finally:
        connection.close()
    return {"count": len(rows), "items": rows}


@app.get("/api/v1/roles")
def roles():
    return {
        "roles": sorted(ROLES),
        "permissions": {
            "ADMIN": ["read", "write", "import", "audit"],
            "MANAGER": ["read", "import"],
            "VIEWER": ["read"],
        },
    }

import os
from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt

app = FastAPI(title="Enterprise MIS & Analytics API", version="1.2.0")

SECRET_KEY = os.getenv("MIS_SECRET_KEY", "development-only-change-me")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")
ROLES = {"ADMIN", "MANAGER", "VIEWER"}

# Portfolio/demo identities. Production systems should store hashed passwords in MySQL.
DEMO_USERS = {
    "admin": {"password": "admin-demo", "role": "ADMIN"},
    "manager": {"password": "manager-demo", "role": "MANAGER"},
    "viewer": {"password": "viewer-demo", "role": "VIEWER"},
}


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


@app.get("/health")
def health():
    return {"status": "ok", "service": "enterprise-mis-api"}


@app.post("/api/v1/auth/login")
def login(form: Annotated[OAuth2PasswordRequestForm, Depends()]):
    user = DEMO_USERS.get(form.username)
    if not user or user["password"] != form.password:
        raise HTTPException(status_code=401, detail="Incorrect username or password")
    return {
        "access_token": create_access_token(form.username, user["role"]),
        "token_type": "bearer",
        "role": user["role"],
        "demo_only": True,
    }


@app.get("/api/v1/me")
def me(user: Annotated[dict, Depends(current_user)]):
    return user


@app.get("/api/v1/kpis")
def kpis(user: Annotated[dict, Depends(require_roles("ADMIN", "MANAGER", "VIEWER"))]):
    revenue = 125000.0
    orders = 500
    return {
        "revenue": revenue,
        "orders": orders,
        "customers": 320,
        "average_order_value": revenue / orders,
        "data_source": "sample",
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

    from csv import DictReader
    from io import StringIO

    rows = list(DictReader(StringIO(text)))
    required = {"sale_date", "customer", "amount"}
    if not rows or not required.issubset(rows[0].keys()):
        raise HTTPException(
            status_code=400,
            detail="CSV must contain sale_date, customer and amount columns",
        )

    valid_rows = []
    for row in rows:
        try:
            amount = float(row["amount"])
            datetime.strptime(row["sale_date"], "%Y-%m-%d")
            if not row["customer"] or amount < 0:
                raise ValueError
            valid_rows.append({
                "sale_date": row["sale_date"],
                "customer": row["customer"],
                "amount": amount,
            })
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail="Invalid sales row")

    return {
        "status": "validated",
        "rows_received": len(valid_rows),
        "rows": valid_rows[:5],
        "imported_by": user["username"],
        "message": "CSV validated successfully; database persistence is the next layer.",
    }


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

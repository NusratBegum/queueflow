from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.config import ACCESS_TOKEN_EXPIRE_MINUTES, JWT_ALGORITHM, JWT_SECRET
from app.db import get_db
from app.models import Staff

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token")


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode(), password_hash.encode())


def create_access_token(staff_id: int) -> str:
    expires = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    return jwt.encode({"sub": str(staff_id), "exp": expires}, JWT_SECRET, algorithm=JWT_ALGORITHM)


def current_staff(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> Staff:
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        staff_id = int(jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        raise unauthorized
    staff = db.get(Staff, staff_id)
    if staff is None:
        raise unauthorized
    return staff

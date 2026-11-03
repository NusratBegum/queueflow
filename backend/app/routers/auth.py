from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Staff
from app.schemas import SignupIn, TokenOut
from app.security import create_access_token, hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/signup", response_model=TokenOut, status_code=status.HTTP_201_CREATED)
def signup(body: SignupIn, db: Session = Depends(get_db)) -> TokenOut:
    email = body.email.lower()
    if db.scalar(select(Staff).where(Staff.email == email)):
        raise HTTPException(status.HTTP_409_CONFLICT, "An account with this email already exists")
    staff = Staff(email=email, password_hash=hash_password(body.password))
    db.add(staff)
    db.commit()
    return TokenOut(access_token=create_access_token(staff.id))


@router.post("/token", response_model=TokenOut)
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)) -> TokenOut:
    staff = db.scalar(select(Staff).where(Staff.email == form.username.lower()))
    if staff is None or not verify_password(form.password, staff.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Wrong email or password")
    return TokenOut(access_token=create_access_token(staff.id))

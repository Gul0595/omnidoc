from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr
from api.database import get_db, User
from api.auth_utils import verify_password, hash_password, create_access_token
from api.audit import log_activity

router = APIRouter()


class RegisterReq(BaseModel):
    email:        EmailStr
    password:     str
    full_name:    str
    organisation: str = ""


class TokenResp(BaseModel):
    access_token: str
    token_type:   str = "bearer"


@router.post("/register", response_model=TokenResp)
def register(req: RegisterReq, request: Request,
             db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == req.email).first():
        raise HTTPException(400, "Email already registered")
    user = User(
        email=req.email,
        hashed_password=hash_password(req.password),
        full_name=req.full_name,
        organisation=req.organisation,
    )
    db.add(user)
    db.flush()
    log_activity(db, user.id, "register", "user", user.id,
                 ip_address=request.client.host)
    db.commit()
    return TokenResp(access_token=create_access_token({"sub": user.email}))


@router.post("/token", response_model=TokenResp)
def login(form: OAuth2PasswordRequestForm = Depends(),
          request: Request = None,
          db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == form.username).first()
    if not user or not verify_password(form.password, user.hashed_password):
        raise HTTPException(401, "Incorrect email or password")
    log_activity(db, user.id, "login",
                 ip_address=getattr(request.client, "host", None) if request else None)
    db.commit()
    return TokenResp(access_token=create_access_token({"sub": user.email}))


@router.get("/me")
def get_me(db: Session = Depends(get_db),
           current_user=Depends(__import__("api.auth_utils",
                                           fromlist=["get_current_user"]).get_current_user)):
    return {
        "id": current_user.id, "email": current_user.email,
        "full_name": current_user.full_name,
        "organisation": current_user.organisation,
    }

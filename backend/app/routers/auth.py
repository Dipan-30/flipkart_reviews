"""Authentication router."""
import logging
from fastapi import APIRouter, HTTPException, status, Depends
from bson import ObjectId
from datetime import datetime, timezone

from app.auth.jwt_handler import create_access_token
from app.auth.password import hash_password, verify_password
from app.auth.dependencies import get_current_user
from app.database.connection import get_db
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse, UserResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(body: RegisterRequest):
    db = get_db()

    # Check for existing email
    existing = await db.users.find_one({"email": body.email.lower()})
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered.")

    # Create user
    user_doc = {
        "name": body.name.strip(),
        "email": body.email.lower().strip(),
        "hashed_password": hash_password(body.password),
        "created_at": datetime.now(timezone.utc),
    }
    result = await db.users.insert_one(user_doc)
    user_id = str(result.inserted_id)
    logger.info(f"New user registered: {body.email}")

    token = create_access_token(user_id, body.email)
    return TokenResponse(
        access_token=token,
        user_id=user_id,
        name=body.name,
        email=body.email.lower(),
    )


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest):
    db = get_db()
    user = await db.users.find_one({"email": body.email.lower()})

    if not user or not verify_password(body.password, user["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )

    user_id = str(user["_id"])
    token = create_access_token(user_id, user["email"])
    logger.info(f"User logged in: {body.email}")
    return TokenResponse(
        access_token=token,
        user_id=user_id,
        name=user["name"],
        email=user["email"],
    )


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: dict = Depends(get_current_user)):
    return UserResponse(
        user_id=current_user["user_id"],
        name=current_user["name"],
        email=current_user["email"],
    )


@router.post("/logout")
async def logout():
    # JWT is stateless; client should discard the token
    return {"message": "Logged out successfully."}

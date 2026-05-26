from fastapi import APIRouter, HTTPException, status
from app.models.schemas import UserRegister, UserLogin, Token
from app.utils.auth_helper import hash_password, verify_password, create_access_token
from app.vectorstore import database as db

router = APIRouter(prefix="/api/auth", tags=["authentication"])

@router.post("/register", status_code=status.HTTP_201_CREATED)
def register_user(user_data: UserRegister):
    """Register a new user account with secure password hashing."""
    # Check if user exists
    existing = db.get_user_by_username(user_data.username)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already taken"
        )
        
    hashed = hash_password(user_data.password)
    success = db.create_user(user_data.username, hashed)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not register user. Please try again."
        )
        
    return {"message": "User registered successfully", "username": user_data.username}

@router.post("/login", response_model=Token)
def login_user(login_data: UserLogin):
    """Authenticate credentials and return a signed JWT token."""
    user = db.get_user_by_username(login_data.username)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password"
        )
        
    if not verify_password(login_data.password, user["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password"
        )
        
    # Generate access token containing the username
    token = create_access_token(data={"sub": user["username"]})
    
    return Token(
        access_token=token,
        token_type="bearer",
        username=user["username"]
    )

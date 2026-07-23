from fastapi import APIRouter, HTTPException, Depends, Header
from app.services.sessions import get_session, create_session, delete_session, delete_all_sessions
from app.services.rate_limit import check_rate_limit
from pydantic import BaseModel
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"])


router = APIRouter(prefix="/auth", tags=["auth"])

class User(BaseModel):
    email: str
    password: str


@router.post("/register", tags=["auth"], dependencies=[Depends(check_rate_limit)])
async def register_user(register_request: User):
    """
    Endpoint to register a new user.
    Validates the request, hashes the password, and stores the user in the database.
    """
    # Hash the password
    hashed_password = pwd_context.hash(register_request.password)

    # TODO: Insert the new user into PostgreSQL with the hashed password and return the created user ID.
    # TODO: Use a raw-SQL insert here once the DB connection helper is in place.

    # Create session for the new user
    session_id = await create_session(user_id=1)

    # TODO: Replace this placeholder user ID with the actual ID returned from the database insert.

    return {"status": "success", "session_id": session_id, "message": "User registered successfully."}



@router.post("/login", tags=["auth"], dependencies=[Depends(check_rate_limit)])
async def login_user(login_request: User):
    """
    Endpoint to log in a user.
    Validates the request, checks the password, and creates a session.
    """
    
    # TODO: Fetch the user from PostgreSQL by email using raw SQL.
    # TODO: Raise 401 if the user is not found.
    # TODO: Replace the placeholder password hash with the stored hash from the database.
    hashed_password = "$2b$12$placeholder"  # stub until Postgres exists


    # Verify the password
    if not pwd_context.verify(login_request.password, hashed_password):
        raise HTTPException(status_code=401, detail="Invalid email or password.")
    
    # Create session for the user
    # TODO: Use the real database user ID instead of the placeholder value here.
    session_id = await create_session(user_id=1)

    return {"status": "success", "session_id": session_id, "message": "User logged in successfully."}



@router.post("/logout", tags=["auth"], dependencies=[Depends(check_rate_limit)])
async def logout_user(session_id: str = Header(alias="X-Session-Id"), user_id: int = Depends(get_session)):
    """
    Endpoint to log out a user.
    Deletes the session associated with the provided session ID.
    """

    await delete_session(session_id, user_id)
    return {"status": "success", "message": "User logged out successfully."}

@router.post("/logout-all", dependencies=[Depends(check_rate_limit)])
async def logout_all(user_id: int = Depends(get_session)):
    await delete_all_sessions(user_id)
    return {"status": "success", "message": "All sessions terminated."}





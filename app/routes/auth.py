from fastapi import APIRouter, HTTPException, Depends, Header
from app.services.sessions import get_session, create_session, delete_session, delete_all_sessions
from app.services.rate_limit import check_rate_limit
from pydantic import BaseModel
from passlib.context import CryptContext
from app.db.connection import get_connection, release_connection

pwd_context = CryptContext(schemes=["bcrypt"])
router = APIRouter(prefix="/auth", tags=["auth"])

class User(BaseModel):
    email: str
    password: str

class RegisterUser(BaseModel):
    email: str
    password: str
    username: str

class AuthResponse(BaseModel):
    status: str
    session_id: str
    message: str

class MessageResponse(BaseModel):
    status: str
    message: str


@router.post("/register", response_model=AuthResponse, tags=["auth"], dependencies=[Depends(check_rate_limit)])
async def register_user(register_request: RegisterUser):
    """
    Endpoint to register a new user.
    Validates the request, hashes the password, and stores the user in the database.
    """
    username = register_request.username.strip()
    if not username:
        raise HTTPException(status_code=400, detail="Username is required.")

    # Hash the password
    hashed_password = pwd_context.hash(register_request.password)

    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            """
            INSERT INTO users (email, hashed_password, username)
            VALUES (%s, %s, %s)
            RETURNING id
            """,
            (register_request.email, hashed_password, username)
        )

        user_id = cursor.fetchone()["id"]
        conn.commit()

        session_id = await create_session(user_id=user_id)

        return {"status": "success", "session_id": session_id, "message": "User registered successfully."}


    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=400, detail="Email or username already registered.")

    finally:
        cursor.close()
        release_connection(conn)


@router.post("/login", tags=["auth"], response_model=AuthResponse, dependencies=[Depends(check_rate_limit)])
async def login_user(login_request: User):
    """
    Endpoint to log in a user.
    Validates the request, checks the password, and creates a session.
    """
    conn = get_connection()
    cursor = conn.cursor()
      
    try:
        cursor.execute(
            """
            SELECT id, hashed_password FROM users
            WHERE email = %s
            """,
            (login_request.email,)
        )

        user = cursor.fetchone()

        if user is None:
            raise HTTPException(status_code=401, detail="User not found.")

        hashed_password = user["hashed_password"]

        # Verify the password
        if not pwd_context.verify(login_request.password, hashed_password):
            raise HTTPException(status_code=401, detail="Invalid email or password.")
    
        # Create session for the user
   
        user_id = user["id"]
        session_id = await create_session(user_id=user_id)
        return {"status": "success", "session_id": session_id, "message": "User logged in successfully."}
    
    except HTTPException:
        raise

    except Exception as e:
        raise HTTPException(status_code=401, detail="Invalid email or password.")

    finally:
        cursor.close()
        release_connection(conn)



@router.post("/logout", tags=["auth"], response_model=MessageResponse, dependencies=[Depends(check_rate_limit)])
async def logout_user(session_id: str = Header(alias="X-Session-Id"), user_id: int = Depends(get_session)):
    """
    Endpoint to log out a user.
    Deletes the session associated with the provided session ID.
    """

    await delete_session(session_id, user_id)
    return {"status": "success", "message": "User logged out successfully."}

@router.post("/logout-all",response_model=MessageResponse, dependencies=[Depends(check_rate_limit)])
async def logout_all(user_id: int = Depends(get_session)):
    await delete_all_sessions(user_id)
    return {"status": "success", "message": "All sessions terminated."}





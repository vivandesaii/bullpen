from fastapi import APIRouter, Depends, HTTPException
from app.services.leaderboard import get_top_n, get_user_rank
from app.services.rate_limit import check_rate_limit
from app.services.sessions import get_session

router = APIRouter(prefix="/leaderboard", tags=["leaderboard"])


@router.get("/", dependencies=[Depends(check_rate_limit)]) # Get the top N users in the leaderboard
async def leaderboard(n: int = 10):
    """
    Endpoint to fetch the top N users in the leaderboard.
    """
    top_users = await get_top_n(n)
    return {"top_users": top_users}

@router.get("/{user_id}", dependencies=[Depends(check_rate_limit)]) # Get rank by user ID
async def user_rank(user_id: int):
    """
    Endpoint to fetch the rank of a specific user in the leaderboard.
    """
    user_rank_info = await get_user_rank(user_id)
    if user_rank_info is None:
        raise HTTPException(status_code=404, detail="User not found in leaderboard.")
    return {"user_rank": user_rank_info}
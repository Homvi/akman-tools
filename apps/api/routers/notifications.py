from __future__ import annotations

from fastapi import APIRouter, Depends

from apps.api.deps import require_roles
from apps.api.models import User

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("")
def list_notifications(
    _: User = Depends(require_roles("planner", "admin", "worker")),
):
    return {"items": [], "unread": 0}

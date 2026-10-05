"""Local human-reviewer authentication boundary for approval decisions."""

import secrets
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Header, HTTPException

from app.config import Settings, get_settings


@dataclass(frozen=True)
class ReviewerIdentity:
    reviewer_id: str


def require_reviewer(
    settings: Annotated[Settings, Depends(get_settings)],
    authorization: Annotated[str | None, Header()] = None,
    reviewer_id: Annotated[str | None, Header(alias="X-Reviewer-Id")] = None,
) -> ReviewerIdentity:
    configured = settings.local_reviewer_token.get_secret_value()
    if not configured:
        raise HTTPException(status_code=503, detail="Local reviewer approval is not configured")
    scheme, _, supplied = (authorization or "").partition(" ")
    valid_token = bool(supplied) and secrets.compare_digest(supplied, configured)
    if scheme.lower() != "bearer" or not valid_token:
        raise HTTPException(status_code=401, detail="Invalid reviewer credential")
    if reviewer_id is None or not reviewer_id.strip() or len(reviewer_id) > 128:
        raise HTTPException(status_code=400, detail="X-Reviewer-Id is required")
    return ReviewerIdentity(reviewer_id=reviewer_id.strip())

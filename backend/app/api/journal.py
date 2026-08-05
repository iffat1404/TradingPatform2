from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from typing import Optional
from app.core.db import get_db
from app.core.security import get_current_user
from app.models.orm import JournalEntry
from app.models.schemas import JournalEntryCreate, JournalEntryUpdate, ALLOWED_EMOTIONAL_TAGS
from app.services.journal_engine import (
    create_entry,
    generate_entry_feedback,
    generate_insights,
    serialize_entry,
    _tags_to_str,
)

router = APIRouter()


def _get_owned_entry(db: Session, entry_id: str, account_id: str) -> JournalEntry:
    """Fetch an entry, 404ing if it doesn't exist or belongs to another account."""
    entry = (
        db.query(JournalEntry)
        .filter(JournalEntry.id == entry_id, JournalEntry.account_id == account_id)
        .first()
    )
    if entry is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Journal entry not found"
        )
    return entry


@router.get("/tags")
def get_allowed_tags():
    """The closed emotional-tag vocabulary the UI renders as selectable chips."""
    return {"tags": ALLOWED_EMOTIONAL_TAGS}


@router.post("/entries", status_code=status.HTTP_201_CREATED)
def create_journal_entry(
    entry_data: JournalEntryCreate,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Log a new journal entry, optionally linked to one of your own orders."""
    try:
        entry = create_entry(db, current_user["account_id"], entry_data)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    return serialize_entry(entry)


@router.get("/entries")
def list_journal_entries(
    ticker: Optional[str] = None,
    emotional_tag: Optional[str] = None,
    entry_type: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List your journal entries, newest first."""
    query = db.query(JournalEntry).filter(
        JournalEntry.account_id == current_user["account_id"]
    )

    if ticker:
        query = query.filter(JournalEntry.ticker == ticker.upper())
    if entry_type:
        query = query.filter(JournalEntry.entry_type == entry_type)

    entries = query.order_by(JournalEntry.created_at.desc()).all()

    # Tag filtering happens in Python: tags are stored comma-joined, so a LIKE would
    # match substrings across tag boundaries (e.g. "fear" hitting "fearful").
    if emotional_tag:
        wanted = emotional_tag.strip().lower()
        entries = [
            e for e in entries
            if wanted in [t.strip() for t in (e.emotional_tags or "").split(",")]
        ]

    return [serialize_entry(entry) for entry in entries]


@router.get("/insights")
def get_journal_insights(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Aggregate AI Coach view: deterministic behavioural stats over real trade history,
    narrated by GenAI when available.
    """
    return generate_insights(db, current_user["account_id"])


@router.get("/entries/{entry_id}")
def get_journal_entry(
    entry_id: str,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get a single journal entry with its linked trade resolved."""
    entry = _get_owned_entry(db, entry_id, current_user["account_id"])
    return serialize_entry(entry)


@router.put("/entries/{entry_id}")
def update_journal_entry(
    entry_id: str,
    update_data: JournalEntryUpdate,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Edit an entry's rationale or emotional tags."""
    entry = _get_owned_entry(db, entry_id, current_user["account_id"])

    if update_data.rationale is not None:
        entry.rationale = update_data.rationale.strip()
    if update_data.emotional_tags is not None:
        entry.emotional_tags = _tags_to_str(update_data.emotional_tags)

    db.commit()
    db.refresh(entry)
    return serialize_entry(entry)


@router.delete("/entries/{entry_id}")
def delete_journal_entry(
    entry_id: str,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a journal entry."""
    entry = _get_owned_entry(db, entry_id, current_user["account_id"])
    db.delete(entry)
    db.commit()
    return {"id": entry_id, "deleted": True}


@router.post("/entries/{entry_id}/analyze")
def analyze_journal_entry(
    entry_id: str,
    regenerate: bool = Query(False, description="Force a fresh analysis, ignoring the cached one"),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Generate (or return cached) AI coaching feedback for one entry."""
    entry = _get_owned_entry(db, entry_id, current_user["account_id"])
    return generate_entry_feedback(db, entry, regenerate=regenerate)

import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.deps import get_current_user
from app.db import get_db
from app.models.user import User
from app.schemas.common import CountResponse
from app.schemas.note_pins import PinArchiveRequest, PinCountResponse, PinCreateRequest, PinListResponse, PinPositionRequest, PinRead, PinUpdateRequest, RoomCreateRequest, RoomRequest, RoomRead, PinColorBatchRequest, PinPositionBatchRequest, ThoughtSummaryRead
from app.services.note_pin_service import NotePinService

router = APIRouter(prefix="/api/notes/pins", tags=["notes"])

@router.get("", response_model=PinListResponse)
def list_pins(collection_id: uuid.UUID, archived: bool = False, room_id: uuid.UUID | None = None, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return PinListResponse(items=[PinRead.model_validate(pin) for pin in NotePinService(db, user.id).list(collection_id, archived, room_id)])

@router.get("/count", response_model=PinCountResponse)
def count_pins(collection_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return PinCountResponse(count=NotePinService(db, user.id).count(collection_id))

@router.post("", response_model=PinRead, status_code=201)
def create_pin(payload: PinCreateRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return NotePinService(db, user.id).create(payload)

@router.post("/archive", response_model=CountResponse)
def archive_pins(payload: PinArchiveRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return CountResponse(count=NotePinService(db, user.id).archive(payload.collection_id, payload.ids, payload.archived))

@router.get("/rooms", response_model=list[RoomRead])
def list_rooms(collection_id: uuid.UUID | None = None, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    service = NotePinService(db, user.id)
    rooms = service.rooms(collection_id)
    pins = service.list(collection_id)
    result = []
    for room in rooms:
        item = RoomRead.model_validate(room)
        contents = [pin for pin in pins if pin.room_id == room.id]
        item.content = "\n".join(pin.text for pin in contents)
        item.note_count = len(contents)
        if contents:
            item.updated_at = max(item.updated_at, *(pin.updated_at for pin in contents))
        result.append(item)
    return result

@router.post("/rooms", response_model=RoomRead, status_code=201)
def create_room(payload: RoomCreateRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return NotePinService(db, user.id).create_room(payload.collection_id, payload.title)

@router.patch("/rooms/{room_id}", response_model=RoomRead)
def rename_room(room_id: uuid.UUID, payload: RoomRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return NotePinService(db, user.id).rename_room(room_id, payload.title)

@router.delete("/rooms/{room_id}", status_code=204)
def delete_room(room_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    NotePinService(db, user.id).delete_room(room_id)

@router.patch("/colors", response_model=PinListResponse)
def color_pins(payload: PinColorBatchRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return PinListResponse(items=[PinRead.model_validate(pin) for pin in NotePinService(db, user.id).color_many(payload)])

@router.patch("/positions", response_model=PinListResponse)
def move_pins(payload: PinPositionBatchRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return PinListResponse(items=[PinRead.model_validate(pin) for pin in NotePinService(db, user.id).move_many(payload)])

@router.post("/rooms/{room_id}/summary", response_model=ThoughtSummaryRead)
def summarize_room(room_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    from app.services.thought_summary import ThoughtSummaryService
    from app.services.note_ai import NoteAIProviderError
    try:
        return ThoughtSummaryService(db, user.id).summarize(room_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except NoteAIProviderError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

@router.patch("/{pin_id}", response_model=PinRead)
def update_pin(pin_id: uuid.UUID, payload: PinUpdateRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return NotePinService(db, user.id).update(pin_id, payload)

@router.patch("/{pin_id}/position", response_model=PinRead)
def move_pin(pin_id: uuid.UUID, payload: PinPositionRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return NotePinService(db, user.id).move(pin_id, payload)

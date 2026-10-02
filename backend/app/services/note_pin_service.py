import re
import uuid
from sqlalchemy import func, select, delete
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from app.core.errors import ConflictError, NotFoundError
from app.models.note_pin import NotePin, ThoughtRoom
from app.models.note_collection import NoteCollection
from app.schemas.note_pins import PinCreateRequest, PinPositionRequest, PinUpdateRequest
from app.services.note_collection_service import NoteCollectionService
from app.services.note_service import NoteService

HASHTAG = re.compile(r"(?<![\w/#])#([^\W\d][\w-]{0,63})", re.UNICODE)

def hashtag_names(text: str) -> list[str]:
    names = {}
    for name in HASHTAG.findall(text):
        names.setdefault(name.casefold(), name)
    return list(names.values())[:50]

class NotePinService:
    def __init__(self, db: Session, owner_id: uuid.UUID):
        self.db, self.owner_id = db, owner_id

    def _collection(self, collection_id):
        return NoteCollectionService(self.db, self.owner_id).resolve_id(collection_id)

    def _get(self, pin_id):
        pin = self.db.scalar(select(NotePin).where(NotePin.id == pin_id, NotePin.owner_id == self.owner_id))
        if pin is None:
            raise NotFoundError("Gedanke nicht gefunden")
        return pin

    def list(self, collection_id, archived=False, room_id=None):
        self._collection(collection_id)
        if room_id:
            self.get_room(room_id, collection_id)
        return list(self.db.scalars(select(NotePin).where(
            NotePin.owner_id == self.owner_id, NotePin.collection_id == collection_id,
            NotePin.status == ("archived" if archived else "open"),
            *([NotePin.room_id == room_id] if room_id else []),
        ).order_by(NotePin.created_at.desc(), NotePin.id.desc())).all())

    def count(self, collection_id):
        self._collection(collection_id)
        return self.db.scalar(select(func.count()).select_from(NotePin).where(
            NotePin.owner_id == self.owner_id, NotePin.collection_id == collection_id, NotePin.status == "open")) or 0

    def _tags(self, pin):
        vocabulary = NoteService(self.db, self.owner_id)
        pin.tags = [tag for name in hashtag_names(pin.text) if (tag := vocabulary._get_or_create_tag(name)) is not None]

    def create(self, payload: PinCreateRequest):
        collection_id = self._collection(payload.collection_id)
        def retry_result():
            existing = self.db.scalar(select(NotePin).where(NotePin.id == payload.request_id, NotePin.owner_id == self.owner_id))
            if existing and existing.collection_id == collection_id and existing.text == payload.text and (payload.room_id is None or existing.room_id == payload.room_id):
                return existing
            raise ConflictError("Dieser Gedanke wurde bereits mit anderem Inhalt gespeichert. Bitte neu laden.")
        if payload.request_id and self.db.scalar(select(NotePin.id).where(NotePin.id == payload.request_id)):
            return retry_result()
        room = self.get_room(payload.room_id, collection_id) if payload.room_id else self.ensure_room(collection_id)
        position = (payload.position_x, payload.position_y) if payload.position_x is not None else self._free_position(room.id)
        pin = NotePin(room_id=room.id, id=payload.request_id or uuid.uuid4(), owner_id=self.owner_id, collection_id=collection_id, text=payload.text, title_color=payload.title_color, status="open", position_x=position[0], position_y=position[1])
        self.db.add(pin)
        try:
            self._tags(pin)
            self.db.commit()
        except IntegrityError:
            self.db.rollback()
            if not payload.request_id:
                raise
            return retry_result()
        self.db.refresh(pin)
        return pin

    def _free_position(self, room_id):
        """First free slot on a 4-column grid, so quick-captured thoughts do not pile up."""
        taken = [(x, y) for x, y in self.db.execute(select(NotePin.position_x, NotePin.position_y).where(
            NotePin.owner_id == self.owner_id, NotePin.room_id == room_id, NotePin.status == "open",
            NotePin.position_x.is_not(None))).all()]
        for row in range(500):
            for col in range(4):
                x, y = 24 + col * 320, 24 + row * 220
                if all(abs(x - tx) >= 160 or abs(y - ty) >= 110 for tx, ty in taken):
                    return x, y
        return 24, 24

    def update(self, pin_id, payload: PinUpdateRequest):
        pin = self.db.scalar(select(NotePin).where(NotePin.id == pin_id, NotePin.owner_id == self.owner_id).with_for_update())
        if pin is None:
            raise NotFoundError("Gedanke nicht gefunden")
        if pin.updated_at != payload.base_updated_at:
            raise ConflictError("Dieser Gedanke wurde inzwischen geändert. Bitte neu laden.")
        if "title_color" in payload.model_fields_set:
            pin.title_color = payload.title_color
        pin.text = payload.text
        self._tags(pin)
        self.db.commit()
        self.db.refresh(pin)
        return pin

    def move(self, pin_id, payload: PinPositionRequest):
        pin = self.db.scalar(select(NotePin).where(NotePin.id == pin_id, NotePin.owner_id == self.owner_id).with_for_update())
        if pin is None:
            raise NotFoundError("Gedanke nicht gefunden")
        if pin.updated_at != payload.base_updated_at:
            raise ConflictError("Dieser Gedanke wurde inzwischen geändert. Bitte neu laden.")
        pin.position_x, pin.position_y = payload.position_x, payload.position_y
        self.db.commit()
        self.db.refresh(pin)
        return pin

    def archive(self, collection_id, ids, archived=True):
        self._collection(collection_id)
        pins = list(self.db.scalars(select(NotePin).where(
            NotePin.owner_id == self.owner_id, NotePin.collection_id == collection_id, NotePin.id.in_(ids),
            NotePin.status == ("open" if archived else "archived"),
        ).with_for_update()).all())
        for pin in pins:
            pin.status = "archived" if archived else "open"
        self.db.commit()
        return len(pins)

    def get_room(self, room_id, collection_id=None):
        room = self.db.scalar(select(ThoughtRoom).where(ThoughtRoom.id == room_id, ThoughtRoom.owner_id == self.owner_id))
        if room is None or (collection_id and room.collection_id != collection_id):
            raise NotFoundError("Sammlung nicht gefunden")
        return room

    def ensure_room(self, collection_id):
        def first_room():
            return self.db.scalar(select(ThoughtRoom).where(ThoughtRoom.owner_id == self.owner_id, ThoughtRoom.collection_id == collection_id).order_by(ThoughtRoom.created_at))
        room = first_room()
        if room is None:
            # Serialize first-use creation per collection so parallel requests share one canvas.
            self.db.scalar(select(NoteCollection).where(NoteCollection.id == collection_id, NoteCollection.owner_id == self.owner_id).with_for_update())
            room = first_room() or self.create_room(collection_id, "Meine Gedanken")
        return room

    def create_room(self, collection_id, title=None):
        self._collection(collection_id)
        if title is None:
            # Serialize automatic naming within the collection, including parallel requests.
            self.db.scalar(select(NoteCollection).where(NoteCollection.id == collection_id, NoteCollection.owner_id == self.owner_id).with_for_update())
            titles = self.db.scalars(select(ThoughtRoom.title).where(ThoughtRoom.owner_id == self.owner_id, ThoughtRoom.collection_id == collection_id)).all()
            numbers = [int(match.group(1)) for name in titles if (match := re.fullmatch(r"(?:Sammlung|Fläche) (\d+)", name))]
            title = f"Sammlung {max(numbers, default=0) + 1}"
        room = ThoughtRoom(owner_id=self.owner_id, collection_id=collection_id, title=title)
        self.db.add(room)
        self.db.commit()
        self.db.refresh(room)
        return room

    def rooms(self, collection_id):
        self._collection(collection_id)
        return list(self.db.scalars(select(ThoughtRoom).where(ThoughtRoom.owner_id == self.owner_id, ThoughtRoom.collection_id == collection_id).order_by(ThoughtRoom.created_at)).all())

    def rename_room(self, room_id, title):
        room = self.get_room(room_id)
        room.title = title
        self.db.commit()
        self.db.refresh(room)
        return room

    def delete_room(self, room_id):
        room = self.get_room(room_id)
        self.db.execute(delete(NotePin).where(NotePin.owner_id == self.owner_id, NotePin.room_id == room.id))
        self.db.delete(room)
        self.db.commit()

    def color_many(self, payload):
        self.get_room(payload.room_id)
        ids = set(payload.ids)
        pins = list(self.db.scalars(select(NotePin).where(NotePin.id.in_(ids), NotePin.owner_id == self.owner_id, NotePin.room_id == payload.room_id, NotePin.status == "open").order_by(NotePin.id).with_for_update()).all())
        if len(pins) != len(ids):
            raise NotFoundError("Gedanke nicht gefunden")
        if any(payload.base_updated_at.get(pin.id) != pin.updated_at for pin in pins):
            raise ConflictError("Ein Gedanke wurde inzwischen geändert. Bitte neu laden.")
        for pin in pins:
            pin.title_color = payload.title_color
        self.db.commit()
        for pin in pins:
            self.db.refresh(pin)
        return pins

    def move_many(self, payload):
        self.get_room(payload.room_id)
        positions = {item.id: item for item in payload.items}
        pins = list(self.db.scalars(select(NotePin).where(NotePin.id.in_(positions), NotePin.owner_id == self.owner_id, NotePin.room_id == payload.room_id, NotePin.status == "open").order_by(NotePin.id).with_for_update()).all())
        if len(pins) != len(positions):
            raise NotFoundError("Gedanke nicht gefunden")
        if any(positions[pin.id].base_updated_at != pin.updated_at for pin in pins):
            raise ConflictError("Ein Gedanke wurde inzwischen geändert. Bitte neu laden.")
        for pin in pins:
            item = positions[pin.id]
            pin.position_x, pin.position_y = item.position_x, item.position_y
        self.db.commit()
        for pin in pins:
            self.db.refresh(pin)
        return pins

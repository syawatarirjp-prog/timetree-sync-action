from dataclasses import dataclass, field
from datetime import datetime
from typing import ClassVar
from zoneinfo import ZoneInfo


GOOGLE_EVENT_COLORS = {
    "1": "#a4bdfc",
    "2": "#7ae7bf",
    "3": "#dbadff",
    "4": "#ff887c",
    "5": "#fbd75b",
    "6": "#ffb878",
    "7": "#46d6db",
    "8": "#e1e1e1",
    "9": "#5484ed",
    "10": "#51b749",
    "11": "#dc2127",
}


def _color_to_hex(color) -> str | None:
    if isinstance(color, int):
        return f"#{color:06x}"
    if isinstance(color, str):
        value = color.strip()
        if not value:
            return None
        if not value.startswith("#"):
            value = "#" + value
        if len(value) == 7:
            return value.lower()
    return None


def _parse_hex(color: str | None) -> tuple[int, int, int] | None:
    if not color:
        return None
    text = color.lstrip("#")
    if len(text) != 6:
        return None
    try:
        return (
            int(text[0:2], 16),
            int(text[2:4], 16),
            int(text[4:6], 16),
        )
    except ValueError:
        return None


def _nearest_google_color_id(color: str | None) -> str | None:
    target = _parse_hex(color)
    if target is None:
        return None

    best_id = None
    best_distance = None
    for color_id, candidate_hex in GOOGLE_EVENT_COLORS.items():
        candidate = _parse_hex(candidate_hex)
        if candidate is None:
            continue
        distance = sum(
            (target_channel - candidate_channel) ** 2
            for target_channel, candidate_channel in zip(target, candidate)
        )
        if best_distance is None or distance < best_distance:
            best_id = color_id
            best_distance = distance
    return best_id


def _extract_label_id(event: dict):
    label_id = event.get("label_id")
    if label_id is not None:
        return label_id

    try:
        relationship_id = event["relationships"]["label"]["data"]["id"]
    except (KeyError, TypeError):
        return None

    if isinstance(relationship_id, str) and "," in relationship_id:
        relationship_id = relationship_id.split(",")[-1]

    try:
        return int(relationship_id)
    except (TypeError, ValueError):
        return relationship_id


def _calendar_labels(metadata: dict) -> dict:
    labels = {}
    for label in metadata.get("calendar_labels") or []:
        label_id = label.get("id")
        if label_id is None:
            continue
        labels[label_id] = {
            "name": label.get("name") or "",
            "color": _color_to_hex(label.get("color")),
        }
    return labels


def _calendar_users(metadata: dict) -> dict:
    users = {}
    for user in metadata.get("calendar_users") or []:
        user_id = user.get("user_id")
        if user_id is None:
            user_id = user.get("id")
        if user_id is None:
            continue
        name = user.get("name")
        if name:
            users[user_id] = str(name)
            users[str(user_id)] = str(name)
    return users


def _assignee_names(event: dict, metadata: dict) -> list[str]:
    user_names = _calendar_users(metadata)
    names = []

    for attendee_id in event.get("attendees") or []:
        name = user_names.get(attendee_id) or user_names.get(str(attendee_id))
        if name and name not in names:
            names.append(name)

    attachment = event.get("attachment") or {}
    for virtual_attendee in attachment.get("virtual_user_attendees") or []:
        if isinstance(virtual_attendee, str) and virtual_attendee.strip():
            name = virtual_attendee.strip()
            if name not in names:
                names.append(name)

    return names


@dataclass
class Event:
    SYNC_SOURCE: ClassVar[str] = "timetree-sync-action"

    id: str
    title: str
    start: datetime
    end: datetime
    all_day: bool
    location: str | None = None
    description: str | None = None
    source_calendar_name: str | None = None
    label_name: str | None = None
    label_color: str | None = None
    assignee_names: list[str] = field(default_factory=list)

    @classmethod
    def from_timetree(
        cls,
        event: dict,
        *,
        calendar_name: str | None = None,
        calendar_metadata: dict | None = None,
    ):
        start_tz = ZoneInfo(event["start_timezone"])
        end_tz = ZoneInfo(event["end_timezone"])
        metadata = calendar_metadata or {}

        label_id = _extract_label_id(event)
        label = _calendar_labels(metadata).get(label_id) or {}

        return cls(
            id=event["id"],
            title=event["title"],
            start=datetime.fromtimestamp(
                event["start_at"] / 1000,
                tz=start_tz,
            ),
            end=datetime.fromtimestamp(
                event["end_at"] / 1000,
                tz=end_tz,
            ),
            all_day=event["all_day"],
            location=event.get("location") or None,
            description=event.get("note") or None,
            source_calendar_name=calendar_name,
            label_name=label.get("name") or None,
            label_color=label.get("color"),
            assignee_names=_assignee_names(event, metadata),
        )

    def _google_description(self) -> str | None:
        parts = []

        if self.description:
            parts.append(self.description.rstrip())

        metadata_lines = []
        if self.source_calendar_name:
            metadata_lines.append(f"元カレンダー：{self.source_calendar_name}")

        if self.label_name:
            metadata_lines.append(f"ラベル：{self.label_name}")
        elif self.label_color:
            metadata_lines.append("ラベル：（名称なし）")

        if self.assignee_names:
            metadata_lines.append(f"担当者：{'、'.join(self.assignee_names)}")

        if metadata_lines:
            parts.append(
                "--- TimeTree同期情報 ---\n" + "\n".join(metadata_lines)
            )

        return "\n\n".join(parts) or None

    def to_google(self, calendar_code: str) -> dict:
        event = {
            "summary": self.title,
            "extendedProperties": {
                "private": {
                    "sync_source": self.SYNC_SOURCE,
                    "timetree_calendar_code": calendar_code,
                    "timetree_id": self.id,
                }
            },
        }

        if self.all_day:
            event["start"] = {
                "date": self.start.strftime("%Y-%m-%d"),
            }
            event["end"] = {
                "date": self.end.strftime("%Y-%m-%d"),
            }
        else:
            event["start"] = {
                "dateTime": self.start.isoformat(),
                "timeZone": "Asia/Tokyo",
            }
            event["end"] = {
                "dateTime": self.end.isoformat(),
                "timeZone": "Asia/Tokyo",
            }

        if self.location:
            event["location"] = self.location

        description = self._google_description()
        if description:
            event["description"] = description

        color_id = _nearest_google_color_id(self.label_color)
        if color_id:
            event["colorId"] = color_id

        return event

    def equals_google(self, google_event: dict, calendar_code: str) -> bool:
        google = self.to_google(calendar_code)

        return (
            google.get("summary") == google_event.get("summary")
            and google.get("location") == google_event.get("location")
            and google.get("description") == google_event.get("description")
            and google.get("start") == google_event.get("start")
            and google.get("end") == google_event.get("end")
            and google.get("colorId") == google_event.get("colorId")
        )

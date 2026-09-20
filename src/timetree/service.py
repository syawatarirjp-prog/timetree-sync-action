from timetree_exporter.api.auth import login
from timetree_exporter.api.calendar import TimeTreeCalendar
from timetree_exporter.calendar import Calendar


class TimeTreeService:
    """Bridge to the bundled TimeTree-exporter."""

    def login(self, email: str, password: str) -> None:
        session_id = login(email, password)
        if session_id is None:
            raise RuntimeError("Failed to login to TimeTree.")
        self._calendar_api = TimeTreeCalendar(session_id)

    def get_calendars(self) -> list[dict]:
        if not hasattr(self, "_calendar_api"):
            raise RuntimeError("Not logged in.")
        calendars = self._calendar_api.get_metadata()
        return [
            calendar for calendar in calendars if calendar["deactivated_at"] is None
        ]

    def _to_calendar(self, metadata: dict) -> Calendar:
        return Calendar(
            api=self._calendar_api,
            metadata=metadata,
        )

    def get_calendar(self, alias_code: str) -> Calendar:
        calendars = self.get_calendars()

        for metadata in calendars:
            if metadata["alias_code"] == alias_code:
                return self._to_calendar(metadata)
        raise RuntimeError(f"Calendar '{alias_code}' not found.")

    def get_calendar_by_name(self, name: str) -> Calendar:
        calendars = self.get_calendars()
        matches = [metadata for metadata in calendars if metadata["name"] == name]

        if not matches:
            available = ", ".join(metadata["name"] for metadata in calendars)
            raise RuntimeError(
                f"Calendar named '{name}' not found. Available calendars: {available}"
            )

        if len(matches) > 1:
            raise RuntimeError(
                f"More than one TimeTree calendar is named '{name}'. "
                "Rename one of them or use TIMETREE_CALENDAR_CODE."
            )

        return self._to_calendar(matches[0])

    def get_events(self, calendar: Calendar):
        return calendar.get_events()

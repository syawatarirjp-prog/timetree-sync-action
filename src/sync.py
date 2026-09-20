from config import Config
from gcalendar import GoogleCalendarClient
from logger import logger
from models import Event
from timetree import TimeTree


def _private_properties(google_event: dict) -> dict:
    return google_event.get("extendedProperties", {}).get("private", {})


def _is_managed_google_event(google_event: dict, calendar_code: str) -> bool:
    """Return True only for events owned by this TimeTree sync.

    Events created by older versions are also accepted when they contain a
    timetree_id but do not yet have the newer ownership markers.
    """
    props = _private_properties(google_event)
    timetree_id = props.get("timetree_id")

    if not timetree_id:
        return False

    sync_source = props.get("sync_source")
    source_calendar_code = props.get("timetree_calendar_code")

    # Backward compatibility for events created by older versions.
    if sync_source is None and source_calendar_code is None:
        return True

    return sync_source == Event.SYNC_SOURCE and source_calendar_code == calendar_code


def sync():
    client = TimeTree()
    client.login(
        Config.TIMETREE_EMAIL,
        Config.TIMETREE_PASSWORD,
    )

    if Config.TIMETREE_CALENDAR_CODE:
        calendar = client.get_calendar(Config.TIMETREE_CALENDAR_CODE)
    else:
        calendar = client.get_calendar_by_name(Config.TIMETREE_CALENDAR_NAME)

    calendar_code = calendar.alias_code
    if not calendar_code:
        raise RuntimeError("Selected TimeTree calendar does not have an alias code.")

    logger.info("Selected TimeTree calendar: %s", calendar.name)

    raw_events = client.get_events(calendar)
    events = [Event.from_timetree(raw) for raw in raw_events]
    timetree_ids = {event.id for event in events}

    google = GoogleCalendarClient(
        Config.GOOGLE_SERVICE_ACCOUNT_JSON,
    )
    logger.info("Connected to Google Calendar")

    google_events = google.list_events(
        Config.GOOGLE_CALENDAR_ID,
    )

    google_event_map: dict[str, list[dict]] = {}

    for google_event in google_events:
        if not _is_managed_google_event(
            google_event,
            calendar_code,
        ):
            continue

        timetree_id = _private_properties(google_event)["timetree_id"]
        google_event_map.setdefault(timetree_id, []).append(google_event)

    created_count = 0
    updated_count = 0
    deleted_count = 0
    skipped_count = 0

    for event in events:
        matches = google_event_map.get(event.id, [])
        if not matches:
            google.create_event(
                Config.GOOGLE_CALENDAR_ID,
                event.to_google(calendar_code),
            )
            created_count += 1
            continue

        google_event = matches[0]
        props = _private_properties(google_event)
        needs_marker_migration = (
            props.get("sync_source") != Event.SYNC_SOURCE
            or props.get("timetree_calendar_code") != calendar_code
        )

        if needs_marker_migration or not event.equals_google(
            google_event,
            calendar_code,
        ):
            google.update_event(
                Config.GOOGLE_CALENDAR_ID,
                google_event["id"],
                event.to_google(calendar_code),
            )
            updated_count += 1
        else:
            skipped_count += 1

        for duplicate in matches[1:]:
            google.delete_event(
                Config.GOOGLE_CALENDAR_ID,
                duplicate["id"],
            )
            deleted_count += 1

    for timetree_id, matches in google_event_map.items():
        if timetree_id in timetree_ids:
            continue

        for google_event in matches:
            google.delete_event(
                Config.GOOGLE_CALENDAR_ID,
                google_event["id"],
            )
            deleted_count += 1

    logger.info(
        "Sync complete: created=%d updated=%d deleted=%d skipped=%d",
        created_count,
        updated_count,
        deleted_count,
        skipped_count,
    )

import json
import time
from typing import ClassVar

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


class GoogleCalendarClient:
    SCOPES: ClassVar[list[str]] = ["https://www.googleapis.com/auth/calendar"]
    MAX_RETRY_ATTEMPTS: ClassVar[int] = 7
    WRITE_DELAY_SECONDS: ClassVar[float] = 0.35

    def __init__(self, credentials_json: str):
        credentials_info = json.loads(credentials_json)

        credentials = service_account.Credentials.from_service_account_info(
            credentials_info,
            scopes=self.SCOPES,
        )

        self._service = build(
            "calendar",
            "v3",
            credentials=credentials,
        )

    @staticmethod
    def _is_retryable_http_error(exc: HttpError) -> bool:
        status = getattr(exc.resp, "status", None)
        if status in {429, 500, 502, 503, 504}:
            return True

        if status == 403:
            message = str(exc)
            return (
                "rateLimitExceeded" in message
                or "Rate Limit Exceeded" in message
                or "userRateLimitExceeded" in message
            )

        return False

    def _execute_with_retry(self, request, *, is_write: bool = False):
        if is_write:
            time.sleep(self.WRITE_DELAY_SECONDS)

        for attempt in range(self.MAX_RETRY_ATTEMPTS):
            try:
                return request.execute()
            except HttpError as exc:
                is_last_attempt = attempt == self.MAX_RETRY_ATTEMPTS - 1
                if not self._is_retryable_http_error(exc) or is_last_attempt:
                    raise

                delay = min(2 ** attempt, 32)
                time.sleep(delay)

        raise RuntimeError("Google Calendar request retry loop exited unexpectedly.")

    def get_calendar(self, calendar_id: str):
        request = self._service.calendars().get(calendarId=calendar_id)
        return self._execute_with_retry(request)

    def create_event(self, calendar_id: str, event: dict):
        request = self._service.events().insert(
            calendarId=calendar_id,
            body=event,
        )
        return self._execute_with_retry(request, is_write=True)

    def list_events(self, calendar_id: str):
        events = []
        page_token = None
        while True:
            request = self._service.events().list(
                calendarId=calendar_id,
                singleEvents=False,
                maxResults=2500,
                pageToken=page_token,
            )
            response = self._execute_with_retry(request)
            events.extend(response.get("items", []))
            page_token = response.get("nextPageToken")
            if not page_token:
                break
        return events

    def update_event(self, calendar_id: str, event_id: str, event: dict):
        request = self._service.events().update(
            calendarId=calendar_id,
            eventId=event_id,
            body=event,
        )
        return self._execute_with_retry(request, is_write=True)

    def delete_event(self, calendar_id: str, event_id: str):
        request = self._service.events().delete(
            calendarId=calendar_id,
            eventId=event_id,
        )
        return self._execute_with_retry(request, is_write=True)

import os


class Config:
    TIMETREE_EMAIL = os.getenv("TIMETREE_EMAIL")
    TIMETREE_PASSWORD = os.getenv("TIMETREE_PASSWORD")
    TIMETREE_CALENDAR_CODE = os.getenv("TIMETREE_CALENDAR_CODE")
    TIMETREE_CALENDAR_NAME = os.getenv("TIMETREE_CALENDAR_NAME")
    GOOGLE_SERVICE_ACCOUNT_JSON = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
    GOOGLE_CALENDAR_ID = os.getenv("GOOGLE_CALENDAR_ID")

    @classmethod
    def validate(cls):
        required = {
            "TIMETREE_EMAIL": cls.TIMETREE_EMAIL,
            "TIMETREE_PASSWORD": cls.TIMETREE_PASSWORD,
            "GOOGLE_SERVICE_ACCOUNT_JSON": cls.GOOGLE_SERVICE_ACCOUNT_JSON,
            "GOOGLE_CALENDAR_ID": cls.GOOGLE_CALENDAR_ID,
        }
        missing = [key for key, value in required.items() if not value]
        if missing:
            raise RuntimeError("Missing environment variables: " + ", ".join(missing))

        if not cls.TIMETREE_CALENDAR_CODE and not cls.TIMETREE_CALENDAR_NAME:
            raise RuntimeError(
                "Set either TIMETREE_CALENDAR_CODE or TIMETREE_CALENDAR_NAME."
            )

import os
import json

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build


SCOPES = ["https://www.googleapis.com/auth/drive.file"]


def get_drive_service():

    creds = None

    # =====================================================
    # GITHUB ACTIONS
    # =====================================================

    token_json = os.environ.get("GOOGLE_TOKEN_JSON")

    if token_json:
        try:
            token_data = json.loads(token_json)

            creds = Credentials.from_authorized_user_info(
                token_data,
                SCOPES
            )

            print("Using Google Drive credentials from GitHub Secret.")

        except Exception as e:
            raise RuntimeError(
                f"Invalid GOOGLE_TOKEN_JSON secret: {e}"
            )

    # =====================================================
    # LOCAL COMPUTER
    # =====================================================

    else:

        if os.path.exists("token.json"):
            creds = Credentials.from_authorized_user_file(
                "token.json",
                SCOPES
            )

        if not creds or not creds.valid:

            if creds and creds.expired and creds.refresh_token:

                creds.refresh(Request())

            else:

                flow = InstalledAppFlow.from_client_secrets_file(
                    "credentials.json",
                    SCOPES
                )

                creds = flow.run_local_server(port=0)

            with open("token.json", "w", encoding="utf-8") as token:
                token.write(creds.to_json())

    # =====================================================
    # REFRESH
    # =====================================================

    if creds and creds.expired and creds.refresh_token:

        creds.refresh(Request())

    if not creds or not creds.valid:

        raise RuntimeError(
            "Google Drive credentials are missing or invalid."
        )

    # =====================================================
    # DRIVE SERVICE
    # =====================================================

    return build(
        "drive",
        "v3",
        credentials=creds
    )

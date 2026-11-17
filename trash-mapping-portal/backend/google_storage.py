import json
import os
from datetime import datetime
from io import BytesIO

import gspread
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

RAW_TAB = "Page 1 unprocessed"
PROCESSED_TAB = "Page 2 processed"

RAW_HEADERS = [
    "Upload date", "Latitude", "Longitude", "Image URL", "Status",
    "File size (MB)", "Width", "Height", "Camera", "ISO",
    "Exposure", "Original capture date"
]
PROCESSED_HEADERS = [
    "Upload date", "Latitude", "Longitude", "Image URL", "Processing status",
    "File size (MB)", "Width", "Height", "Camera", "ISO",
    "Exposure", "Original capture date", "Processed date", "Detection results"
]


def _clients():
    raw = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip()
    spreadsheet_id = os.environ.get("GOOGLE_SPREADSHEET_ID", "").strip()
    if not raw or not spreadsheet_id:
        raise RuntimeError("Google storage is not configured. Set GOOGLE_SERVICE_ACCOUNT_JSON and GOOGLE_SPREADSHEET_ID.")
    info = json.loads(raw)
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    credentials = Credentials.from_service_account_info(info, scopes=scopes)
    gc = gspread.authorize(credentials)
    spreadsheet = gc.open_by_key(spreadsheet_id)
    drive = build("drive", "v3", credentials=credentials, cache_discovery=False)
    return spreadsheet, drive


def _worksheet(spreadsheet, title, headers):
    try:
        ws = spreadsheet.worksheet(title)
    except gspread.WorksheetNotFound:
        ws = spreadsheet.add_worksheet(title=title, rows=1000, cols=max(14, len(headers)))
    if not ws.row_values(1):
        ws.append_row(headers, value_input_option="USER_ENTERED")
    return ws


def save_submission(image_bytes: bytes, filename: str, mime_type: str, metadata: dict) -> dict:
    spreadsheet, drive = _clients()
    folder_id = os.environ.get("GOOGLE_DRIVE_FOLDER_ID", "").strip()
    folder_name = os.environ.get("GOOGLE_DRIVE_FOLDER_NAME", "Uploaded images map thesis")

    if not folder_id:
        query = (
            "mimeType='application/vnd.google-apps.folder' and "
            f"name='{folder_name.replace(chr(39), chr(92) + chr(39))}' and trashed=false"
        )
        found = drive.files().list(q=query, fields="files(id,name)", pageSize=10, supportsAllDrives=True, includeItemsFromAllDrives=True).execute().get("files", [])
        if found:
            folder_id = found[0]["id"]
        else:
            folder = drive.files().create(
                body={"name": folder_name, "mimeType": "application/vnd.google-apps.folder"},
                fields="id", supportsAllDrives=True
            ).execute()
            folder_id = folder["id"]

    safe_name = filename.replace("/", "_").replace("\\", "_")[:180]
    media = MediaIoBaseUpload(BytesIO(image_bytes), mimetype=mime_type or "application/octet-stream", resumable=False)
    uploaded = drive.files().create(
        body={"name": f"{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{safe_name}", "parents": [folder_id]},
        media_body=media,
        fields="id,name,webViewLink", supportsAllDrives=True
    ).execute()
    file_id = uploaded["id"]

    # Public map previews require link-view access. This can be changed to private storage
    # if a future authenticated image-proxy endpoint is added.
    drive.permissions().create(
        fileId=file_id,
        body={"type": "anyone", "role": "reader"},
        fields="id", supportsAllDrives=True
    ).execute()
    image_url = f"https://drive.google.com/thumbnail?id={file_id}&sz=w1000"

    now = datetime.now().astimezone()
    upload_date = now.strftime("%m/%d/%Y %H:%M:%S")
    lat, lng = metadata.get("latitude"), metadata.get("longitude")
    status = "Pending YOLO Processing"
    common = [
        upload_date, lat if lat is not None else "", lng if lng is not None else "",
        image_url, status, metadata.get("file_size_mb", ""),
        metadata.get("width", ""), metadata.get("height", ""),
        metadata.get("camera", "Unknown"), metadata.get("iso", "Unknown"),
        metadata.get("exposure", "Unknown"), metadata.get("original_date", "Unknown")
    ]

    raw_ws = _worksheet(spreadsheet, RAW_TAB, RAW_HEADERS)
    processed_ws = _worksheet(spreadsheet, PROCESSED_TAB, PROCESSED_HEADERS)
    raw_ws.append_row(common, value_input_option="USER_ENTERED")
    processed_ws.append_row(
        common + ["", "Not yet analyzed — YOLO model not configured"],
        value_input_option="USER_ENTERED"
    )

    return {
        "image_url": image_url,
        "upload_date": upload_date,
        "status": status,
        "drive_file_id": file_id,
    }


def get_map_rows(tab_name: str) -> list[dict]:
    spreadsheet, _ = _clients()
    headers = RAW_HEADERS if tab_name == RAW_TAB else PROCESSED_HEADERS
    ws = _worksheet(spreadsheet, tab_name, headers)
    rows = ws.get_all_records()
    reports = []
    for row in rows:
        try:
            lat = float(str(row.get("Latitude", "")).replace(",", "."))
            lng = float(str(row.get("Longitude", "")).replace(",", "."))
            if not (-90 <= lat <= 90 and -180 <= lng <= 180):
                lat = lng = None
        except (TypeError, ValueError):
            lat = lng = None
        reports.append({
            "upload_date": row.get("Upload date", ""),
            "latitude": lat,
            "longitude": lng,
            "image_url": row.get("Image URL", ""),
            "status": row.get("Status", row.get("Processing status", "")),
            "file_size_mb": row.get("File size (MB)", ""),
            "width": row.get("Width", ""),
            "height": row.get("Height", ""),
            "camera": row.get("Camera", ""),
            "iso": row.get("ISO", ""),
            "exposure": row.get("Exposure", ""),
            "original_date": row.get("Original capture date", ""),
            "processed_date": row.get("Processed date", ""),
            "detection_results": row.get("Detection results", ""),
        })
    return reports

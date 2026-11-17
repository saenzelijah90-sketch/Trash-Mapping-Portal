# Trash & Road Damage Mapping Portal

A public photo-submission website with EXIF GPS extraction, Google Sheets/Drive storage, and two Leaflet maps.

## Current capabilities

- Public single-photo and batch-photo uploads
- Extracts GPS coordinates from the **photo's EXIF metadata** (not the uploader's current phone location)
- Extracts original capture date, camera make/model, ISO, exposure, image dimensions and file size
- Saves original images to Google Drive
- Appends records to `Page 1 unprocessed` and `Page 2 processed` in Google Sheets
- Displays raw submissions with red map markers
- Displays processed/pending records with green map markers
- Clearly marks missing-GPS photos as not mappable
- YOLO is intentionally a future integration: this starter records `Pending YOLO Processing`; it does not claim to detect trash or damage yet.

## Architecture

- `frontend/` — static site hosted by GitHub Pages
- `backend/` — FastAPI service hosted separately (for example, Render)
- Google Sheets and Google Drive — storage
- Leaflet + OpenStreetMap — maps

**Important:** GitHub Pages cannot run Python server code. The frontend is hosted on GitHub Pages; the Python API must run on a Python hosting service.

## 1. Configure Google

1. Create or select a Google Cloud project.
2. Enable **Google Sheets API** and **Google Drive API**.
3. Create a service account and download its JSON key.
4. Share the target spreadsheet with the service account's email address as an Editor.
5. If using an existing Drive folder, share that folder with the service account as an Editor. Otherwise the service account can create a folder in its own Drive space.
6. Find the spreadsheet ID in its URL:
   `https://docs.google.com/spreadsheets/d/SPREADSHEET_ID/edit`
7. Keep the JSON key private. Never commit it to GitHub.

The app uses these worksheet names:
- `Page 1 unprocessed`
- `Page 2 processed`

It creates either worksheet if missing and writes a header row if the sheet is empty.

## 2. Configure and run the Python backend locally

Python 3.11 or newer is recommended.

```bash
cd backend
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

pip install -r requirements.txt
```

Set environment variables. The simplest method is to create `backend/.env` using `.env.example` as a guide. **Do not commit `.env`.**

`GOOGLE_SERVICE_ACCOUNT_JSON` must contain the entire service-account JSON as a single-line JSON string. `GOOGLE_SPREADSHEET_ID` is the ID from your spreadsheet URL.

```bash
uvicorn main:app --reload
```

API docs: `http://127.0.0.1:8000/docs`

## 3. Configure the frontend

Edit `frontend/config.js` and set `API_BASE_URL` to your backend URL, for example:

```js
window.APP_CONFIG = {
  API_BASE_URL: "https://YOUR-SERVICE.onrender.com"
};
```

For local testing, use `http://127.0.0.1:8000`.

## 4. Publish the frontend on GitHub Pages

1. Create a GitHub repository, for example `trash-mapping-portal`.
2. Upload the **contents** of `frontend/` to the repository root, or change the Pages publishing folder to `/frontend` if you commit the complete project.
3. In GitHub, open **Settings → Pages**.
4. Select **Deploy from a branch**, choose `main`, and select `/ (root)` (if frontend files are in the repository root).
5. Save. GitHub will provide the public website URL.

Do not put backend credentials or the Python backend's `.env` file in the public Pages repository.

## 5. Deploy the backend

A simple option is Render:
1. Push the project to GitHub.
2. Create a new Render **Web Service** from the repository.
3. Set the root directory to `backend`.
4. Build command: `pip install -r requirements.txt`
5. Start command: `uvicorn main:app --host 0.0.0.0 --port $PORT`
6. Add the environment variables from `.env.example` in the Render dashboard.
7. Set `CORS_ORIGINS` to your exact GitHub Pages origin, such as `https://YOUR-USERNAME.github.io`. If using a project site with a path, the origin still ends at `.io`.

The free hosting tier may sleep when idle and can have cold-start delays.

## Data columns

`Page 1 unprocessed`:
1. Upload date
2. Latitude
3. Longitude
4. Image URL
5. Status
6. File size (MB)
7. Width
8. Height
9. Camera
10. ISO
11. Exposure
12. Original capture date

`Page 2 processed`:
1. Upload date
2. Latitude
3. Longitude
4. Image URL
5. Processing status
6. File size (MB)
7. Width
8. Height
9. Camera
10. ISO
11. Exposure
12. Original capture date
13. Processed date
14. Detection results (reserved for future YOLO integration)

This makes the image URL column consistent between both worksheets.

## Public-upload security and privacy

This is a public upload endpoint. Before promoting the site widely:
- Set a reasonable maximum file size and batch size (already configured in the backend).
- Review the allowed CORS origin.
- Consider adding CAPTCHA, stronger per-IP rate limiting, moderation, and abuse monitoring.
- The current implementation sets uploaded Drive files to **Anyone with the link: Viewer** so map popups can display them. This means anyone who obtains a file link can view the image. Do not use this setting for sensitive photos.
- Do not store API keys, service-account JSON, or other secrets in frontend files or GitHub.
- Public uploads can incur Google Drive/API and hosting usage. Monitor quotas and billing.

## GPS notes

The analyzer reads GPS from EXIF tags in the original image. Many social-media apps strip EXIF metadata. Screenshots and edited/compressed copies may also lack GPS. Such photos are still stored in the spreadsheet and Drive but are not placed on the map unless GPS is added or verified later.

Coordinates from image metadata are not guaranteed to be correct. The website labels them as photo EXIF coordinates and does not silently substitute the uploader's current location.

## YOLO is a later phase

No YOLO model or training data has been supplied yet. The current app stores the record as pending. When you are ready, we can add a model, define trash/damage classes, confidence thresholds, and a review workflow before displaying detections.

## Existing code compatibility

This project replaces `google.script.run`, `SpreadsheetApp`, `DriveApp`, and `HtmlService` with a FastAPI backend. Your old Google Apps Script is not run by GitHub Pages. The original two worksheet names and the raw/processed map concept are retained.

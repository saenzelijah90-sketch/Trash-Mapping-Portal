from datetime import datetime
from io import BytesIO
from PIL import Image, ExifTags

# Pillow exposes EXIF tag IDs by name. GPS values are rationals (degrees/minutes/seconds).

def _as_float(value):
    try:
        return float(value)
    except (TypeError, ValueError, ZeroDivisionError):
        try:
            return float(value.numerator) / float(value.denominator)
        except Exception:
            return None


def _dms_to_decimal(value, ref):
    if not value or len(value) < 3:
        return None
    degrees = _as_float(value[0])
    minutes = _as_float(value[1])
    seconds = _as_float(value[2])
    if None in (degrees, minutes, seconds):
        return None
    result = degrees + minutes / 60 + seconds / 3600
    if str(ref).upper() in ("S", "W"):
        result = -result
    return result


def analyze_photo(image_bytes: bytes) -> dict:
    result = {
        "latitude": None,
        "longitude": None,
        "camera": "Unknown",
        "iso": "Unknown",
        "exposure": "Unknown",
        "original_date": "Unknown",
        "width": None,
        "height": None,
        "file_size_mb": round(len(image_bytes) / (1024 * 1024), 2),
    }

    with Image.open(BytesIO(image_bytes)) as image:
        result["width"], result["height"] = image.size
        exif = image.getexif()
        named = {ExifTags.TAGS.get(tag_id, tag_id): value for tag_id, value in exif.items()}

        make = str(named.get("Make", "")).strip()
        model = str(named.get("Model", "")).strip()
        result["camera"] = " ".join(part for part in (make, model) if part) or "Unknown"

        iso = named.get("ISOSpeedRatings", named.get("PhotographicSensitivity"))
        if iso is not None:
            result["iso"] = str(iso)

        exposure = named.get("ExposureTime")
        if exposure is not None:
            result["exposure"] = str(exposure)

        date_value = named.get("DateTimeOriginal") or named.get("DateTimeDigitized") or named.get("DateTime")
        if date_value:
            result["original_date"] = str(date_value)

        gps_ifd = {}
        try:
            gps_ifd = exif.get_ifd(ExifTags.IFD.GPSInfo)
        except Exception:
            # Older Pillow versions / malformed EXIF: no GPS information available.
            gps_ifd = {}

        gps = {ExifTags.GPSTAGS.get(tag_id, tag_id): value for tag_id, value in gps_ifd.items()}
        result["latitude"] = _dms_to_decimal(gps.get("GPSLatitude"), gps.get("GPSLatitudeRef"))
        result["longitude"] = _dms_to_decimal(gps.get("GPSLongitude"), gps.get("GPSLongitudeRef"))

    return result

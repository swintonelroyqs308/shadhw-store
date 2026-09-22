import json
import os
import subprocess
import time
import requests

from googleapiclient.http import MediaFileUpload
from test_drive import get_drive_service


# =========================================================
# CONFIG
# =========================================================

INSTAGRAM = "@shadhw.jewels"
PHONE = "0630000552"

FFMPEG = os.environ.get(
    "FFMPEG_PATH",
    r"C:\Users\العسل\Downloads\ffmpeg-9.0.2-essentials_build\bin\ffmpeg.exe"
)

PRODUCTS_FILE = "products.json"
STATE_FILE = "processed_videos.json"

DRIVE_FOLDER_NAME = "shadhw"

FONT = "C\\:/Windows/Fonts/arial.ttf"

# جودة الفيديو
CRF = "18"
PRESET = "slow"

# لون الكتابة
TEXT_OPACITY = "0.78"

# حجم الكتابة
FONT_SIZE = "h*0.040"

# المسافة بين "درهم" والثمن
PRICE_GAP = 5


# =========================================================
# LOAD PRODUCTS
# =========================================================

with open(PRODUCTS_FILE, "r", encoding="utf-8") as f:
    products = json.load(f)

print(f"\nعدد المنتجات: {len(products)}")


# =========================================================
# LOAD STATE
# =========================================================

if os.path.exists(STATE_FILE):
    with open(STATE_FILE, "r", encoding="utf-8") as f:
        processed = json.load(f)
else:
    processed = {}

print(f"الفيديوهات المسجلة كمكتملة: {len(processed)}")


# =========================================================
# SAVE STATE
# =========================================================

def save_state():
    temp_file = STATE_FILE + ".tmp"

    with open(temp_file, "w", encoding="utf-8") as f:
        json.dump(
            processed,
            f,
            ensure_ascii=False,
            indent=2
        )

    os.replace(temp_file, STATE_FILE)


# =========================================================
# DRIVE FOLDER
# =========================================================

def get_shadhw_folder(service):

    query = (
        "name = 'shadhw' "
        "and mimeType = 'application/vnd.google-apps.folder' "
        "and trashed = false"
    )

    results = service.files().list(
        q=query,
        spaces="drive",
        fields="files(id,name)",
        pageSize=10
    ).execute()

    folders = results.get("files", [])

    if folders:
        print(f"\nمجلد Drive موجود: {DRIVE_FOLDER_NAME}")
        return folders[0]["id"]

    metadata = {
        "name": DRIVE_FOLDER_NAME,
        "mimeType": "application/vnd.google-apps.folder"
    }

    folder = service.files().create(
        body=metadata,
        fields="id,name"
    ).execute()

    print(f"\nتم إنشاء مجلد Drive: {DRIVE_FOLDER_NAME}")

    return folder["id"]


# =========================================================
# DOWNLOAD
# =========================================================

def download_video(url, filename):

    print("Downloading...")

    response = requests.get(
        url,
        stream=True,
        timeout=180
    )

    response.raise_for_status()

    with open(filename, "wb") as f:
        for chunk in response.iter_content(chunk_size=1024 * 1024):
            if chunk:
                f.write(chunk)

    print("Download complete.")


# =========================================================
# WATERMARK
# =========================================================

def process_video(input_file, output_file, price):

    print("Processing video...")

    # كلمة درهم مستقلة حتى تبقى على يسار الرقم
    # ونرفعها قليلاً حتى تكون بمحاذاة الرقم
    filter_complex = (
        # درهم
        "drawtext="
        f"fontfile='{FONT}':"
        "text='درهم':"
        "text_shaping=1:"
        f"fontcolor=white@{TEXT_OPACITY}:"
        f"fontsize={FONT_SIZE}:"
        f"x=(w/2)-text_w-5:"
        "y=(h-text_h)/2-54,"

        # الرقم
        "drawtext="
        f"fontfile='{FONT}':"
        f"text='{price}':"
        f"fontcolor=white@{TEXT_OPACITY}:"
        f"fontsize={FONT_SIZE}:"
        "x=(w/2)+5:"
        "y=(h-text_h)/2-60,"

        # Instagram
        "drawtext="
        f"fontfile='{FONT}':"
        f"text='{INSTAGRAM}':"
        f"fontcolor=white@{TEXT_OPACITY}:"
        f"fontsize={FONT_SIZE}:"
        "x=(w-text_w)/2:"
        "y=(h-text_h)/2,"

        # Phone
        "drawtext="
        f"fontfile='{FONT}':"
        f"text='{PHONE}':"
        f"fontcolor=white@{TEXT_OPACITY}:"
        f"fontsize={FONT_SIZE}:"
        "x=(w-text_w)/2:"
        "y=(h-text_h)/2+60"
    )

    command = [
        FFMPEG,
        "-y",
        "-i", input_file,

        "-vf", filter_complex,

        "-c:v", "libx264",
        "-preset", PRESET,
        "-crf", CRF,

        "-c:a", "aac",
        "-b:a", "192k",

        "-movflags", "+faststart",

        output_file
    ]

    subprocess.run(
        command,
        check=True
    )

    print("Processing complete.")


# =========================================================
# UPLOAD
# =========================================================

def upload_video(service, folder_id, output_file):

    print("Uploading to Google Drive...")

    metadata = {
        "name": os.path.basename(output_file),
        "parents": [folder_id]
    }

    media = MediaFileUpload(
        output_file,
        mimetype="video/mp4",
        resumable=True
    )

    uploaded = service.files().create(
        body=metadata,
        media_body=media,
        fields="id,name"
    ).execute()

    del media

    print(f"Uploaded: {uploaded['name']}")

    return uploaded


# =========================================================
# DELETE TEMP FILE
# =========================================================

def delete_file(filename):

    if not os.path.exists(filename):
        return

    for attempt in range(5):

        try:
            os.remove(filename)
            return

        except PermissionError:

            if attempt < 4:
                time.sleep(2)

    print(f"Warning: لم يتم حذف الملف المؤقت: {filename}")


# =========================================================
# MAIN
# =========================================================

service = get_drive_service()

folder_id = get_shadhw_folder(service)

print("\n========================================")
print("SHADHW VIDEO PROCESSOR")
print("========================================")


total_videos = 0
completed_now = 0
skipped = 0
failed = 0


for product in products:

    product_id = product.get("id")
    price = product.get("price")
    videos = product.get("videos") or []

    if not product_id:
        continue

    if not videos:
        continue

    print("\n----------------------------------------")
    print(f"Product: {product_id}")
    print(f"Price: {price}")
    print(f"Videos: {len(videos)}")
    print("----------------------------------------")

    for video_index, video_url in enumerate(videos, start=1):

        total_videos += 1

        # كل فيديو له ID خاص في ملف الحالة
        video_key = f"{product_id}_video_{video_index}"

        # اسم الملف النهائي
        if len(videos) == 1:
            output_name = f"{product_id}-{price}.mp4"
        else:
            output_name = f"{product_id}-{price}-{video_index}.mp4"

        input_file = f"temp_{video_key}.mp4"
        output_file = output_name

        # -----------------------------------------
        # SKIP COMPLETED
        # -----------------------------------------

        if processed.get(video_key, {}).get("status") == "completed":

            print(f"\nSKIP: {video_key}")
            print("هذا الفيديو تمت معالجته سابقًا.")

            skipped += 1
            continue

        print(f"\nProcessing: {video_key}")
        print(f"URL: {video_url}")

        try:

            # -------------------------------------
            # DOWNLOAD
            # -------------------------------------

            processed[video_key] = {
                "product_id": product_id,
                "video_index": video_index,
                "price": price,
                "status": "processing"
            }

            save_state()

            download_video(
                video_url,
                input_file
            )

            # -------------------------------------
            # PROCESS
            # -------------------------------------

            process_video(
                input_file,
                output_file,
                price
            )

            # -------------------------------------
            # UPLOAD
            # -------------------------------------

            uploaded = upload_video(
                service,
                folder_id,
                output_file
            )

            # -------------------------------------
            # MARK COMPLETED
            # -------------------------------------

            processed[video_key] = {
                "product_id": product_id,
                "video_index": video_index,
                "price": price,
                "filename": output_name,
                "drive_id": uploaded["id"],
                "status": "completed"
            }

            save_state()

            completed_now += 1

            print("SUCCESS")

        except Exception as e:

            failed += 1

            processed[video_key] = {
                "product_id": product_id,
                "video_index": video_index,
                "price": price,
                "filename": output_name,
                "status": "failed",
                "error": str(e)
            }

            save_state()

            print("\nERROR")
            print(str(e))

        finally:

            # حذف الأصل المؤقت
            delete_file(input_file)

            # حذف الفيديو النهائي المحلي بعد الرفع
            delete_file(output_file)


# =========================================================
# FINAL REPORT
# =========================================================

print("\n========================================")
print("FINISHED")
print("========================================")

print(f"إجمالي الفيديوهات: {total_videos}")
print(f"تمت معالجتها الآن: {completed_now}")
print(f"تم تخطيها: {skipped}")
print(f"فشلت: {failed}")

print("\nالملفات النهائية موجودة في Google Drive:")
print("shadhw")

print("\nحالة المعالجة محفوظة في:")
print("processed_videos.json")

print("========================================")

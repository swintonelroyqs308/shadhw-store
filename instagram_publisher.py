import json
import os
import time

import requests

from test_drive import get_drive_service
from googleapiclient.http import MediaIoBaseDownload
from io import FileIO


# =========================================================
# CONFIG
# =========================================================

INSTAGRAM_USER_ID = "17841424496835585"

INSTAGRAM_ACCESS_TOKEN = os.environ.get("INSTAGRAM_ACCESS_TOKEN")
POSTFILE_API_KEY = os.environ.get("POSTFILE_API_KEY")

PRODUCTS_FILE = "products.json"
PROCESSING_STATE_FILE = "processed_videos.json"
PUBLISHED_STATE_FILE = "published_videos.json"

# أول تجربة: فيديو واحد فقط
MAX_PUBLISH = 1

POSTFILE_UPLOAD_URL = "https://postfile.net/v1/upload"

INSTAGRAM_MEDIA_URL = (
    f"https://graph.instagram.com/{INSTAGRAM_USER_ID}/media"
)

INSTAGRAM_PUBLISH_URL = (
    f"https://graph.instagram.com/{INSTAGRAM_USER_ID}/media_publish"
)


# =========================================================
# CHECK SECRETS
# =========================================================

if not INSTAGRAM_ACCESS_TOKEN:
    raise RuntimeError("INSTAGRAM_ACCESS_TOKEN غير موجود في GitHub Secrets.")

if not POSTFILE_API_KEY:
    raise RuntimeError("POSTFILE_API_KEY غير موجود في GitHub Secrets.")


# =========================================================
# LOAD JSON
# =========================================================

with open(PROCESSING_STATE_FILE, "r", encoding="utf-8") as f:
    processed = json.load(f)


if os.path.exists(PUBLISHED_STATE_FILE):

    with open(PUBLISHED_STATE_FILE, "r", encoding="utf-8") as f:
        published = json.load(f)

else:
    published = {}


# =========================================================
# SAVE PUBLISHED STATE
# =========================================================

def save_published_state():

    temp_file = PUBLISHED_STATE_FILE + ".tmp"

    with open(temp_file, "w", encoding="utf-8") as f:

        json.dump(
            published,
            f,
            ensure_ascii=False,
            indent=2
        )

    os.replace(
        temp_file,
        PUBLISHED_STATE_FILE
    )


# =========================================================
# LOAD PRODUCTS
# =========================================================

with open(PRODUCTS_FILE, "r", encoding="utf-8") as f:
    products = json.load(f)


products_by_id = {
    product.get("id"): product
    for product in products
    if product.get("id")
}


# =========================================================
# GOOGLE DRIVE
# =========================================================

service = get_drive_service()


def download_from_drive(drive_id, filename):

    print(f"Downloading from Google Drive: {drive_id}")

    request = service.files().get_media(
        fileId=drive_id
    )

    with FileIO(filename, "wb") as fh:

        downloader = MediaIoBaseDownload(
            fh,
            request
        )

        done = False

        while not done:

            status, done = downloader.next_chunk()

            if status:
                print(
                    f"Drive download: "
                    f"{int(status.progress() * 100)}%"
                )

    print("Drive download complete.")


# =========================================================
# POSTFILE
# =========================================================

def upload_to_postfile(filename):

    print("Uploading to PostFile...")

    file_size = os.path.getsize(filename)

    print(
        f"File size: "
        f"{file_size / (1024 * 1024):.2f} MB"
    )

    # Free plan limit
    if file_size > 50 * 1024 * 1024:

        raise RuntimeError(
            f"الفيديو أكبر من 50MB: {filename}"
        )

    headers = {
        "X-API-Key": POSTFILE_API_KEY
    }

    with open(filename, "rb") as video_file:

        response = requests.post(
            POSTFILE_UPLOAD_URL,
            headers=headers,
            files={
                "file": (
                    os.path.basename(filename),
                    video_file,
                    "video/mp4"
                )
            },
            timeout=300
        )

    if not response.ok:

        raise RuntimeError(
            "PostFile upload failed: "
            f"{response.status_code} "
            f"{response.text}"
        )

    data = response.json()

    url = data.get("url")
    file_id = data.get("file_id")

    if not url:

        raise RuntimeError(
            f"PostFile لم يرجع URL: {data}"
        )

    print(f"PostFile URL: {url}")

    return {
        "url": url,
        "file_id": file_id
    }


# =========================================================
# INSTAGRAM CONTAINER
# =========================================================

def create_instagram_container(video_url, caption):

    print("Creating Instagram Reel container...")

    data = {
        "media_type": "REELS",
        "video_url": video_url,
        "caption": caption,
        "access_token": INSTAGRAM_ACCESS_TOKEN
    }

    response = requests.post(
        INSTAGRAM_MEDIA_URL,
        data=data,
        timeout=120
    )

    if not response.ok:

        raise RuntimeError(
            "Instagram container failed: "
            f"{response.status_code} "
            f"{response.text}"
        )

    result = response.json()

    creation_id = result.get("id")

    if not creation_id:

        raise RuntimeError(
            f"Instagram لم يرجع creation ID: {result}"
        )

    print(f"Creation ID: {creation_id}")

    return creation_id


# =========================================================
# WAIT FOR CONTAINER
# =========================================================

def wait_for_container(creation_id):

    print("Waiting for Instagram processing...")

    url = (
        f"https://graph.instagram.com/"
        f"{creation_id}"
    )

    for attempt in range(30):

        response = requests.get(
            url,
            params={
                "fields": "id,status_code,status",
                "access_token": INSTAGRAM_ACCESS_TOKEN
            },
            timeout=60
        )

        if not response.ok:

            raise RuntimeError(
                "Instagram status request failed: "
                f"{response.status_code} "
                f"{response.text}"
            )

        data = response.json()

        status_code = data.get("status_code")
        status = data.get("status")

        print(
            f"Attempt {attempt + 1}: "
            f"{status_code} / {status}"
        )

        if status_code == "FINISHED":

            print("Instagram container FINISHED.")

            return data

        if status_code in (
            "ERROR",
            "EXPIRED"
        ):

            raise RuntimeError(
                f"Instagram container failed: {data}"
            )

        time.sleep(10)

    raise RuntimeError(
        "Instagram container لم يصل إلى FINISHED خلال الوقت المحدد."
    )


# =========================================================
# PUBLISH
# =========================================================

def publish_container(creation_id):

    print("Publishing Reel...")

    response = requests.post(
        INSTAGRAM_PUBLISH_URL,
        data={
            "creation_id": creation_id,
            "access_token": INSTAGRAM_ACCESS_TOKEN
        },
        timeout=120
    )

    if not response.ok:

        raise RuntimeError(
            "Instagram publish failed: "
            f"{response.status_code} "
            f"{response.text}"
        )

    data = response.json()

    media_id = data.get("id")

    if not media_id:

        raise RuntimeError(
            f"Instagram لم يرجع media ID: {data}"
        )

    print(
        f"Published successfully: {media_id}"
    )

    return media_id


# =========================================================
# CAPTION
# =========================================================

def make_caption(data):

    source_id = data.get("source_id", "")
    
    return (
        f"{source_id}\n\n"
        "✨ شَذْو للمجوهرات ✨\n\n"
        "🛍️ اكتشفي المجموعة كاملة من الرابط في Bio\n"
        "📲 للطلب والاستفسار عبر وتساب:\n\n"
        "0630000552\n\n"
        "🚚 التوصيل لجميع المدن المغربية\n"
        "💵 والدفع عند الاستلام"
    )


# =========================================================
# MAIN
# =========================================================

print()
print("========================================")
print("SHADHW INSTAGRAM PUBLISHER")
print("========================================")

candidates = []

for video_key, data in processed.items():

    if data.get("status") != "completed":
        continue

    if video_key in published:
        continue

   # if video_key in published and published[video_key].get("status") == "published":
   #     continue

    drive_id = data.get("drive_id")

    if not drive_id:
        print(
            f"SKIP {video_key}: "
            "لا يوجد drive_id"
        )
        continue

    candidates.append(
        (video_key, data)
    )


print(
    f"Videos ready for publishing: "
    f"{len(candidates)}"
)


published_now = 0
failed = 0


for video_key, data in candidates:

    if published_now >= MAX_PUBLISH:
        break

    product_id = data.get("product_id")
    drive_id = data.get("drive_id")
    filename = data.get("filename")

    product = products_by_id.get(
        product_id,
        {}
    )

    temp_file = f"publish_{video_key}.mp4"

    print()
    print("----------------------------------------")
    print(f"Video: {video_key}")
    print(f"Drive ID: {drive_id}")
    print(f"Filename: {filename}")
    print("----------------------------------------")

    try:

        # -------------------------------------
        # DOWNLOAD FROM DRIVE
        # -------------------------------------

        download_from_drive(
            drive_id,
            temp_file
        )

        # -------------------------------------
        # UPLOAD TO POSTFILE
        # -------------------------------------

        postfile = upload_to_postfile(
            temp_file
        )

        # -------------------------------------
        # CREATE INSTAGRAM CONTAINER
        # -------------------------------------

        caption = make_caption(
            data
        )

        creation_id = create_instagram_container(
            postfile["url"],
            caption
        )

        # -------------------------------------
        # WAIT
        # -------------------------------------

        wait_for_container(
            creation_id
        )

        # -------------------------------------
        # PUBLISH
        # -------------------------------------

        media_id = publish_container(
            creation_id
        )

        # -------------------------------------
        # SAVE STATE
        # -------------------------------------

        published[video_key] = {
            "product_id": product_id,
            "source_id": data.get("source_id"),
            "video_index": data.get("video_index"),
            "price": data.get("price"),
            "filename": filename,
            "drive_id": drive_id,
            "postfile_id": postfile["file_id"],
            "postfile_url": postfile["url"],
            "instagram_creation_id": creation_id,
            "instagram_media_id": media_id,
            "status": "published"
        }

        save_published_state()

        published_now += 1

        print()
        print("SUCCESS")
        print(
            f"Instagram Media ID: {media_id}"
        )

    except Exception as e:

        failed += 1

        published[video_key] = {
            "product_id": product_id,
            "source_id": data.get("source_id"),
            "video_index": data.get("video_index"),
            "price": data.get("price"),
            "filename": filename,
            "drive_id": drive_id,
            "status": "failed",
            "error": str(e)
        }

        save_published_state()

        print()
        print("ERROR")
        print(str(e))

    finally:

        if os.path.exists(temp_file):

            try:
                os.remove(temp_file)

            except Exception as e:

                print(
                    f"Warning: لم يتم حذف "
                    f"{temp_file}: {e}"
                )


print()
print("========================================")
print("PUBLISHER FINISHED")
print("========================================")
print(f"تم النشر الآن: {published_now}")
print(f"فشل: {failed}")
print("========================================")

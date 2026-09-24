import json
import os
import subprocess
import time
import requests
import zlib
import struct
import math
import re

from googleapiclient.http import MediaFileUpload
from test_drive import get_drive_service


# =========================================================
# CONFIG
# =========================================================

PHONE = "0630 000 552"

FFMPEG = os.environ.get(
    "FFMPEG_PATH",
    r"C:\Users\العسل\Downloads\ffmpeg-9.0.2-essentials_build\ffmpeg.exe"
)

PRODUCTS_FILE = "products.json"
STATE_FILE = "processed_videos.json"

DRIVE_FOLDER_NAME = "shadhw"

LOGO = "logo.png"
WHATSAPP = "whatsapp.png"

# خط يدعم العربية
FONT = "C\\:/Windows/Fonts/arial.ttf"

# جودة الفيديو
CRF = "18"
PRESET = "slow"

# شفافية اللوغو و WhatsApp
LOGO_ALPHA = 0.65
WHATSAPP_ALPHA = 0.35


# =========================================================
# LOAD PRODUCTS
# =========================================================

with open(
    PRODUCTS_FILE,
    "r",
    encoding="utf-8"
) as f:

    products = json.load(f)

print(
    f"\nعدد المنتجات: {len(products)}"
)


# =========================================================
# LOAD STATE
# =========================================================

if os.path.exists(STATE_FILE):

    with open(
        STATE_FILE,
        "r",
        encoding="utf-8"
    ) as f:

        processed = json.load(f)

else:

    processed = {}

print(
    f"الفيديوهات المسجلة كمكتملة: {len(processed)}"
)


# =========================================================
# SAVE STATE
# =========================================================

def save_state():

    temp_file = STATE_FILE + ".tmp"

    with open(
        temp_file,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            processed,
            f,
            ensure_ascii=False,
            indent=2
        )

    os.replace(
        temp_file,
        STATE_FILE
    )


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

    folders = results.get(
        "files",
        []
    )

    if folders:

        print(
            f"\nمجلد Drive موجود: {DRIVE_FOLDER_NAME}"
        )

        return folders[0]["id"]

    metadata = {
        "name": DRIVE_FOLDER_NAME,
        "mimeType": "application/vnd.google-apps.folder"
    }

    folder = service.files().create(
        body=metadata,
        fields="id,name"
    ).execute()

    print(
        f"\nتم إنشاء مجلد Drive: {DRIVE_FOLDER_NAME}"
    )

    return folder["id"]


# =========================================================
# DOWNLOAD
# =========================================================

def download_video(
    url,
    filename
):

    print(
        "Downloading..."
    )

    response = requests.get(
        url,
        stream=True,
        timeout=180
    )

    response.raise_for_status()

    with open(
        filename,
        "wb"
    ) as f:

        for chunk in response.iter_content(
            chunk_size=1024 * 1024
        ):

            if chunk:
                f.write(chunk)

    print(
        "Download complete."
    )


# =========================================================
# PNG WRITER
# =========================================================

def save_png(
    filename,
    width,
    height,
    pixels
):

    raw = bytearray()

    for y in range(height):

        raw.append(0)

        for x in range(width):

            r, g, b, a = pixels[
                y * width + x
            ]

            raw.extend([
                r & 255,
                g & 255,
                b & 255,
                a & 255
            ])

    def chunk(
        chunk_type,
        data
    ):

        return (
            struct.pack(
                ">I",
                len(data)
            )
            + chunk_type
            + data
            + struct.pack(
                ">I",
                zlib.crc32(
                    chunk_type + data
                ) & 0xffffffff
            )
        )

    png = (
        b"\x89PNG\r\n\x1a\n"
    )

    png += chunk(
        b"IHDR",
        struct.pack(
            ">IIBBBBB",
            width,
            height,
            8,
            6,
            0,
            0,
            0
        )
    )

    png += chunk(
        b"IDAT",
        zlib.compress(
            bytes(raw),
            9
        )
    )

    png += chunk(
        b"IEND",
        b""
    )

    with open(
        filename,
        "wb"
    ) as f:

        f.write(png)


# =========================================================
# CREATE YELLOW SALE BURST
# =========================================================

def create_boom_frame(
    filename
):

    width = 250
    height = 250

    cx = width / 2
    cy = height / 2

    YELLOW = (
        255,
        215,
        0
    )

    spikes = 16

    outer_x = 108
    outer_y = 92

    inner_x = 76
    inner_y = 63

    polygon = []

    for i in range(
        spikes * 2
    ):

        angle = (
            -math.pi / 2
            + (
                i
                * math.pi
                / spikes
            )
        )

        if i % 2 == 0:

            radius_x = outer_x
            radius_y = outer_y

        else:

            radius_x = inner_x
            radius_y = inner_y

        x = (
            cx
            + math.cos(angle)
            * radius_x
        )

        y = (
            cy
            + math.sin(angle)
            * radius_y
        )

        polygon.append(
            (x, y)
        )

    def point_in_polygon(
        px,
        py,
        points
    ):

        inside = False
        j = len(points) - 1

        for i in range(
            len(points)
        ):

            xi, yi = points[i]
            xj, yj = points[j]

            if (
                (yi > py)
                !=
                (yj > py)
            ):

                intersection = (
                    (xj - xi)
                    * (py - yi)
                    / (
                        (yj - yi)
                        + 1e-12
                    )
                    + xi
                )

                if px < intersection:

                    inside = not inside

            j = i

        return inside

    pixels = []

    for y in range(height):

        for x in range(width):

            if point_in_polygon(
                x + 0.5,
                y + 0.5,
                polygon
            ):

                pixels.append(
                    (
                        YELLOW[0],
                        YELLOW[1],
                        YELLOW[2],
                        255
                    )
                )

            else:

                pixels.append(
                    (
                        0,
                        0,
                        0,
                        0
                    )
                )

    save_png(
        filename,
        width,
        height,
        pixels
    )


# =========================================================
# GET VIDEO DURATION
# =========================================================

def get_video_duration(
    input_file
):

    command = [
        FFMPEG,
        "-i",
        input_file
    ]

    result = subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="ignore"
    )

    output = result.stderr

    match = re.search(
        r"Duration:\s*(\d+):(\d+):([\d.]+)",
        output
    )

    if not match:

        raise RuntimeError(
            "Could not determine video duration."
        )

    hours = int(
        match.group(1)
    )

    minutes = int(
        match.group(2)
    )

    seconds = float(
        match.group(3)
    )

    return (
        hours * 3600
        + minutes * 60
        + seconds
    )


# =========================================================
# PROCESS VIDEO
# =========================================================

def process_video(
    input_file,
    output_file,
    price
):

    print(
        "Processing video..."
    )

    burst_file = (
        f"temp_sale_burst_{os.getpid()}.png"
    )

    try:

        create_boom_frame(
            burst_file
        )

        duration = get_video_duration(
            input_file
        )

        print(
            f"Video duration: {duration:.2f} seconds"
        )


        # =================================================
        # LOGO
        # =================================================

        logo_filter = (
            "[1:v]"
            "scale=105:-1,"
            "format=rgba,"
            f"colorchannelmixer=aa={LOGO_ALPHA}"
            "[logo]"
        )


        # =================================================
        # WHATSAPP
        # =================================================

        whatsapp_filter = (
            "[2:v]"
            "scale=38:38,"
            "format=rgba,"
            f"colorchannelmixer=aa={WHATSAPP_ALPHA}"
            "[wa]"
        )


        # =================================================
        # BURST
        # =================================================

        burst_filter = (
            "[3:v]"
            "scale=200:200"
            "[burst]"
        )


        # =================================================
        # LOGO OVERLAY
        # =================================================

        logo_overlay = (
            "[0:v][logo]"
            "overlay=x=W-w:y=0"
            "[v1]"
        )


        # =================================================
        # BURST OVERLAY
        # =================================================

        burst_overlay = (
            "[v1][burst]"
            "overlay=x=5:y=-10"
            "[v2]"
        )


        # =================================================
        # SALE TEXT
        # =================================================

        sale_text = (
            "drawtext="
            f"fontfile='{FONT}':"
            "text='عرض خاص':"
            "text_shaping=1:"
            "fontcolor=red:"
            "bordercolor=red:"
            "borderw=1:"
            "fontsize=25:"
            "x=40+(130-text_w)/2:"
            "y=52"
        )


        # =================================================
        # SECOND TEXT
        # =================================================

        second_text = (
            "drawtext="
            f"fontfile='{FONT}':"
            "text='فقط بـ':"
            "text_shaping=1:"
            "fontcolor=red:"
            "bordercolor=red:"
            "borderw=1:"
            "fontsize=24:"
            "x=40+(130-text_w)/2:"
            "y=80"
        )


        # =================================================
        # PRICE
        # =================================================

        price_number = (
            "drawtext="
            f"fontfile='{FONT}':"
            f"text='{price}':"
            "fontcolor=red:"
            "bordercolor=red:"
            "borderw=1:"
            "fontsize=30:"
            "x=110:"
            "y=105"
        )


        # =================================================
        # CURRENCY
        # =================================================

        currency_text = (
            "drawtext="
            f"fontfile='{FONT}':"
            "text='درهم':"
            "text_shaping=1:"
            "fontcolor=red:"
            "bordercolor=red:"
            "borderw=1:"
            "fontsize=25:"
            "x=65:"
            "y=110"
        )


        # =================================================
        # PHONE
        # =================================================

        phone_text = (
            "drawtext="
            f"fontfile='{FONT}':"
            f"text='{PHONE}':"
            "fontcolor=white:"
            "fontsize=28:"
            "x=(w-text_w)/2+25:"
            "y=(h-text_h)/2"
        )


        # =================================================
        # FILTER GRAPH
        # =================================================

        filter_complex = ";".join([

            logo_filter,

            whatsapp_filter,

            burst_filter,

            logo_overlay,

            burst_overlay,

            "[v2]"
            + sale_text
            + ","
            + second_text
            + ","
            + price_number
            + ","
            + currency_text
            + "[v3]",

            "[v3]"
            + phone_text
            + "[v4]",

            # WhatsApp + PHONE في نفس السطر
            "[v4][wa]"
            "overlay="
            "x=(W-w)/2-55:"
            "y=(H-h)/2-1"
            "[vout]"
        ])


        # =================================================
        # FFMPEG
        # =================================================

        command = [

            FFMPEG,

            "-y",

            "-i",
            input_file,

            "-i",
            LOGO,

            "-i",
            WHATSAPP,

            "-loop",
            "1",

            "-i",
            burst_file,

            "-filter_complex",
            filter_complex,

            "-map",
            "[vout]",

            "-map",
            "0:a?",

            "-t",
            str(duration),

            "-c:v",
            "libx264",

            "-preset",
            PRESET,

            "-crf",
            CRF,

            "-pix_fmt",
            "yuv420p",

            "-c:a",
            "aac",

            "-b:a",
            "192k",

            "-movflags",
            "+faststart",

            output_file
        ]

        subprocess.run(
            command,
            check=True
        )

        print(
            "Processing complete."
        )

    finally:

        delete_file(
            burst_file
        )


# =========================================================
# UPLOAD
# =========================================================

def upload_video(
    service,
    folder_id,
    output_file
):

    print(
        "Uploading to Google Drive..."
    )

    metadata = {
        "name": os.path.basename(
            output_file
        ),
        "parents": [
            folder_id
        ]
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

    print(
        f"Uploaded: {uploaded['name']}"
    )

    return uploaded


# =========================================================
# DELETE
# =========================================================

def delete_file(
    filename
):

    if not os.path.exists(
        filename
    ):

        return

    for attempt in range(5):

        try:

            os.remove(
                filename
            )

            return

        except PermissionError:

            if attempt < 4:

                time.sleep(2)

    print(
        f"Warning: لم يتم حذف الملف المؤقت: {filename}"
    )


# =========================================================
# MAIN
# =========================================================

service = get_drive_service()

folder_id = get_shadhw_folder(
    service
)

print()
print(
    "========================================"
)
print(
    "SHADHW VIDEO PROCESSOR"
)
print(
    "========================================"
)


total_videos = 0
completed_now = 0
skipped = 0
failed = 0


# =========================================================
# TEST MODE
# =========================================================

TEST_MODE = True
TEST_SOURCE_ID = "288"


for product in products:

    if (
        TEST_MODE
        and
        str(
            product.get("source_id")
        )
        != TEST_SOURCE_ID
    ):

        continue

    product_id = product.get(
        "id"
    )

    source_id = product.get(
        "source_id"
    )

    price = product.get(
        "price"
    )

    videos = product.get(
        "videos"
    ) or []


    if not product_id:

        continue


    if not source_id:

        print(
            f"SKIP: {product_id} — لا يوجد source_id"
        )

        continue


    if not videos:

        continue


    print()
    print(
        "----------------------------------------"
    )

    print(
        f"Product: {product_id}"
    )

    print(
        f"Source ID: {source_id}"
    )

    print(
        f"Price: {price}"
    )

    print(
        f"Videos: {len(videos)}"
    )

    print(
        "----------------------------------------"
    )


    for video_index, video_url in enumerate(
        videos,
        start=1
    ):

        total_videos += 1


        video_key = (
            f"{source_id}_video_{video_index}"
        )


        if len(videos) == 1:

            output_name = (
                f"{source_id}-{price}.mp4"
            )

        else:

            output_name = (
                f"{source_id}-{price}-{video_index}.mp4"
            )


        input_file = (
            f"temp_{video_key}.mp4"
        )

        output_file = (
            output_name
        )


        if (
            processed
            .get(video_key, {})
            .get("status")
            ==
            "completed"
        ):

            print()
            print(
                f"SKIP: {video_key}"
            )

            print(
                "هذا الفيديو تمت معالجته سابقًا."
            )

            skipped += 1

            continue


        print()
        print(
            f"Processing: {video_key}"
        )

        print(
            f"URL: {video_url}"
        )


        try:

            processed[video_key] = {

                "product_id":
                    product_id,

                "source_id":
                    source_id,

                "video_index":
                    video_index,

                "price":
                    price,

                "status":
                    "processing"
            }

            save_state()


            download_video(
                video_url,
                input_file
            )


            process_video(
                input_file,
                output_file,
                price
            )


            uploaded = upload_video(
                service,
                folder_id,
                output_file
            )


            processed[video_key] = {

                "product_id":
                    product_id,

                "source_id":
                    source_id,

                "video_index":
                    video_index,

                "price":
                    price,

                "filename":
                    output_name,

                "drive_id":
                    uploaded["id"],

                "status":
                    "completed"
            }

            save_state()

            completed_now += 1

            print(
                "SUCCESS"
            )


        except Exception as e:

            failed += 1

            processed[video_key] = {

                "product_id":
                    product_id,

                "source_id":
                    source_id,

                "video_index":
                    video_index,

                "price":
                    price,

                "filename":
                    output_name,

                "status":
                    "failed",

                "error":
                    str(e)
            }

            save_state()

            print()
            print(
                "ERROR"
            )

            print(
                str(e)
            )


        finally:

            delete_file(
                input_file
            )

            delete_file(
                output_file
            )


# =========================================================
# FINAL REPORT
# =========================================================

print()
print(
    "========================================"
)

print(
    "FINISHED"
)

print(
    "========================================"
)

print(
    f"إجمالي الفيديوهات: {total_videos}"
)

print(
    f"تمت معالجتها الآن: {completed_now}"
)

print(
    f"تم تخطيها: {skipped}"
)

print(
    f"فشلت: {failed}"
)

print()

print(
    "الملفات النهائية موجودة في Google Drive:"
)

print(
    "shadhw"
)

print()

print(
    "حالة المعالجة محفوظة في:"
)

print(
    "processed_videos.json"
)

print(
    "========================================"
)

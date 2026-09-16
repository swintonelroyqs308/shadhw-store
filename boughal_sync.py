import os
import json
import time
import re
from urllib.parse import urljoin

from playwright.sync_api import sync_playwright


# =========================================================
# CONFIG
# =========================================================

EMAIL = os.environ.get("BOUGHAL_EMAIL")
PASSWORD = os.environ.get("BOUGHAL_PASSWORD")

BASE_URL = "https://boughalaffiliate.com"
BASE_PRODUCTS_URL = f"{BASE_URL}/affiliate/products"

PROFIT_MARGIN = 100

MAX_EMPTY_PAGES = 2
MAX_PAGES = 1000


# =========================================================
# HELPERS
# =========================================================

def clean_text(value):
    if not value:
        return ""

    return " ".join(str(value).split()).strip()


def absolute_url(url):
    if not url:
        return ""

    url = str(url).strip()

    if not url:
        return ""

    if url.startswith("//"):
        return "https:" + url

    return urljoin(BASE_URL, url)


def normalize_url(url):
    if not url:
        return ""

    return absolute_url(url).strip()


def extract_number(text):
    if not text:
        return None

    text = str(text).replace(",", ".")

    match = re.search(
        r"(\d+(?:\.\d+)?)",
        text
    )

    if not match:
        return None

    try:
        return float(match.group(1))
    except Exception:
        return None


# =========================================================
# PRICE
# =========================================================

def extract_price(text):

    if not text:
        return None

    text = clean_text(text)

    patterns = [

        r'(\d+(?:[.,]\d{1,2})?)\s*(?:DH|dh|MAD|mad)',

        r'(?:DH|dh|MAD|mad)\s*(\d+(?:[.,]\d{1,2})?)',

        r'(\d+(?:[.,]\d{1,2})?)\s*د\.?\s*م',

        r'(\d+(?:[.,]\d{1,2})?)\s*(?:درهم|درهما|درهمًا)'
    ]

    for pattern in patterns:

        match = re.search(
            pattern,
            text
        )

        if match:

            value = (
                match.group(1)
                .replace(",", ".")
            )

            try:
                return float(value)
            except Exception:
                pass

    return None


def format_price(value):

    if value is None:
        return ""

    try:

        value = float(value)

        if value.is_integer():
            return f"{int(value)} DH"

        return f"{value:.2f} DH"

    except Exception:

        return ""


def extract_revendeur_price(text):

    if not text:
        return None

    text = clean_text(text)

    patterns = [

        r"prix\s+revendeur\s*[:\-]?\s*"
        r"(\d+(?:[.,]\d{1,2})?)",

        r"revendeur\s*[:\-]?\s*"
        r"(\d+(?:[.,]\d{1,2})?)"
    ]

    for pattern in patterns:

        match = re.search(
            pattern,
            text,
            re.IGNORECASE
        )

        if match:

            try:

                return float(
                    match.group(1)
                    .replace(",", ".")
                )

            except Exception:
                pass

    # -----------------------------------------------------
    # البحث سطر بسطر
    # -----------------------------------------------------

    lines = [
        clean_text(line)
        for line in text.split("\n")
        if clean_text(line)
    ]

    for i, line in enumerate(lines):

        low = line.lower()

        if (
            "prix revendeur" in low
            or "revendeur" in low
        ):

            price = extract_price(line)

            if price is not None:
                return price

            if i + 1 < len(lines):

                price = extract_price(
                    lines[i + 1]
                )

                if price is not None:
                    return price

    return None


# =========================================================
# IMAGE HELPERS
# =========================================================

BLOCKED_IMAGE_WORDS = [
    "placeholder",
    "placehold",
    "unsplash.com",
    "default-image",
    "default_image",
    "no-image",
    "no_image",
    "noimage"
]


def is_valid_image(url):

    if not url:
        return False

    low = url.lower()

    if any(
        word in low
        for word in BLOCKED_IMAGE_WORDS
    ):
        return False

    return True


def get_image_candidates(img):

    candidates = []

    attributes = [
        "src",
        "data-src",
        "data-image",
        "data-original",
        "data-lazy-src",
        "data-lazy",
        "data-url",
        "data-original-src",
        "data-full",
        "data-large",
        "data-zoom-image"
    ]

    for attr in attributes:

        try:

            value = img.get_attribute(attr)

            if value:
                candidates.append(value)

        except Exception:
            pass

    # -----------------------------------------------------
    # srcset
    # -----------------------------------------------------

    try:

        srcset = img.get_attribute(
            "srcset"
        )

        if srcset:

            for part in srcset.split(","):

                part = part.strip()

                if not part:
                    continue

                url = part.split()[0].strip()

                if url:
                    candidates.append(url)

    except Exception:
        pass

    return candidates


def extract_image(img):

    if not img:
        return None

    candidates = get_image_candidates(
        img
    )

    for url in candidates:

        url = absolute_url(url)

        if is_valid_image(url):

            return url

    return None


# =========================================================
# ALL IMAGES
# =========================================================

def extract_all_images(page):

    results = []
    seen = set()

    # -----------------------------------------------------
    # نحاول Gallery الرئيسية أولاً
    # -----------------------------------------------------

    gallery_selectors = [

        ".product-main-slider img",

        ".product-gallery img",

        ".product-images img",

        ".swiper-slide img",

        "[class*='gallery'] img",

        "[class*='Gallery'] img"
    ]

    for selector in gallery_selectors:

        try:

            imgs = page.locator(
                selector
            ).all()

            if not imgs:
                continue

            local_results = []

            for img in imgs:

                url = extract_image(img)

                if not url:
                    continue

                if url not in local_results:

                    local_results.append(url)

            if local_results:

                for url in local_results:

                    if url not in seen:

                        seen.add(url)
                        results.append(url)

                # وجدنا Gallery حقيقية
                if len(results) > 0:
                    return results

        except Exception:
            pass

    # -----------------------------------------------------
    # fallback: كل الصور
    # -----------------------------------------------------

    try:

        imgs = page.locator(
            "img"
        ).all()

        for img in imgs:

            url = extract_image(img)

            if not url:
                continue

            if url not in seen:

                seen.add(url)
                results.append(url)

    except Exception:
        pass

    return results


# =========================================================
# VIDEOS
# =========================================================

def extract_all_videos(page):

    videos = []
    seen = set()

    # -----------------------------------------------------
    # video elements
    # -----------------------------------------------------

    try:

        video_elements = page.locator(
            "video"
        ).all()

        for video in video_elements:

            # video src
            try:

                src = video.get_attribute(
                    "src"
                )

                if src:

                    url = absolute_url(src)

                    if url and url not in seen:

                        seen.add(url)
                        videos.append(url)

            except Exception:
                pass

            # source داخل video
            try:

                sources = video.locator(
                    "source"
                ).all()

                for source in sources:

                    src = source.get_attribute(
                        "src"
                    )

                    if not src:
                        continue

                    url = absolute_url(src)

                    if url and url not in seen:

                        seen.add(url)
                        videos.append(url)

            except Exception:
                pass

    except Exception:
        pass

    # -----------------------------------------------------
    # fallback:
    # عناصر قد تحتوي data-video
    # -----------------------------------------------------

    if not videos:

        selectors = [
            "[data-video]",
            "[data-video-url]",
            "[data-src*='.mp4']",
            "[href*='.mp4']"
        ]

        for selector in selectors:

            try:

                elements = page.locator(
                    selector
                ).all()

                for element in elements:

                    for attr in [
                        "data-video",
                        "data-video-url",
                        "data-src",
                        "href"
                    ]:

                        try:

                            value = element.get_attribute(
                                attr
                            )

                            if not value:
                                continue

                            url = absolute_url(value)

                            if url and url not in seen:

                                seen.add(url)
                                videos.append(url)

                        except Exception:
                            pass

            except Exception:
                pass

    return videos


# =========================================================
# TITLE
# =========================================================

def find_title(
    container,
    fallback_text=""
):

    selectors = [

        "h1",
        "h2",
        "h3",

        ".product-title",
        "[class*='product-title']",
        "[class*='Product-title']",

        "[class*='title']",
        "[class*='Title']",

        "[class*='name']",
        "[class*='Name']",

        "[data-title]"
    ]

    for selector in selectors:

        try:

            elements = container.locator(
                selector
            ).all()

            for element in elements:

                try:

                    # data-title
                    data_title = element.get_attribute(
                        "data-title"
                    )

                    if data_title:

                        value = clean_text(
                            data_title
                        )

                        if (
                            len(value) >= 3
                            and extract_price(value) is None
                        ):
                            return value

                    text = clean_text(
                        element.inner_text()
                    )

                    if (
                        len(text) >= 3
                        and len(text) <= 250
                        and extract_price(text) is None
                    ):

                        return text

                except Exception:
                    pass

        except Exception:
            pass

    # -----------------------------------------------------
    # fallback text
    # -----------------------------------------------------

    lines = [
        clean_text(line)
        for line in fallback_text.split("\n")
        if clean_text(line)
    ]

    ignored_words = [

        "acheter",
        "ajouter",
        "commander",
        "voir",

        "stock",
        "rupture",
        "out of stock",
        "in stock",

        "disponible",
        "disponibilité",

        "prix",
        "revendeur",
        "dh",
        "mad"
    ]

    for line in lines:

        if len(line) < 3:
            continue

        if len(line) > 250:
            continue

        if extract_price(line) is not None:
            continue

        low = line.lower()

        if any(
            word in low
            for word in ignored_words
        ):
            continue

        return line

    return ""


# =========================================================
# DESCRIPTION
# =========================================================

def extract_description(page):

    candidates = []

    selectors = [

        "#description",

        ".description",

        "[data-description]",

        ".product-description",

        "[class*='product-description']",

        "[class*='description']",

        "[class*='Description']"
    ]

    for selector in selectors:

        try:

            elements = page.locator(
                selector
            ).all()

            for element in elements:

                try:

                    text = clean_text(
                        element.inner_text()
                    )

                    if len(text) < 10:
                        continue

                    candidates.append(
                        text
                    )

                except Exception:
                    pass

        except Exception:
            pass

    # -----------------------------------------------------
    # البحث عن عنوان Description
    # -----------------------------------------------------

    try:

        headings = page.locator(
            "h2, h3, h4, strong"
        ).all()

        for heading in headings:

            try:

                heading_text = clean_text(
                    heading.inner_text()
                )

                if heading_text.lower() not in [
                    "description",
                    "description:",
                    "détails",
                    "details"
                ]:
                    continue

                for level in range(1, 5):

                    try:

                        parent = heading.locator(
                            "xpath=" + "/.." * level
                        ).first

                        if parent.count() == 0:
                            continue

                        text = clean_text(
                            parent.inner_text()
                        )

                        # إزالة كلمة Description
                        text = re.sub(
                            r"^\s*description\s*:?\s*",
                            "",
                            text,
                            flags=re.IGNORECASE
                        )

                        text = clean_text(text)

                        if len(text) >= 10:

                            candidates.append(
                                text
                            )

                    except Exception:
                        pass

            except Exception:
                pass

    except Exception:
        pass

    if not candidates:
        return ""

    # إزالة duplicates
    unique = []

    for item in candidates:

        if item not in unique:
            unique.append(item)

    # نأخذ المرشح الأفضل
    # مع تجنب body كامل الصفحة
    unique.sort(
        key=len,
        reverse=True
    )

    for text in unique:

        low = text.lower()

        # لا نريد wrapper ضخم يحتوي الكتالوج كله
        if len(text) > 5000:
            continue

        if (
            "prix revendeur" in low
            and "description" not in low
        ):
            continue

        return text

    return unique[0]


# =========================================================
# SIZES
# =========================================================

SIZE_REGEX = re.compile(
    r"^(?:"
    r"XXXS|XXS|XS|S|M|L|XL|XXL|XXXL|"
    r"2XL|3XL|4XL|5XL|"
    r"\d{2}"
    r")$",
    re.IGNORECASE
)


def extract_sizes(page):

    sizes = []
    seen = set()

    selectors = [

        "select option",

        "input[type='radio']",

        "input[name='size']",

        "[data-size]",

        "[class*='size']",

        "[class*='Size']"
    ]

    for selector in selectors:

        try:

            elements = page.locator(
                selector
            ).all()

            for element in elements:

                values = []

                for attr in [
                    "data-size",
                    "value",
                    "title"
                ]:

                    try:

                        value = element.get_attribute(
                            attr
                        )

                        if value:
                            values.append(value)

                    except Exception:
                        pass

                try:

                    values.append(
                        element.inner_text()
                    )

                except Exception:
                    pass

                for value in values:

                    value = clean_text(value)

                    if not value:
                        continue

                    # -------------------------------------------------
                    # إذا كان value مثلاً "Size: XL"
                    # -------------------------------------------------

                    parts = re.split(
                        r"[:|/,]+",
                        value
                    )

                    for part in parts:

                        part = clean_text(
                            part
                        )

                        # معالجة "-"
                        if "-" in part and len(part) < 10:
                            subparts = [
                                clean_text(x)
                                for x in part.split("-")
                            ]
                        else:
                            subparts = [part]

                        for item in subparts:

                            if not item:
                                continue

                            if SIZE_REGEX.match(item):

                                normalized = item.upper()

                                if normalized not in seen:

                                    seen.add(
                                        normalized
                                    )

                                    sizes.append(
                                        normalized
                                    )

        except Exception:
            pass

    return sizes


# =========================================================
# COLORS
# =========================================================

def extract_colors(page):

    colors = []
    seen = set()

    selectors = [

        ".color-button",

        "[data-color]",

        "button[data-color]",

        "input[data-color]",

        "[class*='color-button']",

        "[class*='Color-button']",

        "[class*='color-option']",

        "[class*='Color-option']",

        "[class*='color']"
    ]

    for selector in selectors:

        try:

            elements = page.locator(
                selector
            ).all()

            for element in elements:

                candidates = []

                # -------------------------------------------------
                # data-color
                # -------------------------------------------------

                for attr in [
                    "data-color",
                    "data-colour",
                    "title",
                    "aria-label",
                    "value"
                ]:

                    try:

                        value = element.get_attribute(
                            attr
                        )

                        if value:
                            candidates.append(
                                value
                            )

                    except Exception:
                        pass

                # -------------------------------------------------
                # parent title / data-color
                # -------------------------------------------------

                try:

                    parent = element.locator(
                        ".."
                    ).first

                    if parent.count() > 0:

                        for attr in [
                            "data-color",
                            "data-colour",
                            "title",
                            "aria-label"
                        ]:

                            try:

                                value = parent.get_attribute(
                                    attr
                                )

                                if value:
                                    candidates.append(
                                        value
                                    )

                            except Exception:
                                pass

                except Exception:
                    pass

                # -------------------------------------------------
                # النص
                # -------------------------------------------------

                try:

                    text = clean_text(
                        element.inner_text()
                    )

                    if text:
                        candidates.append(
                            text
                        )

                except Exception:
                    pass

                # -------------------------------------------------
                # اختيار color
                # -------------------------------------------------

                for value in candidates:

                    value = clean_text(
                        value
                    )

                    if not value:
                        continue

                    if len(value) > 80:
                        continue

                    # استبعاد أشياء ليست ألواناً
                    low = value.lower()

                    ignored = [

                        "color",
                        "colour",
                        "couleur",

                        "select",
                        "choisir",

                        "size",
                        "taille",

                        "add to cart",
                        "acheter",
                        "commander"
                    ]

                    if low in ignored:
                        continue

                    # لا نعتبر RGB/hex ألواناً نصية
                    # إذا كان الموقع يستعملها كـstyle
                    if re.match(
                        r"^#[0-9a-f]{3,8}$",
                        low
                    ):
                        # نخليها لأنها قد تكون
                        # المصدر الوحيد للون
                        pass

                    # تنظيف label
                    value = re.sub(
                        r"^(?:color|colour|couleur)\s*[:\-]\s*",
                        "",
                        value,
                        flags=re.IGNORECASE
                    )

                    value = clean_text(value)

                    if not value:
                        continue

                    key = value.lower()

                    if key not in seen:

                        seen.add(key)
                        colors.append(value)

    return colors


# =========================================================
# STATUS
# =========================================================

def extract_status(page):

    selectors = [

        ".stock-status",

        ".product-stock",

        "[class*='stock-status']",

        "[class*='product-stock']",

        "[class*='stock']"
    ]

    for selector in selectors:

        try:

            elements = page.locator(
                selector
            ).all()

            for element in elements:

                text = clean_text(
                    element.inner_text()
                )

                if text:
                    return text

        except Exception:
            pass

    body = ""

    try:

        body = clean_text(
            page.locator("body").inner_text()
        )

    except Exception:
        pass

    low = body.lower()

    if (
        "rupture" in low
        or "out of stock" in low
        or "غير متوفر" in low
    ):
        return "Out of Stock"

    return "In Stock"


# =========================================================
# PRODUCT LINK
# =========================================================

def looks_like_product_link(href):

    if not href:
        return False

    h = href.lower()

    patterns = [

        "/product/",
        "/products/",

        "/affiliate/product/",
        "/affiliate/products/",

        "/p/"
    ]

    return any(
        pattern in h
        for pattern in patterns
    )


# =========================================================
# DETAIL PAGE
# =========================================================

def scrape_product_details(
    context,
    product
):

    url = product.get(
        "original_link"
    )

    if not url:
        return product

    detail = context.new_page()

    try:

        print(
            f"      🔎 فتح: {url}"
        )

        detail.goto(
            url,
            wait_until="domcontentloaded",
            timeout=30000
        )

        try:

            detail.wait_for_load_state(
                "networkidle",
                timeout=12000
            )

        except Exception:
            pass

        detail.wait_for_timeout(
            2000
        )

        # =================================================
        # BODY
        # =================================================

        try:

            body = clean_text(
                detail.locator(
                    "body"
                ).inner_text()
            )

        except Exception:

            body = ""

        # =================================================
        # TITLE
        # =================================================

        title = find_title(
            detail,
            body
        )

        if title:

            product["title"] = title

        # =================================================
        # ALL IMAGES
        # =================================================

        images = extract_all_images(
            detail
        )

        if images:

            product["images"] = images
            product["image"] = images[0]

        else:

            product.setdefault(
                "images",
                []
            )

        # =================================================
        # ALL VIDEOS
        # =================================================

        videos = extract_all_videos(
            detail
        )

        product["videos"] = videos

        # =================================================
        # DESCRIPTION
        # =================================================

        description = extract_description(
            detail
        )

        product["description"] = (
            description
        )

        # =================================================
        # SIZES
        # =================================================

        sizes = extract_sizes(
            detail
        )

        product["sizes"] = sizes

        # =================================================
        # COLORS
        # =================================================

        colors = extract_colors(
            detail
        )

        product["colors"] = colors

        # =================================================
        # STATUS
        # =================================================

        product["status"] = extract_status(
            detail
        )

        # =================================================
        # EXACT PRIX REVENDEUR
        # =================================================

        reseller_price = (
            extract_revendeur_price(
                body
            )
        )

        if reseller_price is not None:

            product["original_price"] = (
                format_price(
                    reseller_price
                )
            )

            selling_price = (
                reseller_price
                + PROFIT_MARGIN
            )

            product["price"] = (
                format_price(
                    selling_price
                )
            )

        # =================================================
        # LOG
        # =================================================

        print(
            f"      🖼️ الصور: "
            f"{len(product.get('images', []))}"
        )

        print(
            f"      🎥 الفيديوهات: "
            f"{len(product.get('videos', []))}"
        )

        print(
            f"      📏 المقاسات: "
            f"{product.get('sizes', [])}"
        )

        print(
            f"      🎨 الألوان: "
            f"{product.get('colors', [])}"
        )

        print(
            f"      📝 الوصف: "
            f"{'نعم' if description else 'لا'}"
        )

        print(
            f"      💰 Prix revendeur: "
            f"{product.get('original_price', '')}"
        )

        print(
            f"      🏷️ Prix SHADHW: "
            f"{product.get('price', '')}"
        )

    except Exception as e:

        print(
            f"      ⚠️ خطأ تفاصيل المنتج: "
            f"{e}"
        )

    finally:

        try:
            detail.close()
        except Exception:
            pass

    return product


# =========================================================
# FIND PRODUCT TITLE FROM CARD
# =========================================================

def find_card_title(
    container,
    text
):

    return find_title(
        container,
        text
    )


# =========================================================
# SCRAPE CURRENT LISTING PAGE
# =========================================================

def scrape_current_page(
    page,
    all_products
):

    before_count = len(
        all_products
    )

    try:

        try:

            page.wait_for_load_state(
                "networkidle",
                timeout=15000
            )

        except Exception:
            pass

        page.wait_for_timeout(
            4000
        )

        links = page.locator(
            "a"
        ).all()

        print(
            f"🔎 روابط الصفحة: "
            f"{len(links)}"
        )

        seen_links = set()

        for link in links:

            try:

                href = link.get_attribute(
                    "href"
                )

                if not looks_like_product_link(
                    href
                ):
                    continue

                absolute_href = absolute_url(
                    href
                )

                if not absolute_href:
                    continue

                if absolute_href in seen_links:
                    continue

                seen_links.add(
                    absolute_href
                )

                # =================================================
                # CONTAINER
                # =================================================

                container = link

                for _ in range(6):

                    try:

                        parent = container.locator(
                            ".."
                        )

                        if parent.count() == 0:
                            break

                        parent_text = clean_text(
                            parent.inner_text()
                        )

                        if len(parent_text) >= 10:
                            container = parent

                        if container.locator(
                            "img"
                        ).count() > 0:
                            break

                    except Exception:
                        break

                text = clean_text(
                    container.inner_text()
                )

                if not text:
                    text = clean_text(
                        link.inner_text()
                    )

                if not text:
                    continue

                # =================================================
                # OUT OF STOCK
                # =================================================

                low_text = text.lower()

                unavailable_words = [

                    "rupture",
                    "out of stock",
                    "out-of-stock",

                    "غير متوفر",
                    "نفذت الكمية"
                ]

                if any(
                    word in low_text
                    for word in unavailable_words
                ):
                    continue

                # =================================================
                # PRIX REVENDEUR
                # =================================================

                base_price = (
                    extract_revendeur_price(
                        text
                    )
                )

                # fallback فقط إذا لم نجد
                # Prix revendeur
                if base_price is None:

                    base_price = extract_price(
                        text
                    )

                if base_price is None:
                    continue

                # =================================================
                # TITLE
                # =================================================

                title = find_card_title(
                    container,
                    text
                )

                if not title:
                    continue

                # =================================================
                # IMAGE
                # =================================================

                image_url = ""

                try:

                    images = container.locator(
                        "img"
                    ).all()

                    for img in images:

                        image_url = (
                            extract_image(img)
                            or ""
                        )

                        if image_url:
                            break

                except Exception:
                    pass

                # =================================================
                # DUPLICATE
                # =================================================

                duplicate = False

                for existing in all_products:

                    existing_link = (
                        existing.get(
                            "original_link",
                            ""
                        )
                    )

                    existing_title = (
                        existing.get(
                            "title",
                            ""
                        )
                    )

                    if (
                        existing_link
                        == absolute_href
                    ):

                        duplicate = True
                        break

                    if (
                        existing_title
                        and existing_title.lower()
                        == title.lower()
                    ):

                        duplicate = True
                        break

                if duplicate:
                    continue

                # =================================================
                # PRICE
                # =================================================

                selling_price = (
                    base_price
                    + PROFIT_MARGIN
                )

                # =================================================
                # PRODUCT
                # =================================================

                product = {

                    "id": (
                        f"shadhw_"
                        f"{len(all_products) + 1}"
                    ),

                    "title": title,

                    "image": image_url,

                    "images": (
                        [image_url]
                        if image_url
                        else []
                    ),

                    "videos": [],

                    "description": "",

                    "sizes": [],

                    "colors": [],

                    "price": format_price(
                        selling_price
                    ),

                    "original_price": format_price(
                        base_price
                    ),

                    "original_link": (
                        absolute_href
                    ),

                    "status": "In Stock"
                }

                all_products.append(
                    product
                )

                print(
                    f"   ✅ {title}"
                )

                print(
                    f"      💰 "
                    f"{format_price(base_price)}"
                    f" → "
                    f"{format_price(selling_price)}"
                )

                print(
                    f"      🖼️ "
                    f"{'OK' if image_url else 'NO IMAGE'}"
                )

            except Exception as item_error:

                print(
                    f"   ⚠️ تخطي عنصر: "
                    f"{item_error}"
                )

    except Exception as e:

        print(
            f"⚠️ خطأ في استخراج الروابط: "
            f"{e}"
        )

    # =========================================================
    # FALLBACK CARDS
    # =========================================================

    if len(all_products) == before_count:

        print(
            "🔄 لم يتم استخراج منتجات "
            "بالطريقة الأولى، نجرب البطاقات..."
        )

        try:

            cards = page.locator(

                "[class*='product'], "
                "[class*='Product'], "

                "[class*='card'], "
                "[class*='Card'], "

                "[class*='item'], "
                "[class*='Item'], "

                "[class*='offer'], "
                "[class*='Offer'], "

                "article, "
                "li"

            ).all()

            print(
                f"🔎 العناصر المرشحة: "
                f"{len(cards)}"
            )

            for card in cards:

                try:

                    text = clean_text(
                        card.inner_text()
                    )

                    if len(text) < 5:
                        continue

                    low_text = text.lower()

                    if any(
                        word in low_text
                        for word in [
                            "rupture",
                            "out of stock",
                            "غير متوفر"
                        ]
                    ):
                        continue

                    base_price = (
                        extract_revendeur_price(
                            text
                        )
                    )

                    if base_price is None:

                        base_price = extract_price(
                            text
                        )

                    if base_price is None:
                        continue

                    title = find_card_title(
                        card,
                        text
                    )

                    if not title:
                        continue

                    # =================================================
                    # LINK
                    # =================================================

                    href = ""

                    try:

                        a = card.locator(
                            "a"
                        ).first

                        if a.count() > 0:

                            href = (
                                a.get_attribute(
                                    "href"
                                )
                                or ""
                            )

                            href = absolute_url(
                                href
                            )

                    except Exception:
                        pass

                    # =================================================
                    # IMAGE
                    # =================================================

                    image_url = ""

                    try:

                        for img in card.locator(
                            "img"
                        ).all():

                            image_url = (
                                extract_image(img)
                                or ""
                            )

                            if image_url:
                                break

                    except Exception:
                        pass

                    # =================================================
                    # DUPLICATE
                    # =================================================

                    duplicate = any(

                        p.get(
                            "title",
                            ""
                        ).lower()
                        == title.lower()

                        for p in all_products

                    )

                    if duplicate:
                        continue

                    selling_price = (
                        base_price
                        + PROFIT_MARGIN
                    )

                    product = {

                        "id": (
                            f"shadhw_"
                            f"{len(all_products) + 1}"
                        ),

                        "title": title,

                        "image": image_url,

                        "images": (
                            [image_url]
                            if image_url
                            else []
                        ),

                        "videos": [],

                        "description": "",

                        "sizes": [],

                        "colors": [],

                        "price": format_price(
                            selling_price
                        ),

                        "original_price": format_price(
                            base_price
                        ),

                        "original_link": href,

                        "status": "In Stock"
                    }

                    all_products.append(
                        product
                    )

                    print(
                        f"   ✅ CARD: "
                        f"{title}"
                    )

                except Exception:
                    continue

        except Exception as e:

            print(
                f"⚠️ خطأ في البطاقات: "
                f"{e}"
            )

    new_products = (
        len(all_products)
        - before_count
    )

    return (
        all_products,
        new_products
    )


# =========================================================
# MAIN
# =========================================================

def run_automation():

    with sync_playwright() as p:

        # =====================================================
        # BROWSER
        # =====================================================

        print(
            "🔗 [1/4] إطلاق المتصفح..."
        )

        browser = p.chromium.launch(
            headless=True
        )

        context = browser.new_context(

            viewport={
                "width": 1280,
                "height": 800
            },

            user_agent=(
                "Mozilla/5.0 "
                "(Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 "
                "(KHTML, like Gecko) "
                "Chrome/122.0.0.0 "
                "Safari/537.36"
            ),

            locale="fr-FR"
        )

        page = context.new_page()

        # =====================================================
        # LOGIN
        # =====================================================

        page.goto(
            "https://boughalaffiliate.com/login",
            wait_until="load"
        )

        time.sleep(4)

        print(
            "🔐 [2/4] ملء بيانات الدخول..."
        )

        email_input = page.locator(
            "input[type='email'], "
            "input[name='email']"
        ).first

        email_input.focus()
        email_input.fill(
            EMAIL
        )

        password_input = page.locator(
            "input[type='password'], "
            "input[name='password']"
        ).first

        password_input.focus()
        password_input.fill(
            PASSWORD
        )

        time.sleep(2)

        print(
            "🚀 [3/4] تسجيل الدخول..."
        )

        try:

            login_btn = page.locator(
                "button[type='submit'], "
                "button:has-text('Se connecter'), "
                ".btn-primary"
            ).first

            login_btn.focus()

            login_btn.click(
                force=True,
                timeout=5000
            )

        except Exception:

            print(
                "⚠️ النقر العادي لم يعمل، "
                "نستخدم Enter..."
            )

            page.keyboard.press(
                "Enter"
            )

        time.sleep(8)

        # =====================================================
        # PRODUCTS
        # =====================================================

        print(
            "🛍️ [4/4] الدخول إلى كتالوج المنتجات..."
        )

        page.goto(
            BASE_PRODUCTS_URL,
            wait_until="networkidle"
        )

        time.sleep(6)

        # =====================================================
        # SCRAPE ALL PAGES
        # =====================================================

        all_products = []

        page_number = 1

        empty_pages = 0

        while True:

            if page_number == 1:

                url = (
                    BASE_PRODUCTS_URL
                )

            else:

                url = (
                    f"{BASE_PRODUCTS_URL}"
                    f"?page={page_number}"
                )

            print("")
            print("=" * 70)

            print(
                f"📄 الصفحة {page_number}"
            )

            print(
                f"🔗 {url}"
            )

            print("=" * 70)

            try:

                page.goto(
                    url,
                    wait_until="networkidle",
                    timeout=30000
                )

            except Exception as navigation_error:

                print(
                    f"⚠️ مشكلة أثناء فتح الصفحة "
                    f"{page_number}: "
                    f"{navigation_error}"
                )

                break

            page.wait_for_timeout(
                4000
            )

            # =================================================
            # SCREENSHOT
            # =================================================

            try:

                page.screenshot(
                    path=(
                        f"page_{page_number}.png"
                    ),
                    full_page=True
                )

            except Exception:
                pass

            # =================================================
            # EXTRACT
            # =================================================

            all_products, new_count = (
                scrape_current_page(
                    page,
                    all_products
                )
            )

            print("")
            print(
                f"📦 الصفحة {page_number}: "
                f"+{new_count} منتج"
            )

            print(
                f"📊 الإجمالي: "
                f"{len(all_products)}"
            )

            # =================================================
            # EMPTY PAGE
            # =================================================

            if new_count == 0:

                empty_pages += 1

                print(
                    f"⚠️ الصفحة لم تضف منتجات "
                    f"({empty_pages}/{MAX_EMPTY_PAGES})"
                )

                if (
                    empty_pages
                    >= MAX_EMPTY_PAGES
                ):

                    print(
                        "🛑 صفحات فارغة متتالية."
                    )

                    print(
                        "🏁 نهاية الكتالوج."
                    )

                    break

            else:

                empty_pages = 0

            # =================================================
            # NEXT PAGE
            # =================================================

            page_number += 1

            if page_number > MAX_PAGES:

                print(
                    f"🛑 تجاوز {MAX_PAGES} صفحة."
                )

                break

        # =====================================================
        # PRODUCT DETAILS
        # =====================================================

        print("")
        print("=" * 70)

        print(
            "🔍 استخراج تفاصيل جميع المنتجات..."
        )

        print("=" * 70)

        total = len(
            all_products
        )

        for index, product in enumerate(
            all_products,
            start=1
        ):

            print("")
            print(
                f"📦 {index}/{total}: "
                f"{product.get('title', '')}"
            )

            scrape_product_details(
                context,
                product
            )

        # =====================================================
        # FINAL NORMALIZATION
        # =====================================================

        for index, product in enumerate(
            all_products,
            start=1
        ):

            product["id"] = (
                f"shadhw_{index}"
            )

            product.setdefault(
                "images",
                []
            )

            product.setdefault(
                "videos",
                []
            )

            product.setdefault(
                "description",
                ""
            )

            product.setdefault(
                "sizes",
                []
            )

            product.setdefault(
                "colors",
                []
            )

            product.setdefault(
                "status",
                "In Stock"
            )

            product.setdefault(
                "original_link",
                ""
            )

            if (
                not product.get("image")
                and product["images"]
            ):

                product["image"] = (
                    product["images"][0]
                )

        # =====================================================
        # SAVE PRODUCTS.JSON
        # =====================================================

        print("")
        print("=" * 70)

        print(
            "💾 حفظ products.json..."
        )

        print("=" * 70)

        with open(
            "products.json",
            "w",
            encoding="utf-8"
        ) as f:

            json.dump(
                all_products,
                f,
                ensure_ascii=False,
                indent=4
            )

        print(
            f"✅ تم حفظ "
            f"{len(all_products)} "
            f"منتج."
        )

        # =====================================================
        # SAVE SOURCE.HTML
        # =====================================================

        try:

            with open(
                "source.html",
                "w",
                encoding="utf-8"
            ) as f:

                f.write(
                    page.content()
                )

            print(
                "✅ تم حفظ source.html"
            )

        except Exception as e:

            print(
                f"⚠️ لم يتم حفظ source.html: "
                f"{e}"
            )

        # =====================================================
        # FINAL REPORT
        # =====================================================

        print("")
        print("=" * 70)

        print(
            "🎉 اكتمل تحديث الكتالوج!"
        )

        print(
            f"📄 عدد الصفحات: "
            f"{page_number}"
        )

        print(
            f"📦 عدد المنتجات: "
            f"{len(all_products)}"
        )

        print(
            "🖼️ الصور: مفعلة"
        )

        print(
            "🎥 الفيديوهات: مفعلة"
        )

        print(
            "📝 الوصف: مفعل"
        )

        print(
            "📏 المقاسات: مفعلة"
        )

        print(
            "🎨 الألوان: مفعلة"
        )

        print(
            "💰 Prix revendeur: مفعل"
        )

        print(
            f"➕ هامش الربح: "
            f"{PROFIT_MARGIN} DH"
        )

        print("=" * 70)

        browser.close()


# =========================================================
# START
# =========================================================

if __name__ == "__main__":
    run_automation()

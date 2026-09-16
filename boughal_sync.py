import os
import json
import time
import re
from urllib.parse import urljoin
from playwright.sync_api import sync_playwright

EMAIL = os.environ.get("BOUGHAL_EMAIL")
PASSWORD = os.environ.get("BOUGHAL_PASSWORD")

BASE_PRODUCTS_URL = "https://boughalaffiliate.com/affiliate/products"
PROFIT_MARGIN = 100

MAX_EMPTY_PAGES = 2
MAX_PAGES = 1000


# =========================================================
# BASIC HELPERS
# =========================================================

def clean_text(value):
    if not value:
        return ""
    return " ".join(value.split()).strip()


def absolute_url(url, base="https://boughalaffiliate.com"):
    if not url:
        return ""

    url = url.strip()

    if url.startswith("//"):
        return "https:" + url

    return urljoin(base, url)


def unique_list(items):
    result = []
    seen = set()

    for item in items:
        item = clean_text(item)

        if not item:
            continue

        key = item.lower()

        if key not in seen:
            seen.add(key)
            result.append(item)

    return result


# =========================================================
# PRICE
# =========================================================

def extract_price(text):
    if not text:
        return None

    patterns = [
        r'(\d+(?:[.,]\d{1,2})?)\s*(?:DH|dh|MAD|mad)',
        r'(?:DH|dh|MAD|mad)\s*(\d+(?:[.,]\d{1,2})?)',
        r'(\d+(?:[.,]\d{1,2})?)\s*د\.?\s*م',
        r'(\d+(?:[.,]\d{1,2})?)\s*(?:درهم|درهما|درهمًا)'
    ]

    for pattern in patterns:
        match = re.search(pattern, text)

        if match:
            try:
                return float(
                    match.group(1).replace(",", ".")
                )
            except Exception:
                pass

    return None


def extract_revendeur_price(text):
    if not text:
        return None

    text = clean_text(text)

    patterns = [
        r"prix\s+revendeur\s*[:\-]?\s*(\d+(?:[.,]\d{1,2})?)",
        r"prix\s*revendeur.{0,100}?(\d+(?:[.,]\d{1,2})?)",
        r"revendeur\s*[:\-]?\s*(\d+(?:[.,]\d{1,2})?)",
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
                    match.group(1).replace(",", ".")
                )
            except Exception:
                pass

    # محاولة البحث سطر بسطر
    lines = [
        clean_text(x)
        for x in text.split("\n")
        if clean_text(x)
    ]

    for i, line in enumerate(lines):

        if (
            "prix revendeur" in line.lower()
            or "revendeur" in line.lower()
        ):

            value = extract_price(line)

            if value is not None:
                return value

            if i + 1 < len(lines):

                value = extract_price(
                    lines[i + 1]
                )

                if value is not None:
                    return value

    return None


# =========================================================
# IMAGE
# =========================================================

def extract_image(img):
    if not img:
        return None

    attributes = [
        "src",
        "data-src",
        "data-image",
        "data-original",
        "data-lazy-src",
        "data-lazy",
        "data-url",
        "data-original-src"
    ]

    candidates = []

    for attr in attributes:

        try:

            value = img.get_attribute(attr)

            if value:
                candidates.append(value)

        except Exception:
            pass

    try:

        srcset = img.get_attribute(
            "srcset"
        )

        if srcset:

            for part in srcset.split(","):

                url = (
                    part.strip()
                    .split(" ")[0]
                    .strip()
                )

                if url:
                    candidates.append(url)

    except Exception:
        pass

    blocked = [
        "placeholder",
        "placehold",
        "unsplash.com",
        "default-image",
        "default_image",
        "no-image",
        "no_image",
        "noimage"
    ]

    for url in candidates:

        if not url:
            continue

        low = url.lower()

        if any(
            word in low
            for word in blocked
        ):
            continue

        return absolute_url(url)

    return None


def extract_all_images(container):
    results = []
    seen = set()

    try:

        # نجمع الصور من أكثر من selector
        selectors = [
            ".product-main-slider img",
            ".product-gallery img",
            ".product-images img",
            ".swiper-slide img",
            "[class*='gallery'] img",
            "[class*='Gallery'] img",
            "[class*='product-image'] img",
            "img"
        ]

        for selector in selectors:

            try:

                imgs = container.locator(
                    selector
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

    except Exception:
        pass

    return results


# =========================================================
# VIDEO
# =========================================================

def extract_all_videos(page):
    videos = []

    # =====================================================
    # <video>
    # =====================================================

    try:

        video_elements = page.locator(
            "video"
        ).all()

        for video in video_elements:

            for attr in [
                "src",
                "data-src",
                "data-video",
                "data-video-url"
            ]:

                try:

                    value = video.get_attribute(
                        attr
                    )

                    if value:
                        videos.append(
                            absolute_url(value)
                        )

                except Exception:
                    pass

            # <source src="...mp4">
            try:

                sources = video.locator(
                    "source"
                ).all()

                for source in sources:

                    for attr in [
                        "src",
                        "data-src"
                    ]:

                        try:

                            value = (
                                source.get_attribute(
                                    attr
                                )
                            )

                            if value:
                                videos.append(
                                    absolute_url(
                                        value
                                    )
                                )

                        except Exception:
                            pass

            except Exception:
                pass

    except Exception:
        pass

    # =====================================================
    # FALLBACK
    # =====================================================

    selectors = [
        "[data-video]",
        "[data-video-url]",
        "[data-src*='.mp4']",
        "[href*='.mp4']",
        "source[src*='.mp4']"
    ]

    for selector in selectors:

        try:

            elements = page.locator(
                selector
            ).all()

            for element in elements:

                for attr in [
                    "src",
                    "data-src",
                    "data-video",
                    "data-video-url",
                    "href"
                ]:

                    try:

                        value = (
                            element.get_attribute(
                                attr
                            )
                        )

                        if (
                            value
                            and ".mp4"
                            in value.lower()
                        ):
                            videos.append(
                                absolute_url(
                                    value
                                )
                            )

                    except Exception:
                        pass

        except Exception:
            pass

    return unique_list(videos)


# =========================================================
# DESCRIPTION
# =========================================================

def extract_description(page):

    selectors = [
        "#description",
        ".description",
        "[data-description]",
        ".product-description",
        "[class*='product-description']",
        "[class*='Product-description']",
        "[class*='description']",
        "[class*='Description']"
    ]

    candidates = []

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

                    if len(text) >= 10:
                        candidates.append(text)

                except Exception:
                    pass

        except Exception:
            pass

    # الأفضل: النص الأطول
    if candidates:
        return max(
            candidates,
            key=len
        )

    # البحث عن عنوان Description
    try:

        headings = page.locator(
            "h1,h2,h3,h4,h5,strong,b"
        ).all()

        for heading in headings:

            try:

                heading_text = clean_text(
                    heading.inner_text()
                )

                if (
                    heading_text.lower()
                    == "description"
                ):

                    parent = heading.locator(
                        ".."
                    )

                    text = clean_text(
                        parent.inner_text()
                    )

                    text = re.sub(
                        r"^description\s*:?\s*",
                        "",
                        text,
                        flags=re.I
                    )

                    if len(text) >= 10:
                        return text

            except Exception:
                pass

    except Exception:
        pass

    return ""


# =========================================================
# SIZES
# =========================================================

def extract_sizes(page):

    sizes = []
    seen = set()

    size_regex = re.compile(
        r'^(?:'
        r'XXXS|XXS|XS|S|M|L|XL|XXL|XXXL|'
        r'2XL|3XL|4XL|5XL|'
        r'\d{2}'
        r')$',
        re.I
    )

    selectors = [
        "select option",
        "input[type='radio']",
        "[data-size]",
        ".size-button",
        ".size-option",
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
                    "value"
                ]:

                    try:

                        value = (
                            element.get_attribute(
                                attr
                            )
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

                    parts = re.split(
                        r'[:|/\-,]+',
                        clean_text(value)
                    )

                    for part in parts:

                        part = clean_text(
                            part
                        )

                        if size_regex.match(
                            part
                        ):

                            normalized = (
                                part.upper()
                            )

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
        "[class*='Color-option']"
    ]

    for selector in selectors:

        try:

            elements = page.locator(
                selector
            ).all()

            for element in elements:

                values = []

                for attr in [
                    "data-color",
                    "data-colour",
                    "title",
                    "aria-label",
                    "value"
                ]:

                    try:

                        value = (
                            element.get_attribute(
                                attr
                            )
                        )

                        if value:
                            values.append(value)

                    except Exception:
                        pass

                try:

                    text = clean_text(
                        element.inner_text()
                    )

                    if text:
                        values.append(text)

                except Exception:
                    pass

                # parent
                if not values:

                    try:

                        parent = element.locator(
                            ".."
                        )

                        for attr in [
                            "data-color",
                            "data-colour",
                            "title",
                            "aria-label"
                        ]:

                            value = (
                                parent.get_attribute(
                                    attr
                                )
                            )

                            if value:
                                values.append(
                                    value
                                )

                        try:

                            text = clean_text(
                                parent.inner_text()
                            )

                            if text:
                                values.append(
                                    text
                                )

                        except Exception:
                            pass

                    except Exception:
                        pass

                for value in values:

                    value = clean_text(
                        value
                    )

                    if (
                        not value
                        or len(value) > 50
                    ):
                        continue

                    # تجاهل القيم العامة جداً
                    if value.lower() in [
                        "color",
                        "colour",
                        "couleur",
                        "couleurs"
                    ]:
                        continue

                    key = value.lower()

                    if key not in seen:

                        seen.add(key)
                        colors.append(value)

        except Exception:
            pass

    return colors


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
        "h4",
        "h5",
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

            for candidate in elements:

                try:

                    data_title = (
                        candidate.get_attribute(
                            "data-title"
                        )
                    )

                    if data_title:

                        data_title = clean_text(
                            data_title
                        )

                        if len(data_title) >= 3:
                            return data_title

                except Exception:
                    pass

                try:

                    text = clean_text(
                        candidate.inner_text()
                    )

                    if (
                        len(text) >= 3
                        and len(text) <= 250
                        and extract_price(text)
                        is None
                    ):
                        return text

                except Exception:
                    pass

        except Exception:
            pass

    # fallback
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
        "prix revendeur"
    ]

    for line in lines:

        if len(line) < 3:
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
# PRODUCT DETAILS
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
            f"      🔗 {url}"
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
            2500
        )

        body = clean_text(
            detail.locator(
                "body"
            ).inner_text()
        )

        # =================================================
        # TITLE
        # =================================================

        title_selectors = [
            "h1",
            "[class*='product-title']",
            "[class*='Product-title']",
            "[data-product-title]"
        ]

        for selector in title_selectors:

            try:

                elements = detail.locator(
                    selector
                ).all()

                for element in elements:

                    text = clean_text(
                        element.inner_text()
                    )

                    if (
                        3 <= len(text) <= 250
                        and extract_price(text)
                        is None
                    ):

                        product["title"] = text
                        raise StopIteration

            except StopIteration:
                break

            except Exception:
                pass

        # =================================================
        # ALL IMAGES
        # =================================================

        images = extract_all_images(
            detail
        )

        if images:

            product["images"] = images
            product["image"] = images[0]

        # =================================================
        # VIDEOS
        # =================================================

        videos = extract_all_videos(
            detail
        )

        product["videos"] = videos

        # =================================================
        # DESCRIPTION
        # =================================================

        product["description"] = (
            extract_description(detail)
        )

        # =================================================
        # SIZES
        # =================================================

        product["sizes"] = (
            extract_sizes(detail)
        )

        # =================================================
        # COLORS
        # =================================================

        product["colors"] = (
            extract_colors(detail)
        )

        # =================================================
        # STATUS
        # =================================================

        low_body = body.lower()

        if any(
            word in low_body
            for word in [
                "rupture de stock",
                "out of stock",
                "hors stock",
                "épuisé",
                "epuise",
                "indisponible",
                "non disponible"
            ]
        ):
            product["status"] = (
                "Out of Stock"
            )
        else:
            product["status"] = (
                "In Stock"
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
                f"{int(reseller_price)} DH"
            )

            product["price"] = (
                f"{int(reseller_price + PROFIT_MARGIN)} DH"
            )

        print(
            f"      🖼️ Images: "
            f"{len(product['images'])}"
        )

        print(
            f"      🎥 Videos: "
            f"{len(product['videos'])}"
        )

        print(
            f"      📝 Description: "
            f"{'YES' if product['description'] else 'NO'}"
        )

        print(
            f"      📏 Sizes: "
            f"{product['sizes']}"
        )

        print(
            f"      🎨 Colors: "
            f"{product['colors']}"
        )

        print(
            f"      💰 Revendeur: "
            f"{product['original_price']}"
        )

    except Exception as e:

        print(
            f"      ⚠️ تفاصيل المنتج: {e}"
        )

    finally:

        try:
            detail.close()
        except Exception:
            pass

    return product


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

        # =================================================
        # الطريقة الأولى: روابط المنتجات
        # =================================================

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

                # =============================================
                # FIND PRODUCT CONTAINER
                # =============================================

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

                        if (
                            container.locator(
                                "img"
                            ).count() > 0
                        ):
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

                # =============================================
                # OUT OF STOCK
                # =============================================

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

                # =============================================
                # PRIX REVENDEUR
                # =============================================

                base_price = (
                    extract_revendeur_price(
                        text
                    )
                )

                # fallback فقط إذا لم نجد label
                if base_price is None:

                    base_price = extract_price(
                        text
                    )

                if base_price is None:
                    continue

                # =============================================
                # PRICE +100 DH
                # =============================================

                your_price = int(
                    base_price
                    + PROFIT_MARGIN
                )

                # =============================================
                # TITLE
                # =============================================

                title = find_title(
                    container,
                    text
                )

                if not title:
                    continue

                # =============================================
                # IMAGE
                # =============================================

                image_url = ""

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

                # =============================================
                # DUPLICATE
                # =============================================

                duplicate = any(
                    p.get("original_link")
                    == absolute_href
                    or p.get("title", "").lower()
                    == title.lower()
                    for p in all_products
                )

                if duplicate:
                    continue

                # =============================================
                # PRODUCT
                # =============================================

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

                    "price": (
                        f"{your_price} DH"
                    ),

                    "original_price": (
                        f"{int(base_price)} DH"
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
                    f"{int(base_price)} DH"
                    f" → "
                    f"{your_price} DH"
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

        # =================================================
        # FALLBACK CARD DISCOVERY
        # =================================================

        if len(all_products) == before_count:

            print(
                "🔄 لم نجد منتجات عبر الروابط، "
                "نجرب البطاقات..."
            )

            try:

                cards = page.locator(
                    "[class*='product'], "
                    "[class*='Product'], "
                    "[class*='card'], "
                    "[class*='Card'], "
                    "article, li"
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

                        title = find_title(
                            card,
                            text
                        )

                        if not title:
                            continue

                        # الرابط
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

                        # الصورة
                        image_url = ""

                        for img in card.locator(
                            "img"
                        ).all():

                            image_url = (
                                extract_image(img)
                                or ""
                            )

                            if image_url:
                                break

                        # duplicate
                        duplicate = any(
                            p.get("title", "").lower()
                            == title.lower()
                            for p in all_products
                        )

                        if duplicate:
                            continue

                        your_price = int(
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

                            "price": (
                                f"{your_price} DH"
                            ),

                            "original_price": (
                                f"{int(base_price)} DH"
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
                    f"⚠️ خطأ في اكتشاف "
                    f"البطاقات: {e}"
                )

    except Exception as e:

        print(
            f"⚠️ خطأ في الصفحة: {e}"
        )

    new_products = (
        len(all_products)
        - before_count
    )

    return all_products, new_products


# =========================================================
# MAIN
# =========================================================

def run_automation():

    if not EMAIL or not PASSWORD:

        raise RuntimeError(
            "BOUGHAL_EMAIL / "
            "BOUGHAL_PASSWORD غير موجودين."
        )

    with sync_playwright() as p:

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
                "Chrome/122.0.0.0 Safari/537.36"
            ),

            locale="fr-FR"
        )

        page = context.new_page()

        # =====================================================
        # LOGIN — نفس الكود اللي كان خدام
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
        email_input.fill(EMAIL)

        password_input = page.locator(
            "input[type='password'], "
            "input[name='password']"
        ).first

        password_input.focus()
        password_input.fill(PASSWORD)

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
                "⚠️ استعمال Enter..."
            )

            page.keyboard.press(
                "Enter"
            )

        time.sleep(8)

        print(
            "✅ Login terminé."
        )

        print(
            f"🌐 URL actuelle: "
            f"{page.url}"
        )

        # =====================================================
        # PRODUCTS
        # =====================================================

        print(
            "🛍️ [4/4] الدخول للمنتجات..."
        )

        all_products = []

        empty_pages = 0

        for page_number in range(
            1,
            MAX_PAGES + 1
        ):

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
                f"📄 PAGE {page_number}"
            )

            print(
                f"🔗 {url}"
            )

            print("=" * 70)

            try:

                page.goto(
                    url,
                    wait_until="domcontentloaded",
                    timeout=30000
                )

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

                # تشخيص
                print(
                    f"🌐 Current URL: "
                    f"{page.url}"
                )

                print(
                    f"🔗 A links: "
                    f"{page.locator('a').count()}"
                )

                # حفظ source للصفحة
                if page_number == 1:

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
                            "💾 source.html saved"
                        )

                    except Exception as e:

                        print(
                            f"⚠️ source.html: {e}"
                        )

                before = len(
                    all_products
                )

                all_products, new_count = (
                    scrape_current_page(
                        page,
                        all_products
                    )
                )

                print(
                    f"📦 منتجات جديدة: "
                    f"{new_count}"
                )

                print(
                    f"📊 الإجمالي: "
                    f"{len(all_products)}"
                )

                # حفظ مؤقت
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

                if new_count == 0:

                    empty_pages += 1

                    print(
                        f"⚠️ صفحة فارغة "
                        f"{empty_pages}/"
                        f"{MAX_EMPTY_PAGES}"
                    )

                else:

                    empty_pages = 0

                if (
                    empty_pages
                    >= MAX_EMPTY_PAGES
                ):

                    print(
                        "🛑 نهاية pagination."
                    )

                    break

            except Exception as e:

                print(
                    f"⚠️ PAGE ERROR: {e}"
                )

                break

        # =====================================================
        # DETAILS
        # =====================================================

        print("")
        print("=" * 70)

        print(
            f"🔍 استخراج تفاصيل "
            f"{len(all_products)} منتج..."
        )

        print("=" * 70)

        for index, product in enumerate(
            all_products,
            start=1
        ):

            print("")
            print(
                f"📦 [{index}/"
                f"{len(all_products)}] "
                f"{product.get('title', '')}"
            )

            scrape_product_details(
                context,
                product
            )

            # حفظ بعد كل منتج
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
                "title",
                ""
            )

            product.setdefault(
                "image",
                ""
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
                "price",
                ""
            )

            product.setdefault(
                "original_price",
                ""
            )

            product.setdefault(
                "original_link",
                ""
            )

            product.setdefault(
                "status",
                "In Stock"
            )

            product["images"] = (
                unique_list(
                    product["images"]
                )
            )

            product["videos"] = (
                unique_list(
                    product["videos"]
                )
            )

            product["sizes"] = (
                unique_list(
                    product["sizes"]
                )
            )

            product["colors"] = (
                unique_list(
                    product["colors"]
                )
            )

            if (
                not product["image"]
                and product["images"]
            ):

                product["image"] = (
                    product["images"][0]
                )

        # =====================================================
        # FINAL SAVE
        # =====================================================

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

        # =====================================================
        # FINAL SOURCE
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

        except Exception:
            pass

        print("")
        print("=" * 70)

        print(
            "🎉 اكتمل التحديث!"
        )

        print(
            f"📦 المنتجات: "
            f"{len(all_products)}"
        )

        print(
            "💾 products.json"
        )

        print(
            "💾 source.html"
        )

        print("=" * 70)

        browser.close()


if __name__ == "__main__":
    run_automation()

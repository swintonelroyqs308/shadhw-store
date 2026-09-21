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

MAX_PAGES = 1000
MAX_EMPTY_PAGES = 2

OUTPUT_FILE = "products.json"
SOURCE_FILE = "source.html"


# =========================================================
# HELPERS
# =========================================================

def clean_text(value):
    if value is None:
        return ""

    value = str(value)
    value = value.replace("\xa0", " ")
    value = re.sub(r"\s+", " ", value)

    return value.strip()


def absolute_url(url):
    if not url:
        return ""

    url = str(url).strip()

    if not url:
        return ""

    if url.startswith("data:"):
        return ""

    if url.startswith("blob:"):
        return ""

    return urljoin(BASE_URL, url)


def unique_list(items):
    result = []
    seen = set()

    for item in items:
        if not item:
            continue

        item = str(item).strip()

        if not item:
            continue

        if item not in seen:
            seen.add(item)
            result.append(item)

    return result


# =========================================================
# PRICE
# =========================================================

def extract_price(text):
    if not text:
        return None

    text = str(text)

    patterns = [
        r"(\d+(?:[.,]\d{1,2})?)\s*(?:DH|MAD|درهم)",
        r"(?:DH|MAD|درهم)\s*(\d+(?:[.,]\d{1,2})?)",
        r"(\d+(?:[.,]\d{1,2})?)"
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)

        if match:
            value = match.group(1)

            try:
                return float(value.replace(",", "."))
            except Exception:
                pass

    return None


def format_price(value):
    if value is None:
        return ""

    try:
        value = float(value)

        if value.is_integer():
            return str(int(value))

        return f"{value:.2f}".rstrip("0").rstrip(".")

    except Exception:
        return str(value)


def extract_revendeur_price(text):
    if not text:
        return None

    text = str(text)

    patterns = [
        r"revendeur\s*[:\-]?\s*(\d+(?:[.,]\d{1,2})?)",
        r"prix\s+revendeur\s*[:\-]?\s*(\d+(?:[.,]\d{1,2})?)",
        r"prix\s+de\s+revendeur\s*[:\-]?\s*(\d+(?:[.,]\d{1,2})?)",
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)

        if match:
            try:
                return float(match.group(1).replace(",", "."))
            except Exception:
                pass

    return None


# =========================================================
# HTML HELPERS
# =========================================================

def get_attr(locator, attr):
    try:
        value = locator.get_attribute(attr)

        if value:
            return value.strip()

    except Exception:
        pass

    return ""


def get_inner_text(locator):
    try:
        return clean_text(locator.inner_text())
    except Exception:
        return ""


# =========================================================
# IMAGE EXTRACTION
# =========================================================

def extract_real_image_url(img):
    candidates = []

    # currentSrc
    try:
        current_src = img.evaluate(
            "(el) => el.currentSrc || ''"
        )

        if current_src:
            candidates.append(current_src)

    except Exception:
        pass

    # normal/lazy attributes
    attributes = [
        "src",
        "data-src",
        "data-lazy-src",
        "data-original",
        "data-image",
        "data-full",
        "data-large",
        "data-zoom",
        "data-url",
    ]

    for attr in attributes:
        value = get_attr(img, attr)

        if value:
            candidates.append(value)

    # srcset
    srcset = get_attr(img, "srcset")

    if srcset:
        parts = []

        for item in srcset.split(","):
            item = item.strip()

            if not item:
                continue

            url = item.split()[0]

            if url:
                parts.append(url)

        candidates.extend(reversed(parts))

    bad_words = [
        "placeholder",
        "loading",
        "loader",
        "spinner",
        "blank",
        "default-image",
        "default_image",
        "no-image",
        "no_image",
    ]

    for candidate in candidates:

        candidate = candidate.strip()

        if not candidate:
            continue

        lower = candidate.lower()

        if lower.startswith("data:"):
            continue

        if lower.startswith("blob:"):
            continue

        if any(word in lower for word in bad_words):
            continue

        return absolute_url(candidate)

    return ""


def extract_product_page_images(page):
    images = []

    # -----------------------------------------------------
    # IMG
    # -----------------------------------------------------

    try:
        img_locators = page.locator("img").all()

        for img in img_locators:

            url = extract_real_image_url(img)

            if url:
                images.append(url)

    except Exception as e:
        print(f"⚠️ خطأ في استخراج img: {e}")

    # -----------------------------------------------------
    # background-image
    # -----------------------------------------------------

    try:
        elements = page.locator(
            "[style*='background-image']"
        ).all()

        for element in elements:

            try:
                style = get_attr(element, "style")

                if not style:
                    continue

                matches = re.findall(
                    r"url\([\"']?(.*?)[\"']?\)",
                    style,
                    re.IGNORECASE
                )

                for match in matches:

                    url = absolute_url(match)

                    if url:
                        images.append(url)

            except Exception:
                continue

    except Exception:
        pass

    # -----------------------------------------------------
    # image links
    # -----------------------------------------------------

    try:
        links = page.locator("a[href]").all()

        for link in links:

            href = get_attr(link, "href")

            if not href:
                continue

            lower = href.lower()

            if any(
                ext in lower
                for ext in [
                    ".jpg",
                    ".jpeg",
                    ".png",
                    ".webp",
                    ".gif",
                    ".avif"
                ]
            ):
                images.append(absolute_url(href))

    except Exception:
        pass

    return unique_list(images)


# =========================================================
# VIDEO EXTRACTION
# =========================================================

def extract_videos(page):
    videos = []

    try:
        video_locators = page.locator("video").all()

        for video in video_locators:

            src = get_attr(video, "src")

            if src:
                videos.append(absolute_url(src))

            try:
                sources = video.locator("source").all()

                for source in sources:

                    src = get_attr(source, "src")

                    if src:
                        videos.append(
                            absolute_url(src)
                        )

            except Exception:
                pass

    except Exception:
        pass

    try:
        links = page.locator("a[href]").all()

        for link in links:

            href = get_attr(link, "href")

            if href and ".mp4" in href.lower():
                videos.append(
                    absolute_url(href)
                )

    except Exception:
        pass

    return unique_list(videos)


# =========================================================
# DESCRIPTION
# =========================================================

def extract_description(page):
    selectors = [
        ".description",
        "#description",
        ".product-description",
        ".product_description",
        "[class*='description']",
    ]

    for selector in selectors:

        try:
            locators = page.locator(selector).all()

            for locator in locators:

                text = get_inner_text(locator)

                if text and len(text) > 20:
                    return text

        except Exception:
            continue

    try:
        headings = page.locator(
            "h1, h2, h3, h4, h5"
        ).all()

        for heading in headings:

            heading_text = get_inner_text(
                heading
            )

            if "description" not in heading_text.lower():
                continue

            try:
                parent = heading.locator(
                    "xpath=.."
                )

                text = get_inner_text(parent)

                if (
                    text
                    and len(text) > len(heading_text)
                ):
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

    selectors = [
        "input[data-size]",
        "[data-size]",
        "button[data-size]",
        "[class*='size'] button",
        "[class*='size'] label",
        "[class*='sizes'] button",
        "[class*='sizes'] label",
    ]

    for selector in selectors:

        try:
            locators = page.locator(selector).all()

            for locator in locators:

                try:
                    value = (
                        get_attr(locator, "data-size")
                        or get_attr(locator, "value")
                        or get_inner_text(locator)
                    )

                    value = clean_text(value)

                    if value:
                        sizes.append(value)

                except Exception:
                    continue

        except Exception:
            continue

    # SELECT OPTIONS — المقاسات فقط
    try:
        selects = page.locator("select").all()

        for select in selects:

            try:
                metadata = " ".join([
                    get_attr(select, "name"),
                    get_attr(select, "id"),
                    get_attr(select, "class"),
                    get_attr(select, "data-size"),
                ]).lower()

                if (
                    "size" not in metadata
                    and "taille" not in metadata
                    and "مقاس" not in metadata
                ):
                    continue

                options = select.locator("option").all()

                for option in options:

                    try:
                        value = (
                            get_attr(option, "value")
                            or get_inner_text(option)
                        )

                        value = clean_text(value)

                        if value:
                            sizes.append(value)

                    except Exception:
                        continue

            except Exception:
                continue

    except Exception:
        pass

    return unique_list(sizes)


# =========================================================
# STATUS
# =========================================================

def extract_status(page):
    try:
        text = get_inner_text(
            page.locator("body")
        )
    except Exception:
        return ""

    lower = text.lower()

    out_of_stock_words = [
        "rupture de stock",
        "out of stock",
        "épuisé",
        "epuise",
        "indisponible",
        "غير متوفر",
    ]

    in_stock_words = [
        "en stock",
        "in stock",
        "disponible",
        "متوفر",
    ]

    for word in out_of_stock_words:

        if word.lower() in lower:
            return "Out of Stock"

    for word in in_stock_words:

        if word.lower() in lower:
            return "In Stock"

    return ""


# =========================================================
# TITLE
# =========================================================

def extract_title(page, fallback=""):

    bad_titles = {
        "tableau de bord",
        "dashboard",
        "accueil",
        "home",
        "لوحة التحكم",
    }

    # product-specific selectors FIRST
    selectors = [
        ".product-title",
        "[class*='product-title']",
        ".product_name",
        ".product-name",
        "[class*='product_name']",
        "[class*='product-name']",
    ]

    for selector in selectors:

        try:
            locators = page.locator(
                selector
            ).all()

            for locator in locators:

                text = get_inner_text(
                    locator
                )

                if not text:
                    continue

                if text.lower() in bad_titles:
                    continue

                if len(text) > 1:
                    return text

        except Exception:
            continue

    # h1 / h2
    try:
        locators = page.locator(
            "h1, h2"
        ).all()

        for locator in locators:

            text = get_inner_text(
                locator
            )

            if not text:
                continue

            if text.lower() in bad_titles:
                continue

            if len(text) > 1:
                return text

    except Exception:
        pass

    fallback = clean_text(fallback)

    if (
        fallback
        and fallback.lower() not in bad_titles
    ):
        return fallback

    return ""


# =========================================================
# CARD PRODUCT
# =========================================================

def extract_card_product(card, index):

    title = ""

    # -----------------------------------------------------
    # title
    # -----------------------------------------------------

    try:
        title = get_attr(
            card,
            "data-name"
        )
    except Exception:
        pass

    if not title:

        for selector in [
            "h4",
            "h3",
            "h2",
            ".product-title",
            "[class*='product-title']",
        ]:

            try:
                locator = card.locator(
                    selector
                ).first

                text = get_inner_text(
                    locator
                )

                if text:
                    title = text
                    break

            except Exception:
                continue

    # -----------------------------------------------------
    # link
    # -----------------------------------------------------

    original_link = get_attr(
        card,
        "data-url"
    )

    if not original_link:

        try:
            links = card.locator(
                "a[href]"
            ).all()

            for link in links:

                href = get_attr(
                    link,
                    "href"
                )

                if href:
                    original_link = href
                    break

        except Exception:
            pass

    original_link = absolute_url(
        original_link
    )

    # -----------------------------------------------------
    # source ID
    # -----------------------------------------------------

    source_id = get_attr(
        card,
        "data-id"
    )

    # -----------------------------------------------------
    # card text
    # -----------------------------------------------------

    card_text = get_inner_text(card)

    # -----------------------------------------------------
    # revendeur price
    # -----------------------------------------------------

    original_price_value = (
        extract_revendeur_price(
            card_text
        )
    )

    if original_price_value is None:

        try:
            elements = card.locator(
                "p, span, div"
            ).all()

            for element in elements:

                text = get_inner_text(
                    element
                )

                if "revendeur" not in text.lower():
                    continue

                price = extract_price(text)

                if price is not None:
                    original_price_value = price
                    break

        except Exception:
            pass

    # -----------------------------------------------------
    # status
    # -----------------------------------------------------

    status = ""

    lower_card_text = card_text.lower()

    if (
        "rupture de stock" in lower_card_text
        or "out of stock" in lower_card_text
        or "épuisé" in lower_card_text
        or "epuise" in lower_card_text
        or "indisponible" in lower_card_text
        or "غير متوفر" in lower_card_text
    ):
        status = "Out of Stock"

    elif (
        "en stock" in lower_card_text
        or "in stock" in lower_card_text
        or "disponible" in lower_card_text
        or "متوفر" in lower_card_text
    ):
        status = "In Stock"

    # -----------------------------------------------------
    # product
    # -----------------------------------------------------

    product = {
        "id": f"shadhw_{index}",
        "source_id": source_id,
        "title": clean_text(title),
        "image": "",
        "images": [],
        "videos": [],
        "description": "",
        "sizes": [],
        "price": (
            format_price(
                original_price_value
                + PROFIT_MARGIN
            )
            if original_price_value is not None
            else ""
        ),
        "original_price": format_price(
            original_price_value
        ),
        "original_link": original_link,
        "status": status,
    }

    return product


# =========================================================
# PRODUCT DETAILS
# =========================================================

def scrape_product_details(
    context,
    product,
    index,
    total
):

    url = product.get(
        "original_link",
        ""
    )

    if not url:

        print(
            f"⚠️ [{index}/{total}] "
            f"لا يوجد رابط للمنتج"
        )

        return product

    print(
        f"\n🔎 [{index}/{total}] "
        f"{product.get('title', '')}"
    )

    print(
        f"🔗 {url}"
    )

    page = None

    try:

        page = context.new_page()

        # -------------------------------------------------
        # فتح صفحة المنتج
        # -------------------------------------------------

        page.goto(
            url,
            wait_until="domcontentloaded",
            timeout=60000
        )

        try:

            page.wait_for_load_state(
                "networkidle",
                timeout=15000
            )

        except Exception:
            pass

        page.wait_for_timeout(2500)

        print(
            f"🌐 URL النهائي: {page.url}"
        )

        # -------------------------------------------------
        # إذا حدث redirect إلى dashboard
        # -------------------------------------------------

        final_url = page.url.lower()

        if (
            "/affiliate/dashboard"
            in final_url
        ):

            print(
                "⛔ تم تحويل المنتج إلى dashboard."
                " لن نأخذ dashboard كصفحة المنتج."
            )

            return product

        # -------------------------------------------------
        # lazy loading
        # -------------------------------------------------

        try:

            for _ in range(6):

                page.mouse.wheel(
                    0,
                    1200
                )

                page.wait_for_timeout(
                    500
                )

            page.mouse.wheel(
                0,
                -800
            )

            page.wait_for_timeout(
                1000
            )

        except Exception:
            pass

        # -------------------------------------------------
        # title
        # -------------------------------------------------

        extracted_title = extract_title(
            page,
            product.get(
                "title",
                ""
            )
        )

        if extracted_title:

            product["title"] = (
                extracted_title
            )

        # -------------------------------------------------
        # images
        # -------------------------------------------------

        images = extract_product_page_images(
            page
        )

        if images:

            product["images"] = images
            product["image"] = images[0]

            print(
                f"🖼️ الصور: {len(images)}"
            )

        else:

            print(
                "⚠️ لم يتم العثور على صور"
            )

        # -------------------------------------------------
        # videos
        # -------------------------------------------------

        videos = extract_videos(
            page
        )

        if videos:

            product["videos"] = videos

            print(
                f"🎥 الفيديوهات: {len(videos)}"
            )

        # -------------------------------------------------
        # description
        # -------------------------------------------------

        description = extract_description(
            page
        )

        if description:

            product["description"] = (
                description
            )

            print(
                "📝 تم استخراج الوصف"
            )

        else:

            print(
                "⚠️ لم يتم العثور على الوصف"
            )

        # -------------------------------------------------
        # sizes
        # -------------------------------------------------

        sizes = extract_sizes(
            page
        )

        if sizes:

            product["sizes"] = sizes

            print(
                f"📏 المقاسات: {', '.join(sizes)}"
            )

        # -------------------------------------------------
        # status
        # -------------------------------------------------

        status = extract_status(
            page
        )

        if status:
            product["status"] = status

        # -------------------------------------------------
        # revendeur price
        # -------------------------------------------------

        page_text = get_inner_text(
            page.locator("body")
        )

        original_price_value = (
            extract_revendeur_price(
                page_text
            )
        )

        if original_price_value is not None:

            product["original_price"] = (
                format_price(
                    original_price_value
                )
            )

            product["price"] = (
                format_price(
                    original_price_value
                    + PROFIT_MARGIN
                )
            )

            print(
                f"💰 Revendeur: "
                f"{product['original_price']}"
            )

            print(
                f"💰 Prix البيع: "
                f"{product['price']}"
            )

        # -------------------------------------------------
        # debug
        # -------------------------------------------------

        try:

            with open(
                "product_debug.html",
                "w",
                encoding="utf-8"
            ) as f:

                f.write(
                    page.content()
                )

        except Exception as e:

            print(
                f"⚠️ تعذر حفظ "
                f"product_debug.html: {e}"
            )

        return product

    except Exception as e:

        print(
            f"❌ خطأ في المنتج "
            f"{product.get('title', '')}: {e}"
        )

        return product

    finally:

        if page:

            try:
                page.close()
            except Exception:
                pass


# =========================================================
# SAVE
# =========================================================

def save_products(products):

    try:

        with open(
            OUTPUT_FILE,
            "w",
            encoding="utf-8"
        ) as f:

            json.dump(
                products,
                f,
                ensure_ascii=False,
                indent=2
            )

        print(
            f"💾 تم حفظ {len(products)} "
            f"منتج في {OUTPUT_FILE}"
        )

    except Exception as e:

        print(
            f"❌ خطأ أثناء حفظ المنتجات: {e}"
        )


# =========================================================
# DELETE PRODUCTS BY SOURCE_ID
# =========================================================

SOURCE_IDS_TO_DELETE = {
    "190",
    "146",
    "117",
    "163",
    "294",
    "151",
    "290",
    "292",
    "202",
    "130",
    "90",
    "71",
    "72",
    "70",
    "297",
}


def delete_products_by_source_id():

    try:

        # -------------------------------------------------
        # قراءة products.json
        # -------------------------------------------------

        with open(
            OUTPUT_FILE,
            "r",
            encoding="utf-8"
        ) as f:

            products = json.load(f)

        if not isinstance(products, list):

            print(
                "⚠️ products.json لا يحتوي على قائمة منتجات."
            )

            return

        original_count = len(products)

        # -------------------------------------------------
        # حذف المنتجات التي source_id ديالها مطابق
        # -------------------------------------------------

        filtered_products = []

        deleted = []

        for product in products:

            source_id = str(
                product.get("source_id", "")
            ).strip()

            if source_id in SOURCE_IDS_TO_DELETE:

                deleted.append(source_id)

                print(
                    f"🗑️ حذف المنتج: "
                    f"{product.get('title', '')} "
                    f"| source_id: {source_id}"
                )

            else:

                filtered_products.append(product)

        # -------------------------------------------------
        # حفظ الملف
        # -------------------------------------------------

        with open(
            OUTPUT_FILE,
            "w",
            encoding="utf-8"
        ) as f:

            json.dump(
                filtered_products,
                f,
                ensure_ascii=False,
                indent=2
            )

        print(
            f"🗑️ تم حذف {len(deleted)} منتج."
        )

        print(
            f"📦 قبل الحذف: {original_count}"
        )

        print(
            f"📦 بعد الحذف: {len(filtered_products)}"
        )

        # -------------------------------------------------
        # source_id غير الموجودة
        # -------------------------------------------------

        found_ids = set(deleted)

        not_found = (
            SOURCE_IDS_TO_DELETE
            - found_ids
        )

        if not_found:

            print(
                "ℹ️ source_id غير الموجودة "
                "ولم يتم حذف أي منتج بها:"
            )

            for source_id in sorted(
                not_found,
                key=lambda x: int(x)
            ):

                print(
                    f"   - {source_id}"
                )

    except Exception as e:

        print(
            f"❌ خطأ أثناء حذف المنتجات: {e}"
        )

# =========================================================
# LOGIN
# =========================================================

def login(page):

    print("🔐 تسجيل الدخول...")

    page.goto(
        BASE_URL,
        wait_until="domcontentloaded",
        timeout=60000
    )

    # إذا لم نكن في صفحة login
    if "/login" not in page.url.lower():

        login_link = None

        for selector in [
            "a[href*='login']",
            "a[href*='connexion']"
        ]:

            try:

                locator = page.locator(
                    selector
                ).first

                if locator.count() > 0:

                    login_link = locator
                    break

            except Exception:
                pass

        if login_link:

            try:

                login_link.click()

                page.wait_for_load_state(
                    "domcontentloaded",
                    timeout=30000
                )

            except Exception:
                pass

    # -----------------------------------------------------
    # email
    # -----------------------------------------------------

    email_input = None

    for selector in [
        "input[type='email']",
        "input[name='email']",
        "input[name='username']"
    ]:

        try:

            locator = page.locator(
                selector
            ).first

            if locator.count() > 0:

                email_input = locator
                break

        except Exception:
            pass

    # -----------------------------------------------------
    # password
    # -----------------------------------------------------

    password_input = None

    for selector in [
        "input[type='password']",
        "input[name='password']"
    ]:

        try:

            locator = page.locator(
                selector
            ).first

            if locator.count() > 0:

                password_input = locator
                break

        except Exception:
            pass

    # -----------------------------------------------------
    # إذا كانت الجلسة مسجلة بالفعل
    # -----------------------------------------------------

    if not email_input or not password_input:

        if "/login" not in page.url.lower():

            print(
                "✅ الجلسة مسجلة الدخول بالفعل."
            )

            return True

        print(
            "❌ لم يتم العثور على حقول تسجيل الدخول."
        )

        return False

    if not EMAIL or not PASSWORD:

        print(
            "❌ BOUGHAL_EMAIL أو "
            "BOUGHAL_PASSWORD غير موجودين."
        )

        return False

    # -----------------------------------------------------
    # fill
    # -----------------------------------------------------

    email_input.fill(
        EMAIL
    )

    password_input.fill(
        PASSWORD
    )

    # -----------------------------------------------------
    # submit
    # -----------------------------------------------------

    submitted = False

    for selector in [
        "button[type='submit']",
        "input[type='submit']"
    ]:

        try:

            button = page.locator(
                selector
            ).first

            if button.count() > 0:

                button.click()

                submitted = True
                break

        except Exception:
            pass

    if not submitted:

        try:

            password_input.press(
                "Enter"
            )

            submitted = True

        except Exception:
            pass

    # -----------------------------------------------------
    # wait
    # -----------------------------------------------------

    if submitted:

        try:

            page.wait_for_load_state(
                "domcontentloaded",
                timeout=30000
            )

        except Exception:
            pass

        try:

            page.wait_for_load_state(
                "networkidle",
                timeout=15000
            )

        except Exception:
            pass

        page.wait_for_timeout(
            3000
        )

    print(
        f"🌐 URL بعد تسجيل الدخول: "
        f"{page.url}"
    )

    if "/login" in page.url.lower():

        print(
            "❌ فشل تسجيل الدخول."
        )

        return False

    print(
        "✅ تم تسجيل الدخول بنجاح."
    )

    return True


# =========================================================
# SCRAPE CURRENT PAGE
# =========================================================

def scrape_current_page(
    page,
    products
):

    print(
        f"\n🔎 استخراج المنتجات من:"
        f" {page.url}"
    )

    # -----------------------------------------------------
    # source.html
    # -----------------------------------------------------

    try:

        with open(
            SOURCE_FILE,
            "w",
            encoding="utf-8"
        ) as f:

            f.write(
                page.content()
            )

    except Exception as e:

        print(
            f"⚠️ تعذر حفظ source.html: {e}"
        )

    # -----------------------------------------------------
    # cards
    # -----------------------------------------------------

    try:

        cards = page.locator(
            "div.productCard[data-url]"
        ).all()

    except Exception as e:

        print(
            f"❌ خطأ في العثور على "
            f"product cards: {e}"
        )

        return 0

    print(
        f"📦 عدد المنتجات في الصفحة: "
        f"{len(cards)}"
    )

    existing_links = {
        p.get("original_link")
        for p in products
        if p.get("original_link")
    }

    added = 0
    skipped = 0

    # =====================================================
    # LOOP
    # =====================================================

    for index, card in enumerate(
        cards,
        start=1
    ):

        # -------------------------------------------------
        # النص الكامل للبطاقة
        # -------------------------------------------------

        try:

            card_text = clean_text(
                card.inner_text()
            )

        except Exception:

            card_text = ""

        # =================================================
        # أهم تعديل:
        # نفحص "غير متوفر حاليا" داخل البطاقة
        # قبل فتح الرابط
        # =================================================

        if "غير متوفر حاليا" in card_text:

            title_preview = ""

            try:

                title_preview = (
                    get_attr(
                        card,
                        "data-name"
                    )
                    or get_inner_text(
                        card.locator(
                            "h4"
                        ).first
                    )
                    or get_inner_text(
                        card.locator(
                            "h3"
                        ).first
                    )
                )

            except Exception:
                pass

            title_preview = clean_text(
                title_preview
            )

            print(
                f"⏭️ [{index}/{len(cards)}] "
                f"تخطي: غير متوفر حاليا"
                f" | {title_preview}"
            )

            skipped += 1

            # مهم جداً:
            # لا نفتح original_link
            continue

        # -------------------------------------------------
        # استخراج المنتج
        # -------------------------------------------------

        product = extract_card_product(
            card,
            index
        )

        if not product:

            print(
                f"⚠️ [{index}] "
                f"تعذر استخراج المنتج."
            )

            continue

        link = product.get(
            "original_link",
            ""
        )

        title = product.get(
            "title",
            ""
        )

        # -------------------------------------------------
        # بدون رابط
        # -------------------------------------------------

        if not link:

            print(
                f"⚠️ [{index}] "
                f"لا يوجد رابط: {title}"
            )

            continue

        # -------------------------------------------------
        # duplicate
        # -------------------------------------------------

        if link in existing_links:

            print(
                f"⏭️ [{index}] "
                f"موجود مسبقاً: {title}"
            )

            continue

        # -------------------------------------------------
        # متوفر
        # -------------------------------------------------

        print(
            f"✅ [{index}/{len(cards)}] "
            f"متوفر: {title}"
        )

        print(
            f"🔗 {link}"
        )

        products.append(
            product
        )

        existing_links.add(
            link
        )

        added += 1

    print(
        f"\n📊 تمت إضافة: {added}"
    )

    print(
        f"⏭️ تم تخطي غير المتوفر: {skipped}"
    )

    print(
        f"📦 الإجمالي: {len(products)}"
    )

    return added


# =========================================================
# MAIN
# =========================================================

def main():

    print("=" * 70)
    print(
        "🚀 BOUGHAL AFFILIATE PRODUCT SYNC"
    )
    print("=" * 70)

    products = []

    with sync_playwright() as p:

        browser = None
        context = None

        try:

            # -------------------------------------------------
            # Browser
            # -------------------------------------------------

            browser = p.chromium.launch(
                headless=True
            )

            context = browser.new_context(
                viewport={
                    "width": 1440,
                    "height": 900
                }
            )

            page = context.new_page()

            # -------------------------------------------------
            # LOGIN
            # -------------------------------------------------

            if not login(page):

                print(
                    "❌ فشل تسجيل الدخول."
                )

                return

            # -------------------------------------------------
            # PRODUCTS PAGE
            # -------------------------------------------------

            page.goto(
                BASE_PRODUCTS_URL,
                wait_until="domcontentloaded",
                timeout=60000
            )

            try:

                page.wait_for_load_state(
                    "networkidle",
                    timeout=15000
                )

            except Exception:
                pass

            page.wait_for_timeout(
                2500
            )

            # -------------------------------------------------
            # PAGINATION
            # -------------------------------------------------

            empty_pages = 0

            for page_number in range(
                1,
                MAX_PAGES + 1
            ):

                page_url = (
                    f"{BASE_PRODUCTS_URL}"
                    f"?page={page_number}"
                )

                print("\n")
                print("=" * 70)
                print(
                    f"📄 PAGE {page_number}"
                )
                print("=" * 70)

                try:

                    page.goto(
                        page_url,
                        wait_until="domcontentloaded",
                        timeout=60000
                    )

                except Exception as e:

                    print(
                        f"⚠️ خطأ عند فتح "
                        f"الصفحة {page_number}: {e}"
                    )

                    continue

                try:

                    page.wait_for_load_state(
                        "networkidle",
                        timeout=15000
                    )

                except Exception:
                    pass

                page.wait_for_timeout(
                    2000
                )

                # -------------------------------------------------
                # cards count
                # -------------------------------------------------

                try:

                    card_count = page.locator(
                        "div.productCard[data-url]"
                    ).count()

                except Exception:

                    card_count = 0

                print(
                    f"📦 Cards: {card_count}"
                )

                # -------------------------------------------------
                # empty page
                # -------------------------------------------------

                if card_count == 0:

                    empty_pages += 1

                    print(
                        f"⚠️ صفحة فارغة "
                        f"({empty_pages}/"
                        f"{MAX_EMPTY_PAGES})"
                    )

                    if (
                        empty_pages
                        >= MAX_EMPTY_PAGES
                    ):

                        print(
                            "🛑 تم الوصول إلى "
                            "الحد الأقصى للصفحات الفارغة."
                        )

                        break

                    continue

                empty_pages = 0

                # -------------------------------------------------
                # extract
                # -------------------------------------------------

                before_count = len(
                    products
                )

                scrape_current_page(
                    page,
                    products
                )

                after_count = len(
                    products
                )

                print(
                    f"📊 منتجات جديدة: "
                    f"{after_count - before_count}"
                )

                # -------------------------------------------------
                # save
                # -------------------------------------------------

                save_products(
                    products
                )

            # =====================================================
            # PRODUCT DETAILS
            # =====================================================

            print("\n")
            print("=" * 70)
            print(
                f"🔎 بدء استخراج تفاصيل "
                f"{len(products)} منتج"
            )
            print("=" * 70)

            total_products = len(
                products
            )

            for index, product in enumerate(
                products,
                start=1
            ):

                product = scrape_product_details(
                    context,
                    product,
                    index,
                    total_products
                )

                product["id"] = (
                    f"shadhw_{index}"
                )

                save_products(
                    products
                )

                print(
                    f"💾 تم حفظ "
                    f"{index}/{total_products}"
                )

                time.sleep(0.5)

            # -------------------------------------------------
            # final save
            # -------------------------------------------------

            save_products(
                products
            )

            # =====================================================
            # DELETE SPECIFIED PRODUCTS AFTER COMPLETE EXTRACTION
            # =====================================================
            
            delete_products_by_source_id()

            print("\n")
            print("=" * 70)
            print(
                "✅ انتهى الاستخراج"
            )
            
            with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
                final_products = json.load(f)
            
            print(
                f"📦 إجمالي المنتجات: "
                f"{len(final_products)}"
            )
            
            print("=" * 70)

        except Exception as e:

            print(
                f"\n❌ خطأ عام: {e}"
            )

            try:
                save_products(
                    products
                )
            except Exception:
                pass

        finally:

            if context:

                try:
                    context.close()
                except Exception:
                    pass

            if browser:

                try:
                    browser.close()
                except Exception:
                    pass


# =========================================================
# RUN
# =========================================================

if __name__ == "__main__":
    main()

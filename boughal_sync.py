import os
import json
import time
import re
from urllib.parse import urljoin
from playwright.sync_api import sync_playwright


# ============================================================
# CONFIG
# ============================================================

EMAIL = os.environ.get("BOUGHAL_EMAIL")
PASSWORD = os.environ.get("BOUGHAL_PASSWORD")

BASE_URL = "https://boughalaffiliate.com"
BASE_PRODUCTS_URL = f"{BASE_URL}/affiliate/products"

PROFIT_MARGIN = 100

MAX_PAGES = 1000
MAX_EMPTY_PAGES = 2

OUTPUT_FILE = "products.json"
SOURCE_FILE = "source.html"


# ============================================================
# HELPERS
# ============================================================

def clean_text(value):
    if not value:
        return ""
    return " ".join(str(value).split()).strip()


def absolute_url(url, base=BASE_URL):
    if not url:
        return ""

    url = str(url).strip()

    if not url:
        return ""

    if url.startswith("data:"):
        return ""

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


def extract_price(text):
    if not text:
        return None

    text = clean_text(text)

    patterns = [
        r'(\d+(?:[.,]\d{1,2})?)\s*(?:DH|dh|MAD|mad)',
        r'(?:DH|dh|MAD|mad)\s*(\d+(?:[.,]\d{1,2})?)',
        r'(\d+(?:[.,]\d{1,2})?)\s*د\.?\s*م',
        r'(\d+(?:[.,]\d{1,2})?)\s*(?:درهم|درهما|درهمًا)',
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)

        if match:
            try:
                return float(match.group(1).replace(",", "."))
            except Exception:
                pass

    return None


def format_price(value):
    if value is None:
        return ""

    if float(value).is_integer():
        return f"{int(value)} DH"

    return f"{value:.2f} DH"


def extract_revendeur_price(text):
    if not text:
        return None

    text = clean_text(text)

    patterns = [
        r'prix\s+revendeur\s*[:\-]?\s*(\d+(?:[.,]\d{1,2})?)',
        r'prix\s+revendeur.{0,100}?(\d+(?:[.,]\d{1,2})?)',
        r'revendeur\s*[:\-]?\s*(\d+(?:[.,]\d{1,2})?)',
        r'revendeur.{0,100}?(\d+(?:[.,]\d{1,2})?)',
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)

        if match:
            try:
                return float(match.group(1).replace(",", "."))
            except Exception:
                pass

    return None


def get_attr(locator, attribute):
    try:
        value = locator.get_attribute(attribute)
        return clean_text(value)
    except Exception:
        return ""


def get_inner_text(locator):
    try:
        return clean_text(locator.inner_text())
    except Exception:
        return ""


# ============================================================
# IMAGE EXTRACTION
# ============================================================

def extract_image_url(img):
    attributes = [
        "data-src",
        "data-lazy-src",
        "data-original",
        "data-image",
        "data-url",
        "src",
    ]

    for attr in attributes:
        value = get_attr(img, attr)

        if not value:
            continue

        if value.startswith("data:"):
            continue

        return absolute_url(value)

    # srcset fallback
    srcset = get_attr(img, "srcset")

    if srcset:
        parts = [x.strip() for x in srcset.split(",") if x.strip()]

        if parts:
            last = parts[-1].split(" ")[0].strip()

            if last:
                return absolute_url(last)

    return ""


def extract_images(page_or_locator):
    images = []

    try:
        img_locators = page_or_locator.locator("img").all()

        for img in img_locators:
            url = extract_image_url(img)

            if url:
                images.append(url)

    except Exception:
        pass

    return unique_list(images)


# ============================================================
# VIDEO EXTRACTION
# ============================================================

def extract_videos(page_or_locator):
    videos = []

    try:
        # <video src="">
        for video in page_or_locator.locator("video").all():
            src = get_attr(video, "src")

            if src and not src.startswith("blob:"):
                videos.append(absolute_url(src))

            # <video data-src="">
            for attr in [
                "data-src",
                "data-video",
                "data-url",
            ]:
                value = get_attr(video, attr)

                if value:
                    videos.append(absolute_url(value))

        # <source src="">
        for source in page_or_locator.locator("video source").all():
            src = get_attr(source, "src")

            if src:
                videos.append(absolute_url(src))

            for attr in [
                "data-src",
                "data-video",
            ]:
                value = get_attr(source, attr)

                if value:
                    videos.append(absolute_url(value))

        # Any mp4 links in the page
        for locator in page_or_locator.locator(
            '[href*=".mp4"], [src*=".mp4"], [data-src*=".mp4"], [data-video*=".mp4"]'
        ).all():

            for attr in [
                "href",
                "src",
                "data-src",
                "data-video",
            ]:
                value = get_attr(locator, attr)

                if value and ".mp4" in value.lower():
                    videos.append(absolute_url(value))

    except Exception:
        pass

    return unique_list(videos)


# ============================================================
# DESCRIPTION
# ============================================================

def extract_description(page):
    descriptions = []

    selectors = [
        "[class*='description']",
        "#description",
        ".description",
        ".product-description",
    ]

    for selector in selectors:
        try:
            for element in page.locator(selector).all():
                text = get_inner_text(element)

                if text and len(text) > 5:
                    descriptions.append(text)
        except Exception:
            pass

    # Search for heading "Description"
    try:
        headings = page.locator("h1, h2, h3, h4, h5, h6").all()

        for heading in headings:
            heading_text = get_inner_text(heading).lower()

            if "description" in heading_text:
                try:
                    parent = heading.locator("..")
                    parent_text = get_inner_text(parent)

                    if parent_text:
                        parent_text = re.sub(
                            r'^\s*description\s*',
                            "",
                            parent_text,
                            flags=re.IGNORECASE
                        )

                        parent_text = clean_text(parent_text)

                        if parent_text:
                            descriptions.append(parent_text)
                except Exception:
                    pass

    except Exception:
        pass

    descriptions = unique_list(descriptions)

    if not descriptions:
        return ""

    # Remove duplicates / very short fragments
    descriptions = [
        x for x in descriptions
        if len(x) >= 5
    ]

    if not descriptions:
        return ""

    return max(descriptions, key=len)


# ============================================================
# SIZES
# ============================================================

def extract_sizes(page):
    sizes = []

    selectors = [
        "input[name='size']",
        "input[name='sizes']",
        "[data-size]",
        ".size-button",
        ".size-btn",
        "button[class*='size']",
        "label[class*='size']",
        "select[name='size'] option",
        "select[name='sizes'] option",
    ]

    for selector in selectors:
        try:
            elements = page.locator(selector).all()

            for element in elements:

                for attr in [
                    "value",
                    "data-size",
                ]:
                    value = get_attr(element, attr)

                    if value:
                        sizes.append(value)

                text = get_inner_text(element)

                if text:
                    sizes.append(text)

        except Exception:
            pass

    # Search common size labels
    try:
        text = get_inner_text(page)

        patterns = [
            r'(?:taille|size)\s*[:\-]?\s*([A-Za-z0-9À-ÿ]+)',
        ]

        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)

            for match in matches:
                if match:
                    sizes.append(match)

    except Exception:
        pass

    sizes = unique_list(sizes)

    # Remove generic words
    ignored = {
        "taille",
        "size",
        "sizes",
        "choisir",
        "select",
        "sélectionner",
    }

    sizes = [
        x for x in sizes
        if x.lower() not in ignored
    ]

    return sizes


# ============================================================
# COLORS
# ============================================================

def extract_colors(page):
    colors = []

    selectors = [
        "[data-color]",
        ".color-button",
        ".color-btn",
        "button[class*='color']",
        "label[class*='color']",
        "input[name='color']",
        "input[name='colors']",
        "select[name='color'] option",
        "select[name='colors'] option",
    ]

    for selector in selectors:
        try:
            elements = page.locator(selector).all()

            for element in elements:

                for attr in [
                    "data-color",
                    "value",
                    "title",
                    "aria-label",
                ]:
                    value = get_attr(element, attr)

                    if value:
                        colors.append(value)

                text = get_inner_text(element)

                if text:
                    colors.append(text)

        except Exception:
            pass

    colors = unique_list(colors)

    ignored = {
        "couleur",
        "color",
        "colors",
        "choisir",
        "select",
        "sélectionner",
    }

    colors = [
        x for x in colors
        if x.lower() not in ignored
    ]

    return colors


# ============================================================
# STATUS
# ============================================================

def extract_status(page):
    text = ""

    try:
        text = get_inner_text(page)
    except Exception:
        pass

    lower = text.lower()

    if (
        "rupture de stock" in lower
        or "out of stock" in lower
        or "épuisé" in lower
        or "epuise" in lower
        or "indisponible" in lower
    ):
        return "Out of Stock"

    if (
        "en stock" in lower
        or "in stock" in lower
        or "disponible" in lower
    ):
        return "In Stock"

    return ""


# ============================================================
# TITLE
# ============================================================

def extract_title(page, fallback=""):
    selectors = [
        "h1",
        "[class*='product-title']",
        ".product-title",
        "h2",
    ]

    for selector in selectors:
        try:
            elements = page.locator(selector).all()

            for element in elements:
                text = get_inner_text(element)

                if text and len(text) > 1:
                    return text
        except Exception:
            pass

    return clean_text(fallback)


# ============================================================
# LISTING CARD
# ============================================================

def extract_card_product(card, index):
    title = get_attr(card, "data-name")

    if not title:
        try:
            title = get_inner_text(card.locator("h4").first)
        except Exception:
            title = ""

    if not title:
        try:
            title = get_inner_text(card.locator("h3").first)
        except Exception:
            title = ""

    original_link = get_attr(card, "data-url")

    if original_link:
        original_link = absolute_url(original_link)

    source_id = get_attr(card, "data-id")

    # -------------------------
    # IMAGES
    # -------------------------

    images = extract_images(card)

    # -------------------------
    # PRICE
    # -------------------------

    card_text = get_inner_text(card)

    original_price_value = extract_revendeur_price(card_text)

    if original_price_value is None:
        # Direct search for p containing Revendeur
        try:
            price_elements = card.locator("p").all()

            for element in price_elements:
                text = get_inner_text(element)

                if "revendeur" in text.lower():
                    value = extract_price(text)

                    if value is not None:
                        original_price_value = value
                        break
        except Exception:
            pass

    # -------------------------
    # STATUS
    # -------------------------

    status = ""

    lower = card_text.lower()

    if (
        "rupture de stock" in lower
        or "out of stock" in lower
        or "épuisé" in lower
        or "epuise" in lower
        or "indisponible" in lower
    ):
        status = "Out of Stock"

    elif (
        "en stock" in lower
        or "in stock" in lower
        or "disponible" in lower
    ):
        status = "In Stock"

    # -------------------------
    # RESULT
    # -------------------------

    product = {
        "id": f"shadhw_{index}",
        "source_id": source_id,
        "title": clean_text(title),
        "image": images[0] if images else "",
        "images": images,
        "videos": [],
        "description": "",
        "sizes": [],
        "colors": [],
        "price": format_price(
            original_price_value + PROFIT_MARGIN
        ) if original_price_value is not None else "",
        "original_price": format_price(original_price_value),
        "original_link": original_link,
        "status": status,
    }

    return product


# ============================================================
# PRODUCT DETAILS
# ============================================================

def scrape_product_details(context, product):
    url = product.get("original_link")

    if not url:
        return product

    page = context.new_page()

    try:
        print(f"   ↳ تفاصيل: {url}")

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

        # Give lazy content time to load
        page.wait_for_timeout(2000)

        # Scroll page to trigger lazy images/videos
        try:
            page.evaluate("""
                async () => {
                    window.scrollTo(0, document.body.scrollHeight);
                    await new Promise(r => setTimeout(r, 1000));
                    window.scrollTo(0, 0);
                }
            """)
        except Exception:
            pass

        page.wait_for_timeout(1500)

        # ====================================================
        # TITLE
        # ====================================================

        title = extract_title(
            page,
            product.get("title", "")
        )

        if title:
            product["title"] = title

        # ====================================================
        # IMAGES
        # ====================================================

        detail_images = extract_images(page)

        product["images"] = unique_list(
            product.get("images", []) +
            detail_images
        )

        if product["images"]:
            product["image"] = product["images"][0]

        # ====================================================
        # VIDEOS
        # ====================================================

        videos = extract_videos(page)

        product["videos"] = unique_list(
            product.get("videos", []) +
            videos
        )

        # ====================================================
        # DESCRIPTION
        # ====================================================

        description = extract_description(page)

        if description:
            product["description"] = description

        # ====================================================
        # SIZES
        # ====================================================

        sizes = extract_sizes(page)

        if sizes:
            product["sizes"] = sizes

        # ====================================================
        # COLORS
        # ====================================================

        colors = extract_colors(page)

        if colors:
            product["colors"] = colors

        # ====================================================
        # STATUS
        # ====================================================

        status = extract_status(page)

        if status:
            product["status"] = status

        # ====================================================
        # REVENDEUR PRICE
        # ====================================================

        page_text = get_inner_text(page)

        original_price_value = extract_revendeur_price(page_text)

        if original_price_value is not None:
            product["original_price"] = format_price(
                original_price_value
            )

            product["price"] = format_price(
                original_price_value + PROFIT_MARGIN
            )

        # ====================================================
        # DEBUG HTML
        # ====================================================

        try:
            with open(
                "product_debug.html",
                "w",
                encoding="utf-8"
            ) as f:
                f.write(page.content())
        except Exception:
            pass

    except Exception as e:
        print(f"   ⚠️ خطأ في تفاصيل المنتج: {e}")

    finally:
        page.close()

    return product


# ============================================================
# SAVE JSON
# ============================================================

def save_products(products):
    with open(
        OUTPUT_FILE,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            products,
            f,
            ensure_ascii=False,
            indent=4
        )


# ============================================================
# LOGIN
# ============================================================

def login(page):
    print("🔐 تسجيل الدخول...")

    page.goto(
        BASE_URL,
        wait_until="domcontentloaded",
        timeout=60000
    )

    page.wait_for_timeout(1500)

    # --------------------------------------------------------
    # Login page detection
    # --------------------------------------------------------

    if "/login" not in page.url.lower():

        # Try common login links
        login_links = [
            "a[href*='login']",
            "a[href*='connexion']",
        ]

        clicked = False

        for selector in login_links:
            try:
                locator = page.locator(selector).first

                if locator.count() > 0:
                    locator.click()
                    page.wait_for_timeout(1500)
                    clicked = True
                    break
            except Exception:
                pass

        if not clicked:
            try:
                page.goto(
                    f"{BASE_URL}/login",
                    wait_until="domcontentloaded",
                    timeout=60000
                )
            except Exception:
                pass

    # --------------------------------------------------------
    # Fill credentials
    # --------------------------------------------------------

    email_selectors = [
        "input[type='email']",
        "input[name='email']",
        "input[name='username']",
    ]

    password_selectors = [
        "input[type='password']",
        "input[name='password']",
    ]

    email_input = None
    password_input = None

    for selector in email_selectors:
        try:
            locator = page.locator(selector).first

            if locator.count() > 0:
                email_input = locator
                break
        except Exception:
            pass

    for selector in password_selectors:
        try:
            locator = page.locator(selector).first

            if locator.count() > 0:
                password_input = locator
                break
        except Exception:
            pass

    if email_input is None or password_input is None:
        print("⚠️ لم يتم العثور على حقول تسجيل الدخول.")
        return False

    if not EMAIL or not PASSWORD:
        print(
            "⚠️ BOUGHAL_EMAIL و BOUGHAL_PASSWORD غير موجودين في Environment."
        )
        return False

    email_input.fill(EMAIL)
    password_input.fill(PASSWORD)

    # --------------------------------------------------------
    # Submit
    # --------------------------------------------------------

    submit_selectors = [
        "button[type='submit']",
        "input[type='submit']",
        "button:has-text('Connexion')",
        "button:has-text('Login')",
        "button:has-text('Se connecter')",
    ]

    submitted = False

    for selector in submit_selectors:
        try:
            button = page.locator(selector).first

            if button.count() > 0:
                button.click()
                submitted = True
                break
        except Exception:
            pass

    if not submitted:
        password_input.press("Enter")

    page.wait_for_timeout(3000)

    try:
        page.wait_for_load_state(
            "networkidle",
            timeout=15000
        )
    except Exception:
        pass

    print(f"🌐 بعد الدخول: {page.url}")

    return True


# ============================================================
# SCRAPE LISTING PAGE
# ============================================================

def scrape_current_page(page, products):
    print(f"📄 الصفحة: {page.url}")

    # Save source
    try:
        with open(
            SOURCE_FILE,
            "w",
            encoding="utf-8"
        ) as f:
            f.write(page.content())
    except Exception:
        pass

    # ========================================================
    # IMPORTANT:
    # REAL PRODUCT CARDS:
    #
    # <div class="productCard"
    #      data-url="..."
    #      data-name="..."
    #      data-id="...">
    #
    # ========================================================

    cards = page.locator(
        "div.productCard[data-url]"
    ).all()

    print(f"🔎 عدد المنتجات الموجودة في الصفحة: {len(cards)}")

    if not cards:
        return 0

    added = 0

    existing_links = {
        p.get("original_link")
        for p in products
        if p.get("original_link")
    }

    for card in cards:

        href = get_attr(card, "data-url")

        if not href:
            continue

        href = absolute_url(href)

        if href in existing_links:
            continue

        product = extract_card_product(
            card,
            len(products) + 1
        )

        if not product.get("original_link"):
            continue

        products.append(product)

        existing_links.add(
            product["original_link"]
        )

        added += 1

        print(
            f"   + {product['title']} | "
            f"Revendeur: {product['original_price']} | "
            f"Vente: {product['price']}"
        )

    return added


# ============================================================
# MAIN
# ============================================================

def main():

    products = []

    with sync_playwright() as p:

        browser = p.chromium.launch(
            headless=False
        )

        context = browser.new_context(
            viewport={
                "width": 1440,
                "height": 900
            }
        )

        page = context.new_page()

        # ====================================================
        # LOGIN
        # ====================================================

        if not login(page):
            browser.close()
            return

        # ====================================================
        # OPEN PRODUCTS
        # ====================================================

        products_url = BASE_PRODUCTS_URL

        page.goto(
            products_url,
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

        page.wait_for_timeout(2000)

        # ====================================================
        # PAGINATION
        # ====================================================

        empty_pages = 0

        for page_number in range(1, MAX_PAGES + 1):

            if page_number == 1:
                url = BASE_PRODUCTS_URL
            else:
                url = (
                    f"{BASE_PRODUCTS_URL}"
                    f"?page={page_number}"
                )

            print()
            print("=" * 70)
            print(f"📄 PAGE {page_number}")
            print("=" * 70)

            try:
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

                page.wait_for_timeout(1500)

            except Exception as e:
                print(f"⚠️ خطأ في فتح الصفحة: {e}")
                continue

            before = len(products)

            added = scrape_current_page(
                page,
                products
            )

            # Save immediately
            save_products(products)

            print(
                f"📦 تمت إضافة: {added} | "
                f"المجموع: {len(products)}"
            )

            if added == 0:
                empty_pages += 1
            else:
                empty_pages = 0

            if empty_pages >= MAX_EMPTY_PAGES:
                print(
                    "🛑 لا توجد منتجات جديدة في الصفحات التالية."
                )
                break

        # ====================================================
        # PRODUCT DETAILS
        # ====================================================

        print()
        print("=" * 70)
        print("🔍 استخراج تفاصيل المنتجات")
        print("=" * 70)

        for index, product in enumerate(products):

            print()
            print(
                f"[{index + 1}/{len(products)}] "
                f"{product.get('title', '')}"
            )

            scrape_product_details(
                context,
                product
            )

            # Keep IDs consistent
            product["id"] = f"shadhw_{index + 1}"

            # Save after EVERY product
            save_products(products)

            print(
                f"   ✓ الصور: {len(product.get('images', []))}"
            )

            print(
                f"   ✓ الفيديوهات: {len(product.get('videos', []))}"
            )

            print(
                f"   ✓ المقاسات: {product.get('sizes', [])}"
            )

            print(
                f"   ✓ الألوان: {product.get('colors', [])}"
            )

            print(
                f"   ✓ الوصف: "
                f"{'نعم' if product.get('description') else 'لا'}"
            )

            print(
                f"   ✓ Revendeur: "
                f"{product.get('original_price', '')}"
            )

            print(
                f"   ✓ Vente: "
                f"{product.get('price', '')}"
            )

        # ====================================================
        # FINAL SAVE
        # ====================================================

        save_products(products)

        print()
        print("=" * 70)
        print("✅ انتهى الاستخراج")
        print("=" * 70)

        print(
            f"📦 عدد المنتجات: {len(products)}"
        )

        print(
            f"💾 الملف: {OUTPUT_FILE}"
        )

        print(
            f"📝 المصدر: {SOURCE_FILE}"
        )

        browser.close()


if __name__ == "__main__":
    main()

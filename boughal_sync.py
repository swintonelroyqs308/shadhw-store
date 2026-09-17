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
                return float(
                    match.group(1).replace(",", ".")
                )
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

    return None


def get_attr(locator, attribute):
    try:
        value = locator.get_attribute(attribute)

        if value:
            return clean_text(value)

    except Exception:
        pass

    return ""


def get_inner_text(locator):
    try:
        return clean_text(locator.inner_text())
    except Exception:
        return ""


# ============================================================
# REAL IMAGE EXTRACTION FROM PRODUCT PAGE
# ============================================================

def extract_real_image_url(img):
    """
    نأخذ الصور الحقيقية من صفحة المنتج.
    الأولوية:
    src
    data-src
    data-lazy-src
    data-original
    data-image
    srcset
    """

    candidates = []

    # --------------------------------------------------------
    # src
    # --------------------------------------------------------

    src = get_attr(img, "src")

    if src:
        candidates.append(src)

    # --------------------------------------------------------
    # lazy attributes
    # --------------------------------------------------------

    for attr in [
        "data-src",
        "data-lazy-src",
        "data-original",
        "data-image",
        "data-full",
        "data-large",
        "data-zoom",
        "data-url",
    ]:
        value = get_attr(img, attr)

        if value:
            candidates.append(value)

    # --------------------------------------------------------
    # srcset
    # --------------------------------------------------------

    srcset = get_attr(img, "srcset")

    if srcset:
        parts = [
            x.strip()
            for x in srcset.split(",")
            if x.strip()
        ]

        for part in reversed(parts):
            pieces = part.split()

            if pieces:
                candidates.append(
                    pieces[0].strip()
                )

    # --------------------------------------------------------
    # Validate candidates
    # --------------------------------------------------------

    for candidate in candidates:

        candidate = candidate.strip()

        if not candidate:
            continue

        if candidate.startswith("data:"):
            continue

        if candidate.startswith("blob:"):
            continue

        url = absolute_url(candidate)

        if not url:
            continue

        lower = url.lower()

        if (
            "placeholder" in lower
            or "loading" in lower
            or "blank" in lower
            or "spinner" in lower
        ):
            continue

        return url

    return ""


def extract_product_page_images(page):
    """
    استخراج جميع الصور من صفحة المنتج نفسها.
    """

    images = []

    # ========================================================
    # 1. جميع img الموجودة في الصفحة
    # ========================================================

    try:
        img_elements = page.locator("img").all()

        for img in img_elements:

            url = extract_real_image_url(img)

            if url:
                images.append(url)

    except Exception:
        pass

    # ========================================================
    # 2. صور موجودة كـ background-image
    # ========================================================

    try:
        elements = page.locator(
            "[style*='background-image']"
        ).all()

        for element in elements:

            style = get_attr(
                element,
                "style"
            )

            if not style:
                continue

            matches = re.findall(
                r'url\([\'"]?([^\'")]+)',
                style,
                re.IGNORECASE
            )

            for match in matches:

                if match.startswith("data:"):
                    continue

                url = absolute_url(match)

                if url:
                    images.append(url)

    except Exception:
        pass

    # ========================================================
    # 3. صور من links / anchors
    # ========================================================

    try:
        links = page.locator(
            "a[href]"
        ).all()

        for link in links:

            href = get_attr(
                link,
                "href"
            )

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

                url = absolute_url(href)

                if url:
                    images.append(url)

    except Exception:
        pass

    return unique_list(images)


# ============================================================
# VIDEO EXTRACTION
# ============================================================

def extract_videos(page):
    videos = []

    try:

        # <video>
        for video in page.locator("video").all():

            for attr in [
                "src",
                "data-src",
                "data-video",
                "data-url",
            ]:

                value = get_attr(
                    video,
                    attr
                )

                if value:
                    url = absolute_url(value)

                    if url and not url.startswith("blob:"):
                        videos.append(url)

        # <source>
        for source in page.locator(
            "video source"
        ).all():

            for attr in [
                "src",
                "data-src",
                "data-video",
            ]:

                value = get_attr(
                    source,
                    attr
                )

                if value:
                    url = absolute_url(value)

                    if url:
                        videos.append(url)

        # mp4 anywhere
        for element in page.locator(
            "[src], [href], [data-src], [data-video]"
        ).all():

            for attr in [
                "src",
                "href",
                "data-src",
                "data-video",
            ]:

                value = get_attr(
                    element,
                    attr
                )

                if (
                    value
                    and ".mp4" in value.lower()
                ):

                    videos.append(
                        absolute_url(value)
                    )

    except Exception:
        pass

    return unique_list(videos)


# ============================================================
# DESCRIPTION
# ============================================================

def extract_description(page):

    descriptions = []

    selectors = [
        ".description",
        "#description",
        ".product-description",
        "[class*='description']",
    ]

    for selector in selectors:

        try:

            elements = page.locator(
                selector
            ).all()

            for element in elements:

                text = get_inner_text(
                    element
                )

                if text and len(text) > 5:
                    descriptions.append(text)

        except Exception:
            pass

    # --------------------------------------------------------
    # Heading Description
    # --------------------------------------------------------

    try:

        headings = page.locator(
            "h1, h2, h3, h4, h5, h6"
        ).all()

        for heading in headings:

            heading_text = get_inner_text(
                heading
            )

            if "description" not in heading_text.lower():
                continue

            try:

                parent = heading.locator(
                    ".."
                )

                text = get_inner_text(
                    parent
                )

                if text:

                    text = re.sub(
                        r'^\s*description\s*',
                        "",
                        text,
                        flags=re.IGNORECASE
                    )

                    text = clean_text(text)

                    if len(text) > 5:
                        descriptions.append(text)

            except Exception:
                pass

    except Exception:
        pass

    descriptions = unique_list(
        descriptions
    )

    if not descriptions:
        return ""

    return max(
        descriptions,
        key=len
    )


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

            elements = page.locator(
                selector
            ).all()

            for element in elements:

                for attr in [
                    "value",
                    "data-size",
                    "title",
                    "aria-label",
                ]:

                    value = get_attr(
                        element,
                        attr
                    )

                    if value:
                        sizes.append(value)

                text = get_inner_text(
                    element
                )

                if text:
                    sizes.append(text)

        except Exception:
            pass

    sizes = unique_list(sizes)

    ignored = {
        "size",
        "sizes",
        "taille",
        "tailles",
        "choisir",
        "select",
    }

    return [
        x for x in sizes
        if x.lower() not in ignored
    ]


# ============================================================
# STATUS
# ============================================================

def is_unavailable_product(page):
    """تحقق مباشرة من DIV الذي يحمل حالة غير متوفر حاليا."""
    try:
        marker = page.locator(
            "div.absolute.top-2.right-2.z-10.bg-red-500.text-white"
        )

        try:
            marker.first.wait_for(timeout=3000)
        except Exception:
            pass

        for i in range(marker.count()):
            try:
                text = marker.nth(i).inner_text().strip()
                text = re.sub(r"\s+", " ", text)
                if text == "غير متوفر حاليا":
                    return True
            except Exception:
                continue

        return False
    except Exception:
        return False


def scrape_current_page(
    page,
    products
):

    print(
        f"📄 Page: {page.url}"
    )

    try:

        with open(
            SOURCE_FILE,
            "w",
            encoding="utf-8"
        ) as f:

            f.write(
                page.content()
            )

    except Exception:
        pass

    # ========================================================
    # REAL PRODUCT CARD
    # ========================================================

    cards = page.locator(
        "div.productCard[data-url]"
    ).all()

    print(
        f"🔎 Products on page: "
        f"{len(cards)}"
    )

    if not cards:
        return 0

    added = 0

    existing_links = {
        p.get("original_link")
        for p in products
        if p.get("original_link")
    }

    for card in cards:

        href = get_attr(
            card,
            "data-url"
        )

        if not href:
            continue

        href = absolute_url(
            href
        )

        if href in existing_links:
            continue

        product = extract_card_product(
            card,
            len(products) + 1
        )

        if not product.get(
            "original_link"
        ):
            continue

        # ========================================================
        # CHECK AVAILABILITY BEFORE ADDING PRODUCT
        # ========================================================
        detail_page = None

        try:
            detail_page = page.context.new_page()

            detail_page.goto(
                product["original_link"],
                wait_until="domcontentloaded",
                timeout=60000
            )

            # لا ننتظر networkidle هنا؛ نتحقق فقط من DIV الخاص بالحالة.
            if is_unavailable_product(detail_page):
                print(
                    f"   ⏭️ تخطي غير متوفر: "
                    f"{product['title']}"
                )
                continue

        except Exception as e:
            # إذا فشل فحص الصفحة، لا نحذف المنتج احتياطياً.
            print(
                f"   ⚠️ Availability check error: {e}"
            )

        finally:
            if detail_page:
                try:
                    detail_page.close()
                except Exception:
                    pass

        products.append(
            product
        )

        existing_links.add(
            product["original_link"]
        )

        added += 1

        print(
            f"   + "
            f"{product['title']} | "
            f"{product['original_price']} | "
            f"{product['price']}"
        )

    return added


# ============================================================
# MAIN
# ============================================================

def main():

    products = []

    with sync_playwright() as p:

        # ====================================================
        # IMPORTANT FOR GITHUB ACTIONS
        # ====================================================

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

        # ====================================================
        # LOGIN
        # ====================================================

        if not login(page):

            browser.close()

            return

        # ====================================================
        # PRODUCTS PAGE
        # ====================================================

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
            2000
        )

        # ====================================================
        # PAGINATION
        # ====================================================

        empty_pages = 0

        for page_number in range(
            1,
            MAX_PAGES + 1
        ):

            if page_number == 1:

                url = BASE_PRODUCTS_URL

            else:

                url = (
                    f"{BASE_PRODUCTS_URL}"
                    f"?page={page_number}"
                )

            print()
            print("=" * 70)
            print(
                f"📄 PAGE {page_number}"
            )
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

                page.wait_for_timeout(
                    1500
                )

            except Exception as e:

                print(
                    f"⚠️ Page error: {e}"
                )

                continue

            added = scrape_current_page(
                page,
                products
            )

            save_products(
                products
            )

            print(
                f"📦 Added: {added} | "
                f"Total: {len(products)}"
            )

            if added == 0:

                empty_pages += 1

            else:

                empty_pages = 0

            if empty_pages >= MAX_EMPTY_PAGES:

                print(
                    "🛑 No new products."
                )

                break

        # ====================================================
        # DETAILS
        # ====================================================

        print()
        print("=" * 70)
        print(
            "🔍 PRODUCT DETAILS"
        )
        print("=" * 70)

        total = len(products)

        for index, product in enumerate(
            products,
            start=1
        ):

            scrape_product_details(
                context,
                product,
                index,
                total
            )

            product["id"] = (
                f"shadhw_{index}"
            )

            # Save after EVERY product
            save_products(
                products
            )

        # ====================================================
        # FINAL
        # ====================================================

        save_products(
            products
        )

        print()
        print("=" * 70)
        print(
            "✅ DONE"
        )
        print("=" * 70)

        print(
            f"📦 Products: {len(products)}"
        )

        print(
            f"💾 {OUTPUT_FILE}"
        )

        print(
            f"📝 {SOURCE_FILE}"
        )

        browser.close()


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":
    main()

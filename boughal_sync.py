import os
import json
import time
import re
from urllib.parse import urljoin
from playwright.sync_api import sync_playwright


EMAIL = os.environ.get("BOUGHAL_EMAIL")
PASSWORD = os.environ.get("BOUGHAL_PASSWORD")

BASE_PRODUCTS_URL = "https://boughalaffiliate.com/affiliate/products"

# الربح المضاف على Prix revendeur
PROFIT_MARGIN = 100

MAX_PAGES = 1000
MAX_EMPTY_PAGES = 2

OUTPUT_JSON = "products.json"
SOURCE_HTML = "source.html"


# =========================================================
# HELPERS
# =========================================================

def clean_text(value):
    if value is None:
        return ""

    return re.sub(r"\s+", " ", str(value)).strip()


def normalize_url(url, base_url):
    if not url:
        return ""

    return urljoin(base_url, url.strip())


def unique_list(items):
    result = []
    seen = set()

    for item in items:
        if not item:
            continue

        item = clean_text(item)

        if not item:
            continue

        key = item.lower()

        if key not in seen:
            seen.add(key)
            result.append(item)

    return result


def get_attr(locator, name):
    try:
        value = locator.get_attribute(name)
        return clean_text(value)
    except Exception:
        return ""


def format_price(value):
    try:
        number = float(str(value).replace(",", "."))

        if number.is_integer():
            return f"{int(number)} DH"

        return f"{number:.2f} DH"

    except Exception:
        value = clean_text(value)

        if value:
            return f"{value} DH"

        return ""


def extract_price(text):
    text = clean_text(text)

    if not text:
        return None

    patterns = [
        r"(\d+(?:[.,]\d+)?)\s*DH",
        r"(\d+(?:[.,]\d+)?)\s*(?:MAD|د\.م)",
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.I)

        if match:
            try:
                return float(
                    match.group(1).replace(",", ".")
                )
            except Exception:
                pass

    return None


def extract_revendeur_price(text):
    text = clean_text(text)

    if not text:
        return None

    patterns = [
        r"prix\s*revendeur\s*:?\s*(\d+(?:[.,]\d+)?)\s*DH",
        r"prix\s*revendeur.{0,100}?(\d+(?:[.,]\d+)?)\s*DH",
        r"revendeur.{0,100}?(\d+(?:[.,]\d+)?)\s*DH",
    ]

    for pattern in patterns:
        match = re.search(
            pattern,
            text,
            re.I
        )

        if match:
            try:
                return float(
                    match.group(1).replace(",", ".")
                )
            except Exception:
                pass

    return None


def looks_like_product_link(href):
    if not href:
        return False

    href = href.lower()

    patterns = [
        "/product/",
        "/products/",
        "/affiliate/product/",
        "/affiliate/products/",
        "/p/",
    ]

    return any(
        pattern in href
        for pattern in patterns
    )


# =========================================================
# IMAGES
# =========================================================

def extract_all_images(page):
    urls = []

    selectors = [
        ".product-main-slider img",
        ".product-main-slider picture img",
        ".product-gallery img",
        ".product-gallery picture img",
        ".product-images img",
        ".product-images picture img",
        ".swiper-slide img",
        "[class*='gallery'] img",
        "[class*='Gallery'] img",
        "[class*='product-image'] img",
        "[class*='Product-image'] img",
    ]

    for selector in selectors:

        try:
            loc = page.locator(selector)
            count = loc.count()

            for i in range(count):

                img = loc.nth(i)

                found = False

                for attr in [
                    "src",
                    "data-src",
                    "data-lazy-src",
                    "data-original",
                    "data-image",
                    "data-url",
                ]:

                    value = get_attr(img, attr)

                    if value:
                        urls.append(
                            normalize_url(
                                value,
                                page.url
                            )
                        )

                        found = True
                        break

                srcset = get_attr(
                    img,
                    "srcset"
                )

                if srcset:

                    for part in srcset.split(","):

                        candidate = (
                            part.strip()
                            .split(" ")[0]
                        )

                        if candidate:
                            urls.append(
                                normalize_url(
                                    candidate,
                                    page.url
                                )
                            )

        except Exception:
            pass

    # Fallback فقط إذا ما لقا حتى صورة
    if not urls:

        try:
            loc = page.locator("img")
            count = loc.count()

            for i in range(count):

                img = loc.nth(i)

                for attr in [
                    "src",
                    "data-src",
                    "data-lazy-src",
                    "data-original",
                    "data-image",
                ]:

                    value = get_attr(
                        img,
                        attr
                    )

                    if value:
                        urls.append(
                            normalize_url(
                                value,
                                page.url
                            )
                        )

                        break

        except Exception:
            pass

    result = []
    seen = set()

    for url in urls:

        if not url:
            continue

        if url.lower().startswith("data:"):
            continue

        if url not in seen:
            seen.add(url)
            result.append(url)

    return result


# =========================================================
# VIDEOS
# =========================================================

def extract_all_videos(page):

    videos = []

    # <video>
    try:

        video_loc = page.locator("video")
        count = video_loc.count()

        for i in range(count):

            video = video_loc.nth(i)

            for attr in [
                "src",
                "data-src",
                "data-video",
                "data-video-url",
            ]:

                value = get_attr(
                    video,
                    attr
                )

                if value:
                    videos.append(
                        normalize_url(
                            value,
                            page.url
                        )
                    )

            # <source src="...mp4">
            source_loc = video.locator(
                "source"
            )

            source_count = source_loc.count()

            for j in range(source_count):

                source = source_loc.nth(j)

                for attr in [
                    "src",
                    "data-src",
                ]:

                    value = get_attr(
                        source,
                        attr
                    )

                    if value:
                        videos.append(
                            normalize_url(
                                value,
                                page.url
                            )
                        )

    except Exception:
        pass

    # Fallback
    selectors = [
        "[data-video]",
        "[data-video-url]",
        "[data-src*='.mp4']",
        "[href*='.mp4']",
    ]

    for selector in selectors:

        try:

            loc = page.locator(selector)
            count = loc.count()

            for i in range(count):

                element = loc.nth(i)

                for attr in [
                    "src",
                    "data-src",
                    "data-video",
                    "data-video-url",
                    "href",
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
                            normalize_url(
                                value,
                                page.url
                            )
                        )

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
    ]

    for selector in selectors:

        try:

            loc = page.locator(selector)
            count = loc.count()

            for i in range(count):

                text = clean_text(
                    loc.nth(i).inner_text()
                )

                if text and len(text) > 5:
                    return text

        except Exception:
            pass

    # البحث عن عنوان Description
    try:

        headings = page.locator(
            "h1, h2, h3, h4, strong, b"
        )

        count = headings.count()

        for i in range(count):

            heading = headings.nth(i)

            heading_text = clean_text(
                heading.inner_text()
            )

            if heading_text.lower() == "description":

                try:

                    parent = heading.locator(
                        "xpath=.."
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

                    if len(text) > 5:
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
        "select[name='size'] option",
        "select[name='sizes'] option",
        "input[name='size']",
        "input[name='sizes']",
        "[data-size]",
        ".size-button",
        ".size-option",
        "[class*='size-button']",
        "[class*='size-option']",
    ]

    for selector in selectors:

        try:

            loc = page.locator(selector)
            count = loc.count()

            for i in range(count):

                el = loc.nth(i)

                disabled = get_attr(
                    el,
                    "disabled"
                )

                aria_disabled = get_attr(
                    el,
                    "aria-disabled"
                )

                data_disabled = get_attr(
                    el,
                    "data-disabled"
                )

                if (
                    disabled
                    or aria_disabled.lower() == "true"
                    or data_disabled.lower() == "true"
                ):
                    continue

                value = (
                    get_attr(el, "data-size")
                    or get_attr(el, "value")
                    or clean_text(el.inner_text())
                )

                value = clean_text(value)

                if (
                    value
                    and len(value) <= 30
                ):
                    sizes.append(value)

        except Exception:
            pass

    # fallback
    if not sizes:

        try:

            body = clean_text(
                page.locator("body").inner_text()
            )

            pattern = (
                r"\b(?:XXXS|XXS|XS|S|M|L|XL|XXL|XXXL|"
                r"2XL|3XL|4XL|5XL|\d{2})\b"
            )

            sizes.extend(
                re.findall(
                    pattern,
                    body,
                    flags=re.I
                )
            )

        except Exception:
            pass

    result = []

    for size in sizes:

        size = clean_text(size).upper()

        if size and size not in result:
            result.append(size)

    return result


# =========================================================
# COLORS
# =========================================================

def extract_colors(page):

    colors = []

    selectors = [
        ".color-button",
        "[data-color]",
        "button[data-color]",
        "input[data-color]",
        "[class*='color-button']",
        "[class*='Color-button']",
        "[class*='color-option']",
        "[class*='Color-option']",
    ]

    for selector in selectors:

        try:

            loc = page.locator(selector)
            count = loc.count()

            for i in range(count):

                el = loc.nth(i)

                disabled = get_attr(
                    el,
                    "disabled"
                )

                aria_disabled = get_attr(
                    el,
                    "aria-disabled"
                )

                data_disabled = get_attr(
                    el,
                    "data-disabled"
                )

                if (
                    disabled
                    or aria_disabled.lower() == "true"
                    or data_disabled.lower() == "true"
                ):
                    continue

                value = (
                    get_attr(el, "data-color")
                    or get_attr(el, "data-colour")
                    or get_attr(el, "title")
                    or get_attr(el, "aria-label")
                    or get_attr(el, "value")
                    or clean_text(el.inner_text())
                )

                # محاولة من parent
                if not value:

                    try:

                        parent = el.locator(
                            "xpath=.."
                        )

                        value = (
                            get_attr(
                                parent,
                                "data-color"
                            )
                            or get_attr(
                                parent,
                                "data-colour"
                            )
                            or get_attr(
                                parent,
                                "title"
                            )
                            or get_attr(
                                parent,
                                "aria-label"
                            )
                            or clean_text(
                                parent.inner_text()
                            )
                        )

                    except Exception:
                        pass

                value = clean_text(value)

                if (
                    value
                    and len(value) <= 50
                ):
                    colors.append(value)

        except Exception:
            pass

    result = []
    seen = set()

    for color in colors:

        color = clean_text(color)

        if not color:
            continue

        key = color.lower()

        if key not in seen:

            seen.add(key)
            result.append(color)

    return result


# =========================================================
# TITLE
# =========================================================

def find_title(container, fallback_text=""):

    selectors = [
        "h1",
        "h2",
        "h3",
        "[class*='product-title']",
        "[class*='Product-title']",
        "[class*='title']",
        "a",
    ]

    for selector in selectors:

        try:

            loc = container.locator(selector)
            count = loc.count()

            for i in range(
                min(count, 5)
            ):

                text = clean_text(
                    loc.nth(i).inner_text()
                )

                if (
                    text
                    and len(text) >= 3
                    and len(text) <= 200
                    and text.lower()
                    not in [
                        "description",
                        "prix revendeur",
                    ]
                ):
                    return text

        except Exception:
            pass

    return clean_text(
        fallback_text
    )


def find_product_title(page):

    selectors = [
        "h1",
        "[class*='product-title']",
        "[class*='Product-title']",
        "[data-product-title]",
    ]

    for selector in selectors:

        try:

            loc = page.locator(selector)
            count = loc.count()

            for i in range(count):

                text = clean_text(
                    loc.nth(i).inner_text()
                )

                if (
                    text
                    and len(text) >= 3
                    and len(text) <= 200
                    and text.lower()
                    != "description"
                ):
                    return text

        except Exception:
            pass

    try:

        title = clean_text(
            page.title()
        )

        if title:
            return title

    except Exception:
        pass

    return ""


# =========================================================
# STATUS
# =========================================================

def extract_status(page):

    try:

        body = clean_text(
            page.locator("body").inner_text()
        )

        low = body.lower()

        out_words = [
            "rupture de stock",
            "hors stock",
            "out of stock",
            "épuisé",
            "epuise",
            "indisponible",
            "non disponible",
        ]

        if any(
            word in low
            for word in out_words
        ):
            return "Out of Stock"

    except Exception:
        pass

    return "In Stock"


# =========================================================
# DETAIL PRODUCT
# =========================================================

def scrape_product_details(
    context,
    product
):

    url = product.get(
        "original_link",
        ""
    )

    if not url:
        return product

    detail = context.new_page()

    try:

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

        detail.wait_for_timeout(2000)

        # source.html
        try:

            with open(
                SOURCE_HTML,
                "w",
                encoding="utf-8"
            ) as f:

                f.write(
                    detail.content()
                )

        except Exception:
            pass

        body = clean_text(
            detail.locator(
                "body"
            ).inner_text()
        )

        # TITLE
        title = find_product_title(
            detail
        )

        if title:
            product["title"] = title

        # IMAGES
        images = extract_all_images(
            detail
        )

        if images:

            product["images"] = images
            product["image"] = images[0]

        # VIDEOS
        product["videos"] = (
            extract_all_videos(detail)
        )

        # DESCRIPTION
        product["description"] = (
            extract_description(detail)
        )

        # SIZES
        product["sizes"] = (
            extract_sizes(detail)
        )

        # COLORS
        product["colors"] = (
            extract_colors(detail)
        )

        # STATUS
        product["status"] = (
            extract_status(detail)
        )

        # PRIX REVENDEUR
        reseller_price = (
            extract_revendeur_price(body)
        )

        if reseller_price is not None:

            product["original_price"] = (
                format_price(
                    reseller_price
                )
            )

            product["price"] = (
                format_price(
                    reseller_price
                    + PROFIT_MARGIN
                )
            )

        product["original_link"] = url

    except Exception as err:

        print(
            f"  [DETAIL ERROR] "
            f"{product.get('title', '')}: {err}"
        )

    finally:

        try:
            detail.close()
        except Exception:
            pass

    return product


# =========================================================
# LISTING PAGE
# =========================================================

def scrape_current_page(
    page,
    all_products
):

    found = 0
    new_products = 0

    links = page.locator(
        "a[href]"
    )

    count = links.count()

    page_items = []

    for i in range(count):

        try:

            link = links.nth(i)

            href = get_attr(
                link,
                "href"
            )

            if not looks_like_product_link(
                href
            ):
                continue

            absolute = urljoin(
                page.url,
                href
            )

            if not absolute:
                continue

            # العثور على card
            container = link

            for _ in range(6):

                try:

                    parent = container.locator(
                        "xpath=.."
                    )

                    if parent.count() == 0:
                        break

                    if (
                        parent.locator(
                            "img"
                        ).count() > 0
                    ):
                        container = parent
                        break

                    container = parent

                except Exception:
                    break

            title = find_title(
                container,
                clean_text(
                    link.inner_text()
                )
            )

            card_text = clean_text(
                container.inner_text()
            )

            low_text = card_text.lower()

            if any(
                word in low_text
                for word in [
                    "rupture de stock",
                    "hors stock",
                    "out of stock",
                    "épuisé",
                    "epuise",
                ]
            ):
                continue

            # Prix revendeur
            reseller_price = (
                extract_revendeur_price(
                    card_text
                )
            )

            # fallback
            if reseller_price is None:

                reseller_price = (
                    extract_revendeur_price(
                        clean_text(
                            link.inner_text()
                        )
                    )
                )

            # dernier fallback
            if reseller_price is None:

                reseller_price = (
                    extract_price(
                        card_text
                    )
                )

            images = extract_all_images(
                container
            )

            item = {
                "id": "",
                "title": title,
                "image": (
                    images[0]
                    if images
                    else ""
                ),
                "images": images,
                "videos": [],
                "description": "",
                "sizes": [],
                "colors": [],
                "price": "",
                "original_price": "",
                "original_link": absolute,
                "status": "In Stock",
            }

            if reseller_price is not None:

                item["original_price"] = (
                    format_price(
                        reseller_price
                    )
                )

                item["price"] = (
                    format_price(
                        reseller_price
                        + PROFIT_MARGIN
                    )
                )

            page_items.append(item)

            found += 1

        except Exception as err:

            print(
                f"  [CARD ERROR] {err}"
            )

    existing_urls = {
        p.get("original_link")
        for p in all_products
        if p.get("original_link")
    }

    for item in page_items:

        url = item["original_link"]

        if url in existing_urls:
            continue

        item["id"] = (
            f"shadhw_"
            f"{len(all_products) + 1}"
        )

        all_products.append(item)

        existing_urls.add(url)

        new_products += 1

    print(
        f"  Products found: {found} | "
        f"New: {new_products}"
    )

    return new_products


# =========================================================
# SAVE JSON
# =========================================================

def save_json(products):

    with open(
        OUTPUT_JSON,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            products,
            f,
            ensure_ascii=False,
            indent=2
        )


# =========================================================
# MAIN
# =========================================================

def run_automation():

    if not EMAIL or not PASSWORD:

        raise RuntimeError(
            "BOUGHAL_EMAIL / "
            "BOUGHAL_PASSWORD manquants."
        )

    all_products = []

    with sync_playwright() as p:

        browser = p.chromium.launch(
            headless=True
        )

        context = browser.new_context(
            viewport={
                "width": 1440,
                "height": 900,
            }
        )

        page = context.new_page()

        # =================================================
        # LOGIN — NE PAS MODIFIER
        # =================================================

        page.goto(
            "https://boughalaffiliate.com/login",
            wait_until="load"
        )
        time.sleep(4)

        email_input = page.locator(
            "input[type='email'], input[name='email']"
        ).first

        email_input.focus()
        email_input.fill(EMAIL)

        password_input = page.locator(
            "input[type='password'], input[name='password']"
        ).first

        password_input.focus()
        password_input.fill(PASSWORD)

        time.sleep(2)

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

            page.keyboard.press(
                "Enter"
            )

        time.sleep(8)

        print("Login terminé.")

        # =================================================
        # PAGINATION
        # =================================================

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

            print(
                f"\n========== PAGE "
                f"{page_number} =========="
            )

            print(url)

            try:

                page.goto(
                    url,
                    wait_until="domcontentloaded",
                    timeout=30000
                )

                try:

                    page.wait_for_load_state(
                        "networkidle",
                        timeout=10000
                    )

                except Exception:
                    pass

                page.wait_for_timeout(
                    1500
                )

                new_count = (
                    scrape_current_page(
                        page,
                        all_products
                    )
                )

                save_json(
                    all_products
                )

                print(
                    f"Total products: "
                    f"{len(all_products)}"
                )

                if new_count == 0:
                    empty_pages += 1
                else:
                    empty_pages = 0

                if (
                    empty_pages
                    >= MAX_EMPTY_PAGES
                ):

                    print(
                        "\nDeux pages vides "
                        "consécutives. "
                        "Fin de la pagination."
                    )

                    break

            except Exception as err:

                print(
                    f"[PAGE ERROR] "
                    f"{page_number}: {err}"
                )

        # =================================================
        # DETAILS
        # =================================================

        print(
            f"\n========== DETAILS: "
            f"{len(all_products)} PRODUCTS =========="
        )

        for index, product in enumerate(
            all_products,
            start=1
        ):

            print(
                f"\n[{index}/"
                f"{len(all_products)}] "
                f"{product.get('title', '')}"
            )

            scrape_product_details(
                context,
                product
            )

            # حفظ بعد كل منتج
            save_json(
                all_products
            )

            print(
                f"  Images: "
                f"{len(product.get('images', []))}"
            )

            print(
                f"  Videos: "
                f"{len(product.get('videos', []))}"
            )

            print(
                f"  Sizes: "
                f"{len(product.get('sizes', []))}"
            )

            print(
                f"  Colors: "
                f"{len(product.get('colors', []))}"
            )

            print(
                f"  Description: "
                f"{'YES' if product.get('description') else 'NO'}"
            )

            print(
                f"  Revendeur: "
                f"{product.get('original_price', '')}"
            )

            print(
                f"  Vente: "
                f"{product.get('price', '')}"
            )

        # =================================================
        # FINAL NORMALIZATION
        # =================================================

        for index, product in enumerate(
            all_products,
            start=1
        ):

            product["id"] = (
                product.get("id")
                or f"shadhw_{index}"
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

            if (
                not product["image"]
                and product["images"]
            ):

                product["image"] = (
                    product["images"][0]
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

        save_json(
            all_products
        )

        try:
            browser.close()
        except Exception:
            pass

    print(
        f"\nDONE: "
        f"{len(all_products)} products "
        f"saved to {OUTPUT_JSON}"
    )


if __name__ == "__main__":
    run_automation()

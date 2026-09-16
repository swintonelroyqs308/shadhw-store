import os
import json
import re
import asyncio
from urllib.parse import urljoin

from playwright.async_api import async_playwright


# ============================================================
# CONFIG
# ============================================================

BASE_URL = "https://boughalaffiliate.com"
BASE_PRODUCTS_URL = f"{BASE_URL}/affiliate/products"

OUTPUT_FILE = "products.json"
SOURCE_FILE = "source.html"

PROFIT_MARGIN = 100


# ============================================================
# HELPERS
# ============================================================

def clean_text(value):
    if not value:
        return ""

    value = re.sub(r"\s+", " ", str(value))
    return value.strip()


def absolute_url(url):
    if not url:
        return ""

    url = url.strip()

    if url.startswith("data:"):
        return ""

    return urljoin(BASE_URL, url)


def unique_list(items):
    result = []

    for item in items:
        item = clean_text(item)

        if item and item not in result:
            result.append(item)

    return result


def extract_price(text):
    if not text:
        return None

    text = text.replace(",", ".")

    matches = re.findall(
        r"(\d+(?:\.\d+)?)\s*(?:MAD|DH|د\.م|درهم)?",
        text,
        re.I
    )

    if not matches:
        return None

    try:
        return float(matches[-1])
    except:
        return None


def format_price(value):
    if value is None:
        return ""

    try:
        value = float(value)

        if value.is_integer():
            return f"{int(value)} DH"

        return f"{value:.2f} DH"

    except:
        return ""


def extract_revendeur_price(text):
    if not text:
        return None

    lines = text.splitlines()

    for line in lines:

        if re.search(
            r"revendeur|prix\s+revendeur",
            line,
            re.I
        ):
            price = extract_price(line)

            if price is not None:
                return price

    return None


def get_attr(element, name):
    try:
        return element.get_attribute(name)
    except:
        return None


async def get_inner_text(element):
    try:
        return await element.inner_text()
    except:
        return ""


# ============================================================
# IMAGES
# ============================================================

async def extract_real_image_url(img):

    attrs = [
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

    for attr in attrs:

        value = await get_attr(img, attr)

        if value:

            value = value.strip()

            if value.startswith("data:"):
                continue

            if value:
                return absolute_url(value)

    # srcset

    srcset = await get_attr(img, "srcset")

    if srcset:

        parts = [
            x.strip()
            for x in srcset.split(",")
            if x.strip()
        ]

        if parts:

            last = parts[-1].split(" ")[0]

            if last:
                return absolute_url(last)

    return ""


async def extract_product_page_images(page):

    images = []

    # --------------------------------------------------------
    # IMG
    # --------------------------------------------------------

    img_elements = await page.locator("img").all()

    for img in img_elements:

        url = await extract_real_image_url(img)

        if url:
            images.append(url)

    # --------------------------------------------------------
    # BACKGROUND IMAGE
    # --------------------------------------------------------

    elements = await page.locator("[style]").all()

    for element in elements:

        style = await get_attr(element, "style")

        if not style:
            continue

        matches = re.findall(
            r'url\(["\']?(.*?)["\']?\)',
            style,
            re.I
        )

        for match in matches:

            url = match.strip()

            if url and not url.startswith("data:"):
                images.append(absolute_url(url))

    # --------------------------------------------------------
    # IMAGE LINKS
    # --------------------------------------------------------

    links = await page.locator("a[href]").all()

    for link in links:

        href = await get_attr(link, "href")

        if not href:
            continue

        href = href.strip()

        if re.search(
            r"\.(jpg|jpeg|png|webp|gif)(\?.*)?$",
            href,
            re.I
        ):
            images.append(absolute_url(href))

    return unique_list(images)


# ============================================================
# VIDEOS
# ============================================================

async def extract_videos(page):

    videos = []

    # --------------------------------------------------------
    # VIDEO
    # --------------------------------------------------------

    video_elements = await page.locator("video").all()

    for video in video_elements:

        attrs = [
            "src",
            "data-src",
            "data-video",
            "data-url",
        ]

        for attr in attrs:

            value = await get_attr(video, attr)

            if value:

                value = value.strip()

                if value and not value.startswith("data:"):
                    videos.append(absolute_url(value))

        # SOURCE

        sources = await video.locator("source").all()

        for source in sources:

            attrs = [
                "src",
                "data-src",
                "data-video",
            ]

            for attr in attrs:

                value = await get_attr(source, attr)

                if value:

                    value = value.strip()

                    if value and not value.startswith("data:"):
                        videos.append(
                            absolute_url(value)
                        )

    # --------------------------------------------------------
    # SEARCH MP4 EVERYWHERE
    # --------------------------------------------------------

    elements = await page.locator(
        "[src], [href], [data-src], [data-video]"
    ).all()

    for element in elements:

        attrs = [
            "src",
            "href",
            "data-src",
            "data-video",
        ]

        for attr in attrs:

            value = await get_attr(element, attr)

            if not value:
                continue

            value = value.strip()

            if re.search(
                r"\.mp4(\?.*)?$",
                value,
                re.I
            ):
                videos.append(
                    absolute_url(value)
                )

    return unique_list(videos)


# ============================================================
# DESCRIPTION
# ============================================================

async def extract_description(page):

    selectors = [
        ".description",
        "#description",
        ".product-description",
        "[class*='description']",
    ]

    for selector in selectors:

        elements = await page.locator(selector).all()

        for element in elements:

            text = await get_inner_text(element)

            text = clean_text(text)

            if text and len(text) > 20:

                return text

    # Search headings containing Description

    headings = await page.locator(
        "h1, h2, h3, h4, h5, h6"
    ).all()

    for heading in headings:

        heading_text = clean_text(
            await get_inner_text(heading)
        )

        if re.search(
            r"description",
            heading_text,
            re.I
        ):

            try:

                parent = heading.locator("..")

                text = clean_text(
                    await parent.inner_text()
                )

                if text and len(text) > len(heading_text):

                    text = re.sub(
                        r"^description\s*:?\s*",
                        "",
                        text,
                        flags=re.I
                    )

                    if len(text) > 20:
                        return text

            except:
                pass

    return ""


# ============================================================
# SIZES
# ============================================================

async def extract_sizes(page):

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

        elements = await page.locator(selector).all()

        for element in elements:

            value = (
                await get_attr(element, "value")
                or await get_attr(element, "data-size")
            )

            text = clean_text(
                await get_inner_text(element)
            )

            if value:
                value = clean_text(value)

            candidate = value or text

            if candidate:

                candidate = clean_text(candidate)

                if candidate.lower() not in [
                    "select",
                    "choisir",
                    "choose",
                    "taille",
                    "size",
                ]:

                    sizes.append(candidate)

    return unique_list(sizes)


# ============================================================
# STATUS
# ============================================================

async def extract_status(page):

    text = ""

    try:
        text = clean_text(
            await page.locator("body").inner_text()
        )
    except:
        pass

    if re.search(
        r"rupture|épuisé|epuise|out\s+of\s+stock|indisponible",
        text,
        re.I
    ):
        return "out_of_stock"

    if re.search(
        r"disponible|en\s+stock|in\s+stock",
        text,
        re.I
    ):
        return "in_stock"

    return ""


# ============================================================
# TITLE
# ============================================================

async def extract_title(page):

    selectors = [
        "h1",
        ".product-title",
        ".product-name",
        "[class*='product-title']",
        "[class*='product-name']",
    ]

    for selector in selectors:

        elements = await page.locator(selector).all()

        for element in elements:

            text = clean_text(
                await get_inner_text(element)
            )

            if text:
                return text

    return ""


# ============================================================
# CARD PRODUCT
# ============================================================

async def extract_card_product(card, index):

    source_id = await get_attr(
        card,
        "data-id"
    )

    title = await get_attr(
        card,
        "data-name"
    )

    original_link = await get_attr(
        card,
        "data-url"
    )

    card_text = ""

    try:
        card_text = await card.inner_text()
    except:
        pass

    original_price_value = extract_revendeur_price(
        card_text
    )

    if original_price_value is None:

        # fallback: search all card text for Revendeur

        original_price_value = extract_price(
            card_text
        )

    price_value = None

    if original_price_value is not None:
        price_value = (
            original_price_value
            + PROFIT_MARGIN
        )

    status = ""

    if re.search(
        r"rupture|épuisé|epuise|out\s+of\s+stock|indisponible",
        card_text,
        re.I
    ):
        status = "out_of_stock"

    elif re.search(
        r"disponible|en\s+stock|in\s+stock",
        card_text,
        re.I
    ):
        status = "in_stock"

    return {

        "id": f"shadhw_{index}",

        "source_id": source_id or "",

        "title": clean_text(title),

        "image": "",

        "images": [],

        "videos": [],

        "description": "",

        "sizes": [],

        "price": format_price(price_value),

        "original_price": format_price(
            original_price_value
        ),

        "original_link": (
            absolute_url(original_link)
            if original_link
            else ""
        ),

        "status": status,
    }


# ============================================================
# PRODUCT DETAILS
# ============================================================

async def scrape_product_details(
    browser,
    product
):

    url = product.get("original_link")

    if not url:
        return product

    page = await browser.new_page()

    try:

        print(
            f"\n🔎 Product: {product.get('title')}"
        )

        print(
            f"🌐 URL: {url}"
        )

        await page.goto(
            url,
            wait_until="domcontentloaded",
            timeout=60000
        )

        # ----------------------------------------------------
        # WAIT
        # ----------------------------------------------------

        try:
            await page.wait_for_load_state(
                "networkidle",
                timeout=15000
            )
        except:
            pass

        # ----------------------------------------------------
        # SCROLL FOR LAZY LOADING
        # ----------------------------------------------------

        await page.evaluate(
            """
            async () => {
                await new Promise(resolve => {

                    let totalHeight = 0;
                    const distance = 500;

                    const timer = setInterval(() => {

                        window.scrollBy(
                            0,
                            distance
                        );

                        totalHeight += distance;

                        if (
                            totalHeight >=
                            document.body.scrollHeight
                        ) {
                            clearInterval(timer);
                            resolve();
                        }

                    }, 200);

                });
            }
            """
        )

        await page.wait_for_timeout(1500)

        # ----------------------------------------------------
        # SAVE SOURCE HTML
        # ----------------------------------------------------

        try:

            html = await page.content()

            with open(
                SOURCE_FILE,
                "w",
                encoding="utf-8"
            ) as f:

                f.write(html)

        except Exception as e:

            print(
                f"⚠️ source.html error: {e}"
            )

        # ----------------------------------------------------
        # TITLE
        # ----------------------------------------------------

        title = await extract_title(page)

        if title:
            product["title"] = title

        # ----------------------------------------------------
        # IMAGES
        # ----------------------------------------------------

        images = await extract_product_page_images(
            page
        )

        product["images"] = unique_list(
            images
        )

        if product["images"]:

            product["image"] = (
                product["images"][0]
            )

        print(
            f"   🖼 Images: {len(product['images'])}"
        )

        # ----------------------------------------------------
        # VIDEOS
        # ----------------------------------------------------

        videos = await extract_videos(
            page
        )

        product["videos"] = unique_list(
            videos
        )

        print(
            f"   🎥 Videos: {product['videos']}"
        )

        # ----------------------------------------------------
        # DESCRIPTION
        # ----------------------------------------------------

        description = await extract_description(
            page
        )

        product["description"] = (
            description
        )

        print(
            f"   📝 Description: "
            f"{bool(description)}"
        )

        # ----------------------------------------------------
        # SIZES
        # ----------------------------------------------------

        sizes = await extract_sizes(
            page
        )

        product["sizes"] = unique_list(
            sizes
        )

        print(
            f"   📏 Sizes: {product['sizes']}"
        )

        # ----------------------------------------------------
        # STATUS
        # ----------------------------------------------------

        status = await extract_status(
            page
        )

        if status:
            product["status"] = status

        print(
            f"   📦 Status: "
            f"{product['status']}"
        )

        # ----------------------------------------------------
        # PRICE / REVENDEUR
        # ----------------------------------------------------

        try:

            body_text = await page.locator(
                "body"
            ).inner_text()

            reseller_price = (
                extract_revendeur_price(
                    body_text
                )
            )

            if reseller_price is not None:

                product[
                    "original_price"
                ] = format_price(
                    reseller_price
                )

                product[
                    "price"
                ] = format_price(
                    reseller_price
                    + PROFIT_MARGIN
                )

                print(
                    f"   💰 Revendeur: "
                    f"{product['original_price']}"
                )

                print(
                    f"   💵 Vente: "
                    f"{product['price']}"
                )

        except Exception as e:

            print(
                f"⚠️ Price error: {e}"
            )

    except Exception as e:

        print(
            f"❌ Product error: {e}"
        )

    finally:

        await page.close()

    return product


# ============================================================
# SAVE
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
            indent=2
        )

    print(
        f"\n💾 Saved {len(products)} products "
        f"to {OUTPUT_FILE}"
    )


# ============================================================
# LOGIN
# ============================================================

async def login(page):

    email = os.getenv(
        "BOUGHAL_EMAIL"
    )

    password = os.getenv(
        "BOUGHAL_PASSWORD"
    )

    if not email or not password:

        raise Exception(
            "BOUGHAL_EMAIL / BOUGHAL_PASSWORD "
            "are missing."
        )

    print("🔐 Opening login...")

    await page.goto(
        BASE_URL,
        wait_until="domcontentloaded",
        timeout=60000
    )

    # --------------------------------------------------------
    # EMAIL
    # --------------------------------------------------------

    email_selectors = [
        "input[type='email']",
        "input[name='email']",
        "input[placeholder*='email' i]",
    ]

    password_selectors = [
        "input[type='password']",
        "input[name='password']",
    ]

    email_input = None

    for selector in email_selectors:

        locator = page.locator(
            selector
        )

        if await locator.count():

            email_input = locator.first
            break

    password_input = None

    for selector in password_selectors:

        locator = page.locator(
            selector
        )

        if await locator.count():

            password_input = locator.first
            break

    if not email_input or not password_input:

        raise Exception(
            "Login fields not found."
        )

    await email_input.fill(email)

    await password_input.fill(password)

    # --------------------------------------------------------
    # SUBMIT
    # --------------------------------------------------------

    submit_selectors = [
        "button[type='submit']",
        "input[type='submit']",
        "button:has-text('Login')",
        "button:has-text('Connexion')",
        "button:has-text('Se connecter')",
    ]

    submitted = False

    for selector in submit_selectors:

        locator = page.locator(
            selector
        )

        if await locator.count():

            await locator.first.click()

            submitted = True
            break

    if not submitted:

        await password_input.press(
            "Enter"
        )

    await page.wait_for_timeout(
        3000
    )

    try:

        await page.wait_for_load_state(
            "networkidle",
            timeout=15000
        )

    except:
        pass

    print("✅ Login completed.")


# ============================================================
# SCRAPE CURRENT PAGE
# ============================================================

async def scrape_current_page(
    page,
    products,
    start_index
):

    print(
        "\n📄 Reading products page..."
    )

    await page.wait_for_timeout(
        1500
    )

    cards = await page.locator(
        "div.productCard[data-url]"
    ).all()

    print(
        f"🛒 Found {len(cards)} product cards."
    )

    if not cards:
        return 0

    added = 0

    for card in cards:

        try:

            index = (
                start_index
                + added
                + 1
            )

            product = await extract_card_product(
                card,
                index
            )

            # ------------------------------------------------
            # SCRAPE PRODUCT PAGE
            # ------------------------------------------------

            product = await scrape_product_details(
                page.context.browser,
                product
            )

            products.append(
                product
            )

            added += 1

            # ------------------------------------------------
            # SAVE AFTER EACH PRODUCT
            # ------------------------------------------------

            save_products(
                products
            )

        except Exception as e:

            print(
                f"❌ Card error: {e}"
            )

    return added


# ============================================================
# MAIN
# ============================================================

async def main():

    products = []

    async with async_playwright() as p:

        browser = await p.chromium.launch(
            headless=True
        )

        context = await browser.new_context(
            viewport={
                "width": 1440,
                "height": 900
            }
        )

        page = await context.new_page()

        try:

            # ------------------------------------------------
            # LOGIN
            # ------------------------------------------------

            await login(page)

            # ------------------------------------------------
            # PRODUCTS
            # ------------------------------------------------

            page_number = 1

            empty_pages = 0

            max_pages = 1000

            while page_number <= max_pages:

                if page_number == 1:

                    url = BASE_PRODUCTS_URL

                else:

                    url = (
                        f"{BASE_PRODUCTS_URL}"
                        f"?page={page_number}"
                    )

                print(
                    f"\n{'=' * 60}"
                )

                print(
                    f"📄 PAGE {page_number}"
                )

                print(
                    f"🌐 {url}"
                )

                print(
                    f"{'=' * 60}"
                )

                await page.goto(
                    url,
                    wait_until="domcontentloaded",
                    timeout=60000
                )

                try:

                    await page.wait_for_load_state(
                        "networkidle",
                        timeout=15000
                    )

                except:
                    pass

                await page.wait_for_timeout(
                    1500
                )

                # ------------------------------------------------
                # CHECK CARDS
                # ------------------------------------------------

                card_count = await page.locator(
                    "div.productCard[data-url]"
                ).count()

                print(
                    f"🛒 Cards: {card_count}"
                )

                if card_count == 0:

                    empty_pages += 1

                    print(
                        f"⚠️ Empty page "
                        f"{empty_pages}/2"
                    )

                    if empty_pages >= 2:
                        break

                    page_number += 1

                    continue

                empty_pages = 0

                # ------------------------------------------------
                # SCRAPE
                # ------------------------------------------------

                await scrape_current_page(
                    page,
                    products,
                    len(products)
                )

                page_number += 1

            # ------------------------------------------------
            # FINAL SAVE
            # ------------------------------------------------

            save_products(
                products
            )

            print(
                "\n✅ SCRAPING FINISHED"
            )

            print(
                f"📦 Total products: "
                f"{len(products)}"
            )

        finally:

            await browser.close()


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":

    asyncio.run(
        main()
    )

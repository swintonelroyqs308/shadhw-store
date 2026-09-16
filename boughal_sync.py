import os
import json
import time
import re
from urllib.parse import urljoin

from playwright.sync_api import sync_playwright


EMAIL = os.environ.get("BOUGHAL_EMAIL")
PASSWORD = os.environ.get("BOUGHAL_PASSWORD")

BASE_PRODUCTS_URL = "https://boughalaffiliate.com/affiliate/products"
BASE_URL = "https://boughalaffiliate.com"


# =========================================================
# Helpers
# =========================================================

def clean_text(text):
    if not text:
        return ""
    return re.sub(r"\s+", " ", text).strip()


def to_absolute_url(url):
    if not url:
        return ""

    url = url.strip()

    if url.startswith("//"):
        return "https:" + url

    return urljoin(BASE_URL, url)


def extract_number(text):
    if not text:
        return None

    # تحويل الفاصلة إلى نقطة
    text = text.replace(",", ".")

    match = re.search(r"(\d+(?:\.\d+)?)", text)

    if not match:
        return None

    try:
        return float(match.group(1))
    except Exception:
        return None


# =========================================================
# Product links
# =========================================================

def looks_like_product_link(href):
    if not href:
        return False

    href_lower = href.lower()

    patterns = [
        "/product/",
        "/products/",
        "/affiliate/product/",
        "/affiliate/products/",
        "/public/affiliate/product/",
        "/public/affiliate/products/",
        "/p/",
    ]

    return any(pattern in href_lower for pattern in patterns)


def get_product_links_from_listing(page):
    links = []

    try:
        anchors = page.locator("a")
        count = anchors.count()

        for i in range(count):

            try:
                href = anchors.nth(i).get_attribute("href")

                if not href:
                    continue

                if not looks_like_product_link(href):
                    continue

                absolute_url = to_absolute_url(href)

                if not absolute_url:
                    continue

                # استبعاد صفحة المنتجات الرئيسية
                if absolute_url.rstrip("/") == BASE_PRODUCTS_URL.rstrip("/"):
                    continue

                if absolute_url not in links:
                    links.append(absolute_url)

            except Exception:
                continue

    except Exception as e:
        print(f"⚠️ خطأ في استخراج روابط المنتجات: {e}")

    return links


# =========================================================
# Title
# =========================================================

def extract_title(page):

    selectors = [
        "h1",
        ".product-title",
        "[class*='product-title']",
    ]

    for selector in selectors:

        try:
            locator = page.locator(selector).first

            if locator.count() > 0:

                title = clean_text(locator.inner_text())

                if title:
                    return title

        except Exception:
            pass

    return ""


# =========================================================
# Prix revendeur
# =========================================================

def extract_revendeur_price(page):

    # المصدر الحقيقي:
    #
    # <span class="font-medium">Prix revendeur:</span>
    # <span class="ml-1 font-semibold ...">80.00 DH</span>

    try:

        labels = page.locator("span")

        count = labels.count()

        for i in range(count):

            try:

                label = labels.nth(i)

                text = clean_text(label.inner_text())

                if not re.search(
                    r"Prix\s+revendeur",
                    text,
                    re.IGNORECASE
                ):
                    continue

                # نحاول أخذ السعر من parent
                parent = label.locator("xpath=..").first

                if parent.count() > 0:

                    parent_text = clean_text(
                        parent.inner_text()
                    )

                    # نحذف اسم الحقل
                    price_text = re.sub(
                        r"Prix\s+revendeur\s*:?",
                        "",
                        parent_text,
                        flags=re.IGNORECASE
                    )

                    price = extract_number(price_text)

                    if price is not None:
                        return price

            except Exception:
                continue

    except Exception:
        pass

    return None


# =========================================================
# Images
# =========================================================

def extract_all_images(page):

    images = []

    # مهم:
    # نستخرج الصور من gallery الرئيسية فقط
    # حتى لا نكرر صور thumbnails.

    selectors = [
        ".product-main-slider .swiper-slide img",
        ".product-main-slider img",
    ]

    for selector in selectors:

        try:

            imgs = page.locator(selector)
            count = imgs.count()

            for i in range(count):

                img = imgs.nth(i)

                candidates = []

                # src
                for attr in [
                    "src",
                    "data-src",
                    "data-lazy-src",
                    "data-original",
                    "data-image",
                ]:

                    try:
                        value = img.get_attribute(attr)

                        if value:
                            candidates.append(value)

                    except Exception:
                        pass

                # srcset
                try:

                    srcset = img.get_attribute("srcset")

                    if srcset:

                        for part in srcset.split(","):

                            part = part.strip()

                            if part:
                                candidates.append(
                                    part.split(" ")[0]
                                )

                except Exception:
                    pass

                for candidate in candidates:

                    absolute_url = to_absolute_url(candidate)

                    if not absolute_url:
                        continue

                    if absolute_url not in images:
                        images.append(absolute_url)

            if images:
                break

        except Exception:
            pass

    return images


# =========================================================
# Videos
# =========================================================

def extract_all_videos(page):

    videos = []

    # المصدر الحقيقي للصفحة:
    #
    # <video>
    #     <source src="https://...mp4" type="video/mp4">
    # </video>
    #
    # لذلك نعتمد على source[src].

    try:

        video_elements = page.locator(
            ".product-main-slider video"
        )

        count = video_elements.count()

        for i in range(count):

            video = video_elements.nth(i)

            # أولاً source داخل video
            try:

                sources = video.locator("source")

                source_count = sources.count()

                for j in range(source_count):

                    src = sources.nth(j).get_attribute("src")

                    if src:

                        absolute_url = to_absolute_url(src)

                        if (
                            absolute_url
                            and absolute_url not in videos
                        ):
                            videos.append(absolute_url)

            except Exception:
                pass

            # fallback إذا كان video نفسه عنده src
            try:

                src = video.get_attribute("src")

                if src:

                    absolute_url = to_absolute_url(src)

                    if (
                        absolute_url
                        and absolute_url not in videos
                    ):
                        videos.append(absolute_url)

            except Exception:
                pass

    except Exception:
        pass

    # fallback: أي video في الصفحة
    if not videos:

        try:

            video_elements = page.locator("video")

            count = video_elements.count()

            for i in range(count):

                video = video_elements.nth(i)

                sources = video.locator("source")

                source_count = sources.count()

                for j in range(source_count):

                    src = sources.nth(j).get_attribute("src")

                    if src:

                        absolute_url = to_absolute_url(src)

                        if (
                            absolute_url
                            and absolute_url not in videos
                        ):
                            videos.append(absolute_url)

        except Exception:
            pass

    return videos


# =========================================================
# Description
# =========================================================

def extract_description(page):

    try:

        headings = page.locator("h3")

        count = headings.count()

        for i in range(count):

            heading = headings.nth(i)

            try:

                heading_text = clean_text(
                    heading.inner_text()
                )

                if heading_text.lower() != "description":
                    continue

                # الوصف موجود في p داخل نفس container
                for level in range(1, 5):

                    try:

                        parent = heading.locator(
                            "xpath=" + "/.." * level
                        ).first

                        if parent.count() == 0:
                            continue

                        paragraph = parent.locator("p").first

                        if paragraph.count() > 0:

                            description = clean_text(
                                paragraph.inner_text()
                            )

                            if description:
                                return description

                    except Exception:
                        pass

            except Exception:
                pass

    except Exception:
        pass

    return ""


# =========================================================
# Sizes
# =========================================================

def extract_sizes(page):

    sizes = []

    try:

        inputs = page.locator(
            "input[name='size']"
        )

        count = inputs.count()

        for i in range(count):

            try:

                inp = inputs.nth(i)

                value = inp.get_attribute("value")

                if not value:
                    try:
                        value = inp.input_value()
                    except Exception:
                        value = ""

                value = clean_text(value)

                if value and value not in sizes:
                    sizes.append(value)

            except Exception:
                continue

    except Exception:
        pass

    return sizes


# =========================================================
# Colors
# =========================================================

def extract_colors(page):

    colors = []

    try:

        buttons = page.locator(
            ".color-button"
        )

        count = buttons.count()

        for i in range(count):

            try:

                button = buttons.nth(i)

                color = ""

                # المصدر يستعمل data-color
                try:

                    color = (
                        button.get_attribute(
                            "data-color"
                        )
                        or ""
                    )

                except Exception:
                    pass

                # fallback: title
                if not color:

                    try:

                        color = (
                            button.get_attribute(
                                "title"
                            )
                            or ""
                        )

                    except Exception:
                        pass

                # fallback: parent title
                if not color:

                    try:

                        parent = button.locator(
                            "xpath=.."
                        ).first

                        if parent.count() > 0:

                            color = (
                                parent.get_attribute(
                                    "title"
                                )
                                or ""
                            )

                    except Exception:
                        pass

                color = clean_text(color)

                if color and color not in colors:
                    colors.append(color)

            except Exception:
                continue

    except Exception:
        pass

    return colors


# =========================================================
# Status
# =========================================================

def extract_status(page):

    selectors = [
        ".stock-status",
        ".product-stock",
        "[class*='stock-status']",
        "[class*='product-stock']",
    ]

    for selector in selectors:

        try:

            locator = page.locator(selector)

            count = locator.count()

            for i in range(count):

                text = clean_text(
                    locator.nth(i).inner_text()
                )

                if text:
                    return text

        except Exception:
            pass

    # كما كان في الكود السابق
    return "In Stock"


# =========================================================
# Scrape Product Detail
# =========================================================

def scrape_product_detail(
    detail_page,
    product_url,
    product_id
):

    print("")
    print(f"      🔎 المنتج: {product_url}")

    try:

        detail_page.goto(
            product_url,
            wait_until="networkidle",
            timeout=30000
        )

        time.sleep(2)

    except Exception as e:

        print(
            f"      ❌ فشل فتح صفحة المنتج: {e}"
        )

        return None

    # -----------------------------------------------------
    # استخراج البيانات
    # -----------------------------------------------------

    title = extract_title(detail_page)

    images = extract_all_images(detail_page)

    videos = extract_all_videos(detail_page)

    revendeur_price = extract_revendeur_price(
        detail_page
    )

    description = extract_description(
        detail_page
    )

    sizes = extract_sizes(
        detail_page
    )

    colors = extract_colors(
        detail_page
    )

    status = extract_status(
        detail_page
    )

    # -----------------------------------------------------
    # تحقق من البيانات الأساسية
    # -----------------------------------------------------

    if not title:

        print(
            "      ⚠️ اسم المنتج غير موجود — تخطي"
        )

        return None

    if revendeur_price is None:

        print(
            "      ⚠️ Prix revendeur غير موجود — تخطي"
        )

        return None

    if not images:

        print(
            "      ⚠️ لا توجد صور — تخطي"
        )

        return None

    # -----------------------------------------------------
    # السعر
    # -----------------------------------------------------

    your_price = revendeur_price + 100

    if your_price.is_integer():
        your_price_text = (
            f"{int(your_price)} DH"
        )
    else:
        your_price_text = (
            f"{your_price:.2f} DH"
        )

    if revendeur_price.is_integer():
        revendeur_text = (
            f"{int(revendeur_price)} DH"
        )
    else:
        revendeur_text = (
            f"{revendeur_price:.2f} DH"
        )

    # -----------------------------------------------------
    # Product JSON
    # -----------------------------------------------------

    product = {

        "id": f"shadhw_{product_id}",

        "title": title,

        # الصورة الرئيسية
        "image": images[0],

        # جميع الصور
        "images": images,

        # جميع الفيديوهات
        "videos": videos,

        # السعر في SHADHW
        "price": your_price_text,

        # Prix revendeur
        "original_price": revendeur_text,

        # الوصف
        "description": description,

        # الأحجام
        "sizes": sizes,

        # الألوان
        "colors": colors,

        # الرابط الأصلي
        "original_link": product_url,

        # الحالة
        "status": status,
    }

    # -----------------------------------------------------
    # Log
    # -----------------------------------------------------

    print(
        f"      ✅ {title}"
    )

    print(
        f"         💰 Prix revendeur: "
        f"{revendeur_text}"
    )

    print(
        f"         🏷️ Prix SHADHW: "
        f"{your_price_text}"
    )

    print(
        f"         🖼️ الصور: "
        f"{len(images)}"
    )

    print(
        f"         🎥 الفيديوهات: "
        f"{len(videos)}"
    )

    print(
        f"         📏 الأحجام: "
        f"{sizes}"
    )

    print(
        f"         🎨 الألوان: "
        f"{colors}"
    )

    print(
        f"         📝 الوصف: "
        f"{'نعم' if description else 'لا'}"
    )

    return product


# =========================================================
# Scrape Current Listing Page
# =========================================================

def scrape_current_page(
    page,
    context,
    all_products,
    next_id
):

    print(
        "   📋 استخراج روابط المنتجات..."
    )

    product_links = (
        get_product_links_from_listing(page)
    )

    print(
        f"   🔗 عدد روابط المنتجات: "
        f"{len(product_links)}"
    )

    new_count = 0

    # صفحة مستقلة لفتح تفاصيل المنتجات
    detail_page = context.new_page()

    try:

        for product_url in product_links:

            # منع التكرار
            already_exists = any(
                product.get("original_link")
                == product_url
                for product in all_products
            )

            if already_exists:
                continue

            product = scrape_product_detail(
                detail_page,
                product_url,
                next_id
            )

            if product:

                all_products.append(product)

                next_id += 1

                new_count += 1

            time.sleep(0.5)

    finally:

        try:
            detail_page.close()
        except Exception:
            pass

    return (
        all_products,
        new_count,
        next_id
    )


# =========================================================
# MAIN
# =========================================================

def run_automation():

    all_products = []

    next_id = 1

    with sync_playwright() as p:

        # =================================================
        # LOGIN
        # =================================================

        print(
            "🔗 [1/4] إطلاق الروبوت المتخفي "
            "ومحاكاة متصفح بشري..."
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

        # =================================================
        # LOGIN — نفس الطريقة التي تعمل عندك
        # =================================================

        page.goto(
            "https://boughalaffiliate.com/login",
            wait_until="load"
        )

        time.sleep(4)

        print(
            "🔐 [2/4] مِلء حقول البيانات "
            "وتثبيت الجلسة برمجياً..."
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
            "🚀 [3/4] الضغط الفيزيائي العنيف "
            "على زر Se connecter المباشر..."
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
                "⚠️ النقر البرمجي العادي واجه حماية، "
                "ننتقل للضغط بالكيبورد..."
            )

            page.keyboard.press(
                "Enter"
            )

        time.sleep(8)

        # =================================================
        # PRODUCTS
        # =================================================

        print(
            "🛍️ الانتقال إلى صفحة المنتجات "
            "وسحب السلع المتوفرة..."
        )

        page_number = 1

        empty_pages = 0

        MAX_EMPTY_PAGES = 2

        # =================================================
        # PAGE 1 → 2 → 3 → ...
        # =================================================

        while True:

            if page_number == 1:

                url = BASE_PRODUCTS_URL

            else:

                url = (
                    f"{BASE_PRODUCTS_URL}"
                    f"?page={page_number}"
                )

            print("")
            print("=" * 70)

            print(
                f"📄 الصفحة رقم {page_number}"
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

                time.sleep(4)

            except Exception as e:

                print(
                    f"❌ خطأ أثناء فتح الصفحة "
                    f"{page_number}: {e}"
                )

                empty_pages += 1

                if (
                    empty_pages
                    >= MAX_EMPTY_PAGES
                ):
                    break

                page_number += 1

                continue

            (
                all_products,
                new_count,
                next_id
            ) = scrape_current_page(
                page,
                context,
                all_products,
                next_id
            )

            print("")
            print(
                f"📦 منتجات جديدة: {new_count}"
            )

            print(
                f"📊 المجموع: "
                f"{len(all_products)}"
            )

            # screenshot
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
            # Empty page
            # =================================================

            if new_count == 0:

                empty_pages += 1

                print(
                    f"⚠️ لا توجد منتجات جديدة "
                    f"(empty={empty_pages})"
                )

                if (
                    empty_pages
                    >= MAX_EMPTY_PAGES
                ):

                    print(
                        "🛑 صفحات فارغة متتالية — "
                        "إيقاف التصفح."
                    )

                    break

            else:

                empty_pages = 0

            page_number += 1

            # حماية
            if page_number > 1000:

                print(
                    "🛑 تجاوز 1000 صفحة — إيقاف."
                )

                break

        # =================================================
        # SAVE products.json
        # =================================================

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
                indent=2
            )

        print(
            f"✅ تم حفظ "
            f"{len(all_products)} "
            f"منتج في products.json"
        )

        # =================================================
        # SAVE source.html
        # =================================================

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
                f"⚠️ تعذر حفظ source.html: {e}"
            )

        browser.close()


# =========================================================
# START
# =========================================================

if __name__ == "__main__":
    run_automation()

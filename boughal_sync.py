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

    text = text.replace(",", ".")
    match = re.search(r"(\d+(?:\.\d+)?)", text)

    if not match:
        return None

    try:
        return float(match.group(1))
    except Exception:
        return None


def looks_like_product_link(href):
    if not href:
        return False

    patterns = [
        "/product/",
        "/products/",
        "/affiliate/product/",
        "/affiliate/products/",
        "/public/affiliate/product/",
        "/public/affiliate/products/",
        "/p/",
    ]

    href = href.lower()

    return any(pattern in href for pattern in patterns)


def extract_title(page):
    selectors = [
        "h1",
        ".product-title",
        "[class*='product-title']",
    ]

    for selector in selectors:
        try:
            loc = page.locator(selector).first
            if loc.count() > 0:
                text = clean_text(loc.inner_text())
                if text:
                    return text
        except Exception:
            pass

    return ""


# =========================================================
# Prix revendeur
# =========================================================

def extract_revendeur_price(page):
    """
    يبحث تحديدا عن:
        Prix revendeur
    ولا يعتمد على أول سعر موجود في الصفحة.
    """

    # الطريقة الأساسية: label يحتوي على Prix revendeur
    try:
        labels = page.locator("text=Prix revendeur")

        count = labels.count()

        for i in range(count):
            label = labels.nth(i)

            try:
                if not label.is_visible():
                    continue
            except Exception:
                pass

            # parent
            for level in range(1, 5):
                try:
                    parent = label.locator("xpath=" + "/.." * level).first

                    if parent.count() == 0:
                        continue

                    text = clean_text(parent.inner_text())

                    if "Prix revendeur" not in text:
                        continue

                    # نحذف اسم الحقل ونبحث عن السعر
                    without_label = re.sub(
                        r"Prix\s+revendeur",
                        "",
                        text,
                        flags=re.IGNORECASE
                    )

                    price = extract_number(without_label)

                    if price is not None:
                        return price

                except Exception:
                    pass

    except Exception:
        pass

    # fallback: البحث في العناصر التي تحتوي بالضبط على النص
    try:
        all_elements = page.locator("span, div, p, strong, b")

        count = min(all_elements.count(), 1000)

        for i in range(count):
            try:
                text = clean_text(all_elements.nth(i).inner_text())

                if not text:
                    continue

                if re.search(r"Prix\s+revendeur", text, re.IGNORECASE):
                    price = extract_number(
                        re.sub(
                            r"Prix\s+revendeur",
                            "",
                            text,
                            flags=re.IGNORECASE
                        )
                    )

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

    selectors = [
        ".product-main-slider .swiper-slide img",
        ".product-main-slider img",
        ".swiper-slide img",
        ".product-gallery img",
        "img",
    ]

    for selector in selectors:
        try:
            loc = page.locator(selector)
            count = loc.count()

            for i in range(count):
                img = loc.nth(i)

                candidates = []

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
                        parts = srcset.split(",")

                        for part in parts:
                            part = part.strip()

                            if part:
                                candidates.append(
                                    part.split(" ")[0]
                                )
                except Exception:
                    pass

                for candidate in candidates:
                    absolute = to_absolute_url(candidate)

                    if not absolute:
                        continue

                    # استبعاد الصور غير المفيدة
                    low = absolute.lower()

                    if any(x in low for x in [
                        "logo",
                        "favicon",
                        "placeholder",
                        "avatar",
                    ]):
                        continue

                    if absolute not in images:
                        images.append(absolute)

        except Exception:
            pass

        # إذا حصلنا على صور من gallery الحقيقي، لا نحتاج
        # أن نضيف صور الصفحة الأخرى
        if images and selector == ".product-main-slider .swiper-slide img":
            break

    return images


# =========================================================
# Description
# =========================================================

def extract_description(page):
    """
    المصدر فيه:
        <h3>Description</h3>
        <p>...</p>
    """

    try:
        headings = page.locator("h3")

        count = headings.count()

        for i in range(count):
            heading = headings.nth(i)

            try:
                text = clean_text(heading.inner_text())

                if text.lower() != "description":
                    continue

                # نبحث عن p قريب من h3
                for level in range(1, 5):
                    try:
                        parent = heading.locator(
                            "xpath=" + "/.." * level
                        ).first

                        if parent.count() == 0:
                            continue

                        p = parent.locator("p").first

                        if p.count() > 0:
                            desc = clean_text(p.inner_text())

                            if desc:
                                return desc

                    except Exception:
                        pass

            except Exception:
                pass

    except Exception:
        pass

    # fallback
    try:
        paragraphs = page.locator("p")
        count = paragraphs.count()

        for i in range(count):
            try:
                text = clean_text(paragraphs.nth(i).inner_text())

                if len(text) > 20:
                    return text
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
        inputs = page.locator("input[name='size']")
        count = inputs.count()

        for i in range(count):
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
        pass

    return sizes


# =========================================================
# Colors
# =========================================================

def extract_colors(page):
    colors = []

    try:
        buttons = page.locator(".color-button")
        count = buttons.count()

        for i in range(count):
            button = buttons.nth(i)

            color = ""

            # المصدر يستعمل title في العنصر الأب
            try:
                parent = button.locator("xpath=..").first

                if parent.count() > 0:
                    color = parent.get_attribute("title") or ""
            except Exception:
                pass

            # fallback: title على الزر نفسه
            if not color:
                try:
                    color = button.get_attribute("title") or ""
                except Exception:
                    pass

            # fallback: النص
            if not color:
                try:
                    color = clean_text(button.inner_text())
                except Exception:
                    pass

            color = clean_text(color)

            if color and color not in colors:
                colors.append(color)

    except Exception:
        pass

    return colors


# =========================================================
# Status
# =========================================================

def extract_status(page):
    """
    نحاول أخذ حالة المنتج إن كانت موجودة.
    إذا لم توجد، نحافظ على In Stock كما في النسخة الأصلية.
    """

    selectors = [
        ".stock-status",
        ".product-stock",
        "[class*='stock']",
    ]

    for selector in selectors:
        try:
            loc = page.locator(selector)

            count = loc.count()

            for i in range(count):
                text = clean_text(loc.nth(i).inner_text())

                if text:
                    return text

        except Exception:
            pass

    return "In Stock"


# =========================================================
# Scrape Product Detail
# =========================================================

def scrape_product_detail(detail_page, product_url, product_id):
    print(f"      🔎 فتح المنتج: {product_url}")

    try:
        detail_page.goto(
            product_url,
            wait_until="networkidle",
            timeout=30000
        )

        time.sleep(2)

    except Exception as e:
        print(f"      ❌ فشل فتح المنتج: {e}")
        return None

    title = extract_title(detail_page)

    images = extract_all_images(detail_page)

    revendeur_price = extract_revendeur_price(detail_page)

    description = extract_description(detail_page)

    sizes = extract_sizes(detail_page)

    colors = extract_colors(detail_page)

    status = extract_status(detail_page)

    # -----------------------------------------------------
    # السعر
    # -----------------------------------------------------

    if revendeur_price is None:
        print("      ⚠️ Prix revendeur غير موجود — المنتج لن يضاف")
        return None

    your_price = revendeur_price + 100

    # تنسيق السعر
    if your_price.is_integer():
        your_price_text = f"{int(your_price)} DH"
    else:
        your_price_text = f"{your_price:.2f} DH"

    if revendeur_price.is_integer():
        revendeur_text = f"{int(revendeur_price)} DH"
    else:
        revendeur_text = f"{revendeur_price:.2f} DH"

    # -----------------------------------------------------
    # الصور
    # -----------------------------------------------------

    if not images:
        print("      ⚠️ لا توجد صور — المنتج لن يضاف")
        return None

    # -----------------------------------------------------
    # الاسم
    # -----------------------------------------------------

    if not title:
        print("      ⚠️ اسم المنتج غير موجود — المنتج لن يضاف")
        return None

    product = {
        "id": f"shadhw_{product_id}",
        "title": title,

        # الصورة الأولى للحفاظ على توافق الموقع الحالي
        "image": images[0],

        # جميع الصور
        "images": images,

        # السعر في متجر SHADHW
        "price": your_price_text,

        # Prix revendeur
        "original_price": revendeur_text,

        # الوصف
        "description": description,

        # الأحجام
        "sizes": sizes,

        # الألوان
        "colors": colors,

        # رابط المنتج الأصلي
        "original_link": product_url,

        # الحالة
        "status": status,
    }

    print(f"      ✅ {title}")
    print(f"         💰 Revendeur: {revendeur_text}")
    print(f"         🏷️ سعر المتجر: {your_price_text}")
    print(f"         🖼️ الصور: {len(images)}")
    print(f"         📏 الأحجام: {sizes}")
    print(f"         🎨 الألوان: {colors}")
    print(f"         📝 الوصف: {'نعم' if description else 'لا'}")

    return product


# =========================================================
# Extract product links from listing page
# =========================================================

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

                absolute = to_absolute_url(href)

                if not absolute:
                    continue

                # نستبعد صفحة المنتجات الرئيسية
                if absolute.rstrip("/") == BASE_PRODUCTS_URL.rstrip("/"):
                    continue

                if absolute not in links:
                    links.append(absolute)

            except Exception:
                continue

    except Exception as e:
        print(f"⚠️ خطأ في استخراج روابط المنتجات: {e}")

    return links


# =========================================================
# Scrape Current Listing Page
# =========================================================

def scrape_current_page(page, context, all_products, next_id):
    print("   📋 استخراج روابط المنتجات من الصفحة...")

    product_links = get_product_links_from_listing(page)

    print(f"   🔗 تم العثور على {len(product_links)} رابط منتج")

    new_count = 0

    detail_page = context.new_page()

    try:
        for product_url in product_links:

            # منع تكرار المنتج
            already_exists = any(
                p.get("original_link") == product_url
                for p in all_products
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

    return all_products, new_count, next_id


# =========================================================
# MAIN AUTOMATION
# =========================================================

def run_automation():

    all_products = []
    next_id = 1

    with sync_playwright() as p:

        print(
            "🔗 [1/4] إطلاق الروبوت المتخفي ومحاكاة متصفح بشري..."
        )

        browser = p.chromium.launch(headless=True)

        context = browser.new_context(
            viewport={'width': 1280, 'height': 800},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            ),
            locale="fr-FR"
        )

        page = context.new_page()

        # =================================================
        # LOGIN — لا نغير هذه الطريقة
        # =================================================

        page.goto(
            "https://boughalaffiliate.com/login",
            wait_until="load"
        )

        time.sleep(4)

        print(
            "🔐 [2/4] مِلء حقول البيانات وتثبيت الجلسة برمجياً..."
        )

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

        print(
            "🚀 [3/4] الضغط الفيزيائي العنيف على زر "
            "Se connecter المباشر..."
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

            page.keyboard.press("Enter")

        time.sleep(8)

        # =================================================
        # PRODUCTS — page 1 → page 2 → page 3...
        # =================================================

        print(
            "🛍️ الانتقال إلى صفحة المنتجات وسحب السلع المتوفرة..."
        )

        page_number = 1
        empty_pages = 0

        MAX_EMPTY_PAGES = 2

        while True:

            if page_number == 1:
                url = BASE_PRODUCTS_URL
            else:
                url = f"{BASE_PRODUCTS_URL}?page={page_number}"

            print("")
            print("=" * 70)
            print(f"📄 الصفحة رقم {page_number}")
            print(f"🔗 {url}")
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

                if empty_pages >= MAX_EMPTY_PAGES:
                    break

                page_number += 1
                continue

            before_count = len(all_products)

            all_products, new_count, next_id = scrape_current_page(
                page,
                context,
                all_products,
                next_id
            )

            after_count = len(all_products)

            print(
                f"📦 منتجات جديدة في الصفحة: {new_count}"
            )

            print(
                f"📊 مجموع المنتجات حتى الآن: {after_count}"
            )

            # screenshot
            try:
                page.screenshot(
                    path=f"page_{page_number}.png",
                    full_page=True
                )
            except Exception:
                pass

            # -------------------------------------------------
            # إذا الصفحة فارغة
            # -------------------------------------------------

            if new_count == 0:

                empty_pages += 1

                print(
                    f"⚠️ لم يتم العثور على منتجات جديدة "
                    f"(empty={empty_pages})"
                )

                if empty_pages >= MAX_EMPTY_PAGES:
                    print(
                        "🛑 تم الوصول إلى صفحات فارغة متتالية. "
                        "إيقاف التصفح."
                    )
                    break

            else:
                empty_pages = 0

            page_number += 1

            if page_number > 1000:
                print("🛑 حماية: تجاوز 1000 صفحة.")
                break

        # =================================================
        # SAVE JSON
        # =================================================

        print("")
        print("=" * 70)
        print("💾 حفظ المنتجات...")
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
            f"✅ تم حفظ {len(all_products)} منتج في products.json"
        )

        # =================================================
        # SAVE SOURCE
        # =================================================

        try:
            with open(
                "source.html",
                "w",
                encoding="utf-8"
            ) as f:
                f.write(page.content())

            print("✅ تم حفظ source.html")

        except Exception as e:
            print(
                f"⚠️ تعذر حفظ source.html: {e}"
            )

        browser.close()


if __name__ == "__main__":
    run_automation()

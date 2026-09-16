import os
import json
import time
import re
from playwright.sync_api import sync_playwright

EMAIL = os.environ.get("BOUGHAL_EMAIL")
PASSWORD = os.environ.get("BOUGHAL_PASSWORD")

BASE_PRODUCTS_URL = "https://boughalaffiliate.com/affiliate/products"


def clean_text(value):
    if not value:
        return ""
    return " ".join(value.split()).strip()


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
            value = match.group(1).replace(",", ".")

            try:
                return float(value)
            except Exception:
                pass

    return None


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

    # استخراج الصور من srcset
    try:
        srcset = img.get_attribute("srcset")

        if srcset:
            for part in srcset.split(","):
                url = part.strip().split(" ")[0].strip()

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

        if any(word in low for word in blocked):
            continue

        if url.startswith("//"):
            url = "https:" + url

        elif url.startswith("/"):
            url = "https://boughalaffiliate.com" + url

        return url

    return None


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

    return any(pattern in h for pattern in patterns)


def find_title(container, fallback_text=""):

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
            candidate = container.locator(selector).first

            if candidate.count() == 0:
                continue

            # data-title
            try:
                data_title = candidate.get_attribute("data-title")

                if data_title:
                    data_title = clean_text(data_title)

                    if len(data_title) >= 3:
                        return data_title

            except Exception:
                pass

            candidate_text = clean_text(
                candidate.inner_text()
            )

            if len(candidate_text) >= 3:

                if extract_price(candidate_text) is None:
                    return candidate_text

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
        "disponibilité"
    ]

    for line in lines:

        if len(line) < 3:
            continue

        if extract_price(line) is not None:
            continue

        low = line.lower()

        if any(word in low for word in ignored_words):
            continue

        return line

    return ""


# =========================================================
# استخراج منتجات الصفحة الحالية
# =========================================================

def scrape_current_page(page, all_products):

    page_products_before = len(all_products)

    try:

        try:
            page.wait_for_load_state(
                "networkidle",
                timeout=15000
            )
        except Exception:
            pass

        page.wait_for_timeout(4000)

        # =====================================================
        # الطريقة الأولى: البحث عن روابط المنتجات
        # =====================================================

        links = page.locator("a").all()

        print(
            f"🔎 روابط الصفحة: {len(links)}"
        )

        seen_links = set()

        for link in links:

            try:

                href = link.get_attribute("href")

                if not looks_like_product_link(href):
                    continue

                if href.startswith("/"):
                    absolute_href = (
                        "https://boughalaffiliate.com"
                        + href
                    )

                elif href.startswith("//"):
                    absolute_href = "https:" + href

                else:
                    absolute_href = href

                if absolute_href in seen_links:
                    continue

                seen_links.add(absolute_href)

                # =================================================
                # العثور على container المنتج
                # =================================================

                container = link

                for _ in range(6):

                    try:

                        parent = container.locator("..")

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
                # السعر
                # =================================================

                base_price = extract_price(text)

                if base_price is None:
                    continue

                your_price = int(
                    base_price + 50
                )

                # =================================================
                # الاسم
                # =================================================

                title = find_title(
                    container,
                    text
                )

                if not title:
                    continue

                # =================================================
                # الصورة
                # =================================================

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

                # =================================================
                # منع التكرار
                # =================================================

                duplicate = any(
                    p["original_link"]
                    == absolute_href
                    or p["title"].lower()
                    == title.lower()
                    for p in all_products
                )

                if duplicate:
                    continue

                product = {
                    "id": f"shadhw_{len(all_products) + 1}",
                    "title": title,
                    "image": image_url,
                    "price": f"{your_price} DH",
                    "original_price": f"{int(base_price)} DH",
                    "original_link": absolute_href,
                    "status": "In Stock"
                }

                all_products.append(product)

                print(
                    f"   ✅ {title}"
                )

                print(
                    f"      💰 {int(base_price)} DH"
                    f" → {your_price} DH"
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
            f"⚠️ خطأ في طريقة الروابط: {e}"
        )

    # =====================================================
    # الطريقة الثانية: إذا لم نستخرج شيئاً
    # =====================================================

    if len(all_products) == page_products_before:

        print(
            "🔄 لم نجد منتجات عبر الروابط، "
            "نجرب اكتشاف البطاقات..."
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
                f"🔎 العناصر المرشحة: {len(cards)}"
            )

            for card in cards:

                try:

                    text = clean_text(
                        card.inner_text()
                    )

                    if len(text) < 5:
                        continue

                    base_price = extract_price(text)

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
                                a.get_attribute("href")
                                or ""
                            )

                            if href.startswith("/"):
                                href = (
                                    "https://boughalaffiliate.com"
                                    + href
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

                    # منع التكرار
                    duplicate = any(
                        p["title"].lower()
                        == title.lower()
                        for p in all_products
                    )

                    if duplicate:
                        continue

                    your_price = int(
                        base_price + 50
                    )

                    product = {
                        "id": f"shadhw_{len(all_products) + 1}",
                        "title": title,
                        "image": image_url,
                        "price": f"{your_price} DH",
                        "original_price": f"{int(base_price)} DH",
                        "original_link": href,
                        "status": "In Stock"
                    }

                    all_products.append(product)

                    print(
                        f"   ✅ CARD: {title}"
                    )

                except Exception:
                    continue

        except Exception as e:

            print(
                f"⚠️ خطأ في اكتشاف البطاقات: {e}"
            )

    new_products = (
        len(all_products)
        - page_products_before
    )

    return all_products, new_products


# =========================================================
# البرنامج الرئيسي
# =========================================================

def run_automation():

    with sync_playwright() as p:

        print(
            "🔗 [1/4] إطلاق الروبوت المتخفي "
            "ومحاكاة متصفح بشري..."
        )

        browser = p.chromium.launch(
            headless=True
        )

        context = browser.new_context(
            viewport={
                'width': 1280,
                'height': 800
            },
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 "
                "(KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            ),
            locale="fr-FR"
        )

        page = context.new_page()

        # =====================================================
        # LOGIN — أبقيته كما هو
        # =====================================================

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

        except Exception as click_err:

            print(
                "⚠️ النقر البرمجي العادي واجه حماية، "
                "ننتقل للضغط بالكيبورد..."
            )

            page.keyboard.press("Enter")

        time.sleep(8)

        # =====================================================
        # الدخول للصفحة الأولى
        # =====================================================

        print(
            "🛍️ [4/4] الانتقال إلى كتالوج المنتجات..."
        )

        page.goto(
            BASE_PRODUCTS_URL,
            wait_until="networkidle"
        )

        time.sleep(6)

        # =====================================================
        # استخراج كل الصفحات
        # =====================================================

        all_products = []

        page_number = 1

        empty_pages = 0

        MAX_EMPTY_PAGES = 2

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

            page.wait_for_timeout(4000)

            # screenshot للمراجعة
            page.screenshot(
                path=f"page_{page_number}.png",
                full_page=True
            )

            before = len(all_products)

            all_products, new_count = scrape_current_page(
                page,
                all_products
            )

            print("")
            print(
                f"📦 الصفحة {page_number}: "
                f"+{new_count} منتج جديد"
            )

            print(
                f"📊 الإجمالي: "
                f"{len(all_products)}"
            )

            # =================================================
            # إذا الصفحة لا تحتوي منتجات جديدة
            # =================================================

            if new_count == 0:

                empty_pages += 1

                print(
                    f"⚠️ الصفحة {page_number} "
                    f"لم تضف منتجات جديدة "
                    f"({empty_pages}/{MAX_EMPTY_PAGES})"
                )

                if empty_pages >= MAX_EMPTY_PAGES:

                    print(
                        "🛑 صفحتان متتاليتان بدون "
                        "منتجات جديدة."
                    )

                    print(
                        "🏁 نعتبر أننا وصلنا إلى نهاية الكتالوج."
                    )

                    break

            else:

                empty_pages = 0

            # =================================================
            # حماية إضافية من pagination لا نهائي
            # =================================================

            page_number += 1

            if page_number > 1000:

                print(
                    "🛑 تم الوصول إلى الحد الأقصى "
                    "1000 صفحة."
                )

                break

        # =====================================================
        # حفظ المنتجات
        # =====================================================

        products_list = all_products

        with open(
            "products.json",
            "w",
            encoding="utf-8"
        ) as f:

            json.dump(
                products_list,
                f,
                ensure_ascii=False,
                indent=4
            )

        # =====================================================
        # حفظ الصفحة الأخيرة
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

        except Exception as e:

            print(
                f"⚠️ لم يتم حفظ source.html: {e}"
            )

        # =====================================================
        # التقرير النهائي
        # =====================================================

        print("")
        print("=" * 70)

        print(
            "🎉 اكتمل تحديث الكتالوج!"
        )

        print(
            f"📄 عدد الصفحات المفحوصة: "
            f"{page_number}"
        )

        print(
            f"📦 إجمالي المنتجات: "
            f"{len(products_list)}"
        )

        print(
            "💾 تم إنشاء products.json"
        )

        print("=" * 70)

        browser.close()


if __name__ == "__main__":
    run_automation()

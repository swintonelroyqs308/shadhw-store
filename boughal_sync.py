import os
import json
import time
import re
from playwright.sync_api import sync_playwright

EMAIL = os.environ.get("BOUGHAL_EMAIL")
PASSWORD = os.environ.get("BOUGHAL_PASSWORD")


def run_automation():
    with sync_playwright() as p:
        print("🔗 [1/4] إطلاق الروبوت المتخفي ومحاكاة متصفح بشري...")

        browser = p.chromium.launch(headless=True)

        context = browser.new_context(
            viewport={'width': 1280, 'height': 800},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            locale="fr-FR"
        )

        page = context.new_page()

        # =====================================================
        # 1. الدخول لصفحة الدخول
        # =====================================================

        page.goto(
            "https://boughalaffiliate.com/login",
            wait_until="load"
        )

        time.sleep(4)

        print("🔐 [2/4] مِلء حقول البيانات وتثبيت الجلسة برمجياً...")

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

        print("🚀 [3/4] الضغط الفيزيائي العنيف على زر Se connecter المباشر...")

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
        # 2. صفحة المنتجات
        # =====================================================

        print("🛍️ الانتقال إلى صفحة المنتجات وسحب السلع المتوفرة...")

        page.goto(
            "https://boughalaffiliate.com/affiliate/products",
            wait_until="networkidle"
        )

        time.sleep(6)

        # حفظ screenshot للمراقبة
        page.screenshot(
            path="page_preview.png",
            full_page=True
        )

        products_list = []

        # =====================================================
        # أدوات مساعدة للاستخراج
        # =====================================================

        def clean_text(value):
            if not value:
                return ""

            return " ".join(
                value.split()
            ).strip()

        def extract_price(text):
            """
            استخراج السعر من النص.

            يدعم أمثلة مثل:
            149 DH
            149.00 DH
            149,00 DH
            149 MAD
            149 د.م
            """

            if not text:
                return None

            patterns = [
                r'(\d+(?:[.,]\d{1,2})?)\s*(?:DH|dh|MAD|mad)',
                r'(?:DH|dh|MAD|mad)\s*(\d+(?:[.,]\d{1,2})?)',
                r'(\d+(?:[.,]\d{1,2})?)\s*د\.?\s*م',
                r'(\d+(?:[.,]\d{1,2})?)\s*(?:درهم|درهمًا)'
            ]

            for pattern in patterns:

                match = re.search(
                    pattern,
                    text
                )

                if match:

                    value = match.group(1)

                    value = value.replace(
                        ",",
                        "."
                    )

                    try:
                        return float(value)

                    except Exception:
                        pass

            return None

        def extract_image(img):
            """
            استخراج الصورة الحقيقية من img.
            يدعم lazy loading.
            """

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

            # srcset
            try:

                srcset = img.get_attribute(
                    "srcset"
                )

                if srcset:

                    parts = [
                        x.strip()
                        for x in srcset.split(",")
                    ]

                    for part in parts:

                        url = part.split(" ")[0].strip()

                        if url:
                            candidates.append(url)

            except Exception:
                pass

            # فحص الروابط
            for url in candidates:

                if not url:
                    continue

                low = url.lower()

                # استبعاد الصور الوهمية
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

                if any(
                    x in low
                    for x in blocked
                ):
                    continue

                # تحويل relative URL
                if url.startswith("//"):

                    url = "https:" + url

                elif url.startswith("/"):

                    url = (
                        "https://boughalaffiliate.com"
                        + url
                    )

                return url

            return None

        def looks_like_product_link(href):

            if not href:
                return False

            h = href.lower()

            product_patterns = [
                "/product/",
                "/products/",
                "/affiliate/product/",
                "/affiliate/products/",
                "/p/"
            ]

            return any(
                pattern in h
                for pattern in product_patterns
            )

        def find_title(container, fallback_text=""):

            title = ""

            # أولاً نحاول العناصر الدلالية
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

                    candidate = container.locator(
                        selector
                    ).first

                    if candidate.count() > 0:

                        # data-title
                        try:

                            data_title = candidate.get_attribute(
                                "data-title"
                            )

                            if data_title:

                                data_title = clean_text(
                                    data_title
                                )

                                if len(data_title) >= 3:
                                    return data_title

                        except Exception:
                            pass

                        candidate_text = clean_text(
                            candidate.inner_text()
                        )

                        if len(candidate_text) >= 3:

                            # لا نأخذ السعر كاسم
                            if extract_price(candidate_text) is None:
                                title = candidate_text
                                break

                except Exception:
                    pass

            if title:
                return title

            # fallback من النص
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

                # لا نأخذ السعر
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

        # =====================================================
        # 3. استخراج المنتجات من روابط المنتجات
        # =====================================================

        try:

            # انتظار إضافي للمحتوى الديناميكي
            try:
                page.wait_for_load_state(
                    "networkidle",
                    timeout=15000
                )
            except Exception:
                pass

            page.wait_for_timeout(5000)

            links = page.locator("a").all()

            print(
                f"🔎 عدد روابط <a> الموجودة في الصفحة: "
                f"{len(links)}"
            )

            seen_links = set()

            for link in links:

                try:

                    href = link.get_attribute(
                        "href"
                    )

                    if not looks_like_product_link(href):
                        continue

                    # تحويل الرابط إلى absolute
                    if href.startswith("/"):

                        absolute_href = (
                            "https://boughalaffiliate.com"
                            + href
                        )

                    elif href.startswith("//"):

                        absolute_href = (
                            "https:"
                            + href
                        )

                    else:

                        absolute_href = href

                    # منع التكرار
                    if absolute_href in seen_links:
                        continue

                    seen_links.add(
                        absolute_href
                    )

                    # =================================================
                    # البحث عن container الخاص بالمنتج
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

                            # إذا وجدنا صورة نعتبره غالباً البطاقة
                            if container.locator(
                                "img"
                            ).count() > 0:

                                break

                        except Exception:
                            break

                    # =================================================
                    # نص المنتج
                    # =================================================

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

                    # المنتجات غير المتوفرة
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

                    base_price = extract_price(
                        text
                    )

                    if base_price is None:

                        print(
                            f"⚠️ لم يتم العثور على السعر: "
                            f"{text[:100]}"
                        )

                        continue

                    # سعر البيع
                    your_price = int(
                        base_price + 50
                    )

                    # =================================================
                    # اسم المنتج
                    # =================================================

                    title = find_title(
                        container,
                        text
                    )

                    if not title:

                        print(
                            "⚠️ لم يتم العثور على اسم المنتج"
                        )

                        continue

                    # =================================================
                    # الصورة
                    # =================================================

                    image_url = None

                    images = container.locator(
                        "img"
                    ).all()

                    for img in images:

                        image_url = extract_image(
                            img
                        )

                        if image_url:
                            break

                    if not image_url:

                        print(
                            f"⚠️ صورة حقيقية غير موجودة: "
                            f"{title}"
                        )

                    # =================================================
                    # منع تكرار المنتج
                    # =================================================

                    duplicate = any(
                        p["title"].lower()
                        == title.lower()
                        for p in products_list
                    )

                    if duplicate:
                        continue

                    # =================================================
                    # إضافة المنتج
                    # =================================================

                    product = {
                        "id": f"shadhw_{len(products_list) + 1}",
                        "title": title,
                        "image": image_url or "",
                        "price": f"{your_price} DH",
                        "original_price": f"{int(base_price)} DH",
                        "original_link": absolute_href,
                        "status": "In Stock"
                    }

                    products_list.append(
                        product
                    )

                    print(
                        f"✅ PRODUCT: {title}"
                    )

                    print(
                        f"   💰 السعر الأصلي: "
                        f"{int(base_price)} DH"
                    )

                    print(
                        f"   🏷️ سعر البيع: "
                        f"{your_price} DH"
                    )

                    print(
                        f"   🖼️ الصورة: "
                        f"{image_url or 'غير موجودة'}"
                    )

                except Exception as item_error:

                    print(
                        f"⚠️ تخطي عنصر بسبب: "
                        f"{item_error}"
                    )

        except Exception as e:

            print(
                f"⚠️ خطأ أثناء استخراج المنتجات: "
                f"{str(e)}"
            )

        # =====================================================
        # 4. طريقة احتياطية لاكتشاف بطاقات المنتجات
        # =====================================================

        if len(products_list) == 0:

            print(
                "🔄 لم نجد روابط منتجات مباشرة."
            )

            print(
                "🔎 الانتقال إلى اكتشاف بطاقات المنتجات..."
            )

            try:

                possible_cards = page.locator(
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
                    f"🔎 عدد العناصر المرشحة: "
                    f"{len(possible_cards)}"
                )

                for card in possible_cards:

                    try:

                        text = clean_text(
                            card.inner_text()
                        )

                        if len(text) < 5:
                            continue

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

                        # الاسم
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

                                if href.startswith("/"):

                                    href = (
                                        "https://boughalaffiliate.com"
                                        + href
                                    )

                        except Exception:
                            pass

                        # الصورة
                        image_url = ""

                        images = card.locator(
                            "img"
                        ).all()

                        for img in images:

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
                            for p in products_list
                        )

                        if duplicate:
                            continue

                        your_price = int(
                            base_price + 50
                        )

                        product = {
                            "id": f"shadhw_{len(products_list) + 1}",
                            "title": title,
                            "image": image_url,
                            "price": f"{your_price} DH",
                            "original_price": f"{int(base_price)} DH",
                            "original_link": href,
                            "status": "In Stock"
                        }

                        products_list.append(
                            product
                        )

                        print(
                            f"✅ CARD PRODUCT: "
                            f"{title}"
                        )

                    except Exception:
                        continue

            except Exception as fallback_error:

                print(
                    f"⚠️ خطأ في نظام البطاقات: "
                    f"{fallback_error}"
                )

        # =====================================================
        # 5. لا نستخدم Unsplash كصورة وهمية
        # =====================================================

        if len(products_list) == 0:

            print(
                "❌ لم يتم العثور على أي منتج حقيقي."
            )

            print(
                "💾 لن يتم إنشاء منتجات وهمية."
            )

        # =====================================================
        # 6. حفظ products.json
        # =====================================================

        print(
            f"📦 تم استخراج "
            f"{len(products_list)} منتج."
        )

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
        # 7. حفظ HTML الكامل للتحليل
        # =====================================================

        with open(
            "source.html",
            "w",
            encoding="utf-8"
        ) as f:

            f.write(
                page.content()
            )

        print(
            "💾 تم حفظ products.json و source.html"
        )

        browser.close()


if __name__ == "__main__":
    run_automation()

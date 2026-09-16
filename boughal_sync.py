import os
import json
import time
import re
from urllib.parse import urljoin

from playwright.sync_api import sync_playwright

EMAIL = os.environ.get("BOUGHAL_EMAIL")
PASSWORD = os.environ.get("BOUGHAL_PASSWORD")

BASE_PRODUCTS_URL = "https://boughalaffiliate.com/affiliate/products"


# =========================================================
# Helpers
# =========================================================

def clean_text(text):
    if not text:
        return ""
    return re.sub(r"\s+", " ", text).strip()


def extract_price(text):
    if not text:
        return None

    patterns = [
        r"(\d+(?:[.,]\d+)?)\s*(?:DH|Dh|dh|MAD|mad)",
        r"(\d+(?:[.,]\d+)?)\s*(?:د\.?\s*م|درهم)",
        r"(?:DH|Dh|dh|MAD|mad)\s*(\d+(?:[.,]\d+)?)",
    ]

    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            try:
                return float(match.group(1).replace(",", "."))
            except:
                pass

    return None


def extract_image(container):
    selectors = [
        "img[src]",
        "img[data-src]",
        "img[data-image]",
        "img[data-original]",
        "img[data-lazy-src]",
        "img[data-lazy]",
        "img[data-url]",
        "img[data-original-src]",
    ]

    for selector in selectors:
        imgs = container.locator(selector)

        for i in range(imgs.count()):
            img = imgs.nth(i)

            for attr in [
                "src",
                "data-src",
                "data-image",
                "data-original",
                "data-lazy-src",
                "data-lazy",
                "data-url",
                "data-original-src",
            ]:
                value = img.get_attribute(attr)

                if value:
                    value = value.strip()

                    if (
                        value
                        and not value.startswith("data:")
                        and "placeholder" not in value.lower()
                        and "no-image" not in value.lower()
                        and "unsplash" not in value.lower()
                    ):
                        return value

            srcset = img.get_attribute("srcset")

            if srcset:
                parts = srcset.split(",")

                if parts:
                    last = parts[-1].strip().split(" ")[0]

                    if last and not last.startswith("data:"):
                        return last

    return ""


def looks_like_product_link(href):
    if not href:
        return False

    href = href.lower()

    product_patterns = [
        "/product/",
        "/products/",
        "/affiliate/product/",
        "/affiliate/products/",
        "/p/",
    ]

    return any(pattern in href for pattern in product_patterns)


def find_title(container):
    # 1. العناوين الواضحة
    for selector in [
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        ".title",
        ".product-title",
        ".product-name",
        ".name",
        "[data-title]",
    ]:
        elements = container.locator(selector)

        for i in range(elements.count()):
            element = elements.nth(i)

            text = (
                element.get_attribute("data-title")
                or element.inner_text()
            )

            text = clean_text(text)

            if text and len(text) >= 2:
                return text

    # 2. البحث داخل العناصر التي تحمل classes مرتبطة بالمنتج
    try:
        elements = container.locator(
            "[class*='title'], [class*='name'], [class*='product']"
        )

        for i in range(min(elements.count(), 20)):
            text = clean_text(elements.nth(i).inner_text())

            if text and len(text) >= 2 and len(text) <= 200:
                return text
    except:
        pass

    # 3. fallback من النص العام
    try:
        text = clean_text(container.inner_text())

        if text:
            lines = [
                clean_text(x)
                for x in text.split("\n")
                if clean_text(x)
            ]

            for line in lines:
                if (
                    len(line) >= 3
                    and len(line) <= 150
                    and not extract_price(line)
                ):
                    return line
    except:
        pass

    return "Produit"


# =========================================================
# Scrape current page
# =========================================================

def scrape_current_page(page, all_products):

    before_count = len(all_products)

    links = page.locator("a")

    for i in range(links.count()):

        try:
            link = links.nth(i)

            href = link.get_attribute("href")

            if not looks_like_product_link(href):
                continue

            absolute_href = urljoin(BASE_PRODUCTS_URL, href)

            # -------------------------------------------------
            # البحث عن container الخاص بالمنتج
            # -------------------------------------------------

            container = link

            for _ in range(6):
                try:
                    parent = container.locator("..")

                    if parent.count() == 0:
                        break

                    text = clean_text(parent.inner_text())

                    if (
                        len(text) > 10
                        and extract_price(text) is not None
                    ):
                        container = parent
                        break

                    container = parent

                except:
                    break

            # -------------------------------------------------
            # النص والسعر
            # -------------------------------------------------

            try:
                container_text = clean_text(container.inner_text())
            except:
                container_text = clean_text(link.inner_text())

            base_price = extract_price(container_text)

            if base_price is None:
                continue

            # -------------------------------------------------
            # العنوان
            # -------------------------------------------------

            title = find_title(container)

            if not title or title == "Produit":
                try:
                    title = clean_text(link.inner_text())
                except:
                    title = "Produit"

            if not title:
                title = "Produit"

            # -------------------------------------------------
            # الصورة
            # -------------------------------------------------

            image_url = extract_image(container)

            if image_url:
                image_url = urljoin(BASE_PRODUCTS_URL, image_url)

            # -------------------------------------------------
            # منع التكرار
            # -------------------------------------------------

            duplicate = False

            for existing in all_products:

                if existing.get("original_link") == absolute_href:
                    duplicate = True
                    break

                if (
                    existing.get("title", "").strip().lower()
                    == title.strip().lower()
                ):
                    duplicate = True
                    break

            if duplicate:
                continue

            # -------------------------------------------------
            # السعر النهائي
            # -------------------------------------------------

            your_price = int(round(base_price + 50))

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
                f"   ✅ {product['id']} | "
                f"{product['title']} | "
                f"{product['original_price']} → "
                f"{product['price']}"
            )

        except Exception as e:
            print(f"⚠️ خطأ أثناء استخراج منتج: {e}")

    # =====================================================
    # Fallback للبطاقات إذا لم تستخرج الروابط
    # =====================================================

    if len(all_products) == before_count:

        print("   🔎 لم نجد منتجات عبر الروابط، نجرب البطاقات...")

        card_selectors = [
            "[class*='product-card']",
            "[class*='product_card']",
            "[class*='product-item']",
            "[class*='product_item']",
            "[class*='card']",
            "article",
        ]

        for selector in card_selectors:

            cards = page.locator(selector)

            if cards.count() == 0:
                continue

            for i in range(cards.count()):

                try:
                    card = cards.nth(i)

                    text = clean_text(card.inner_text())

                    if not text:
                        continue

                    base_price = extract_price(text)

                    if base_price is None:
                        continue

                    title = find_title(card)

                    image_url = extract_image(card)

                    if image_url:
                        image_url = urljoin(
                            BASE_PRODUCTS_URL,
                            image_url
                        )

                    # البحث عن رابط داخل البطاقة
                    original_link = ""

                    card_links = card.locator("a")

                    for j in range(card_links.count()):
                        h = card_links.nth(j).get_attribute("href")

                        if looks_like_product_link(h):
                            original_link = urljoin(
                                BASE_PRODUCTS_URL,
                                h
                            )
                            break

                    if not original_link:
                        original_link = f"{BASE_PRODUCTS_URL}#{len(all_products)+1}"

                    duplicate = False

                    for existing in all_products:

                        if (
                            existing.get("original_link")
                            == original_link
                        ):
                            duplicate = True
                            break

                        if (
                            existing.get("title", "").lower()
                            == title.lower()
                        ):
                            duplicate = True
                            break

                    if duplicate:
                        continue

                    your_price = int(round(base_price + 50))

                    product = {
                        "id": f"shadhw_{len(all_products) + 1}",
                        "title": title,
                        "image": image_url,
                        "price": f"{your_price} DH",
                        "original_price": f"{int(base_price)} DH",
                        "original_link": original_link,
                        "status": "In Stock"
                    }

                    all_products.append(product)

                    print(
                        f"   ✅ {product['id']} | "
                        f"{product['title']} | "
                        f"{product['original_price']} → "
                        f"{product['price']}"
                    )

                except Exception as e:
                    print(f"⚠️ خطأ في البطاقة: {e}")

            if len(all_products) > before_count:
                break

    return all_products, len(all_products) - before_count


# =========================================================
# Main automation
# =========================================================

def run_automation():

    with sync_playwright() as p:

        print(
            "🔗 [1/4] إطلاق الروبوت المتخفي "
            "ومحاكاة متصفح بشري..."
        )

        # =================================================
        # تسجيل الدخول — لا تغيّر هذه الآلية
        # =================================================

        browser = p.chromium.launch(headless=True)

        context = browser.new_context(
            viewport={'width': 1280, 'height': 800},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                       "AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            locale="fr-FR"
        )

        page = context.new_page()

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

        print(
            "🛍️ الانتقال إلى صفحة المنتجات "
            "وسحب السلع المتوفرة..."
        )

        page.goto(
            BASE_PRODUCTS_URL,
            wait_until="networkidle"
        )

        time.sleep(6)

        # =================================================
        # اكتشاف آخر صفحة
        # =================================================

        print("🔢 البحث عن آخر صفحة في pagination...")

        page_numbers = [1]

        pagination_links = page.locator(
            "a[href*='?page='], "
            "a[href*='&page=']"
        )

        for i in range(pagination_links.count()):

            try:

                href = pagination_links.nth(i).get_attribute("href")

                if href:

                    match = re.search(
                        r"[?&]page=(\d+)",
                        href
                    )

                    if match:
                        page_numbers.append(
                            int(match.group(1))
                        )

            except:
                pass

        last_page = max(page_numbers)

        print(
            f"📚 آخر صفحة مكتشفة: {last_page}"
        )

        # =================================================
        # استخراج من الأقدم إلى الأحدث
        #
        # الصفحة 1 = الأحدث
        # الصفحة الأخيرة = الأقدم
        #
        # لذلك نزور:
        # last_page → ... → 3 → 2 → 1
        # =================================================

        all_products = []

        for page_number in range(
            last_page,
            0,
            -1
        ):

            if page_number == 1:

                url = BASE_PRODUCTS_URL

            else:

                url = (
                    f"{BASE_PRODUCTS_URL}"
                    f"?page={page_number}"
                )

            print("")
            print("=" * 60)
            print(
                f"📄 الصفحة {page_number}/{last_page}"
            )
            print(url)
            print("=" * 60)

            try:

                page.goto(
                    url,
                    wait_until="networkidle",
                    timeout=30000
                )

            except Exception as e:

                print(
                    f"⚠️ networkidle لم يكتمل: {e}"
                )

                try:
                    page.goto(
                        url,
                        wait_until="load",
                        timeout=30000
                    )
                except:
                    pass

            time.sleep(4)

            # screenshot للتشخيص
            try:
                page.screenshot(
                    path=f"page_{page_number}.png",
                    full_page=True
                )
            except:
                pass

            all_products, new_count = scrape_current_page(
                page,
                all_products
            )

            print(
                f"📦 منتجات جديدة من الصفحة "
                f"{page_number}: {new_count}"
            )

            print(
                f"📊 المجموع حتى الآن: "
                f"{len(all_products)}"
            )

        # =================================================
        # حفظ source.html
        # =================================================

        try:

            with open(
                "source.html",
                "w",
                encoding="utf-8"
            ) as f:

                f.write(page.content())

        except Exception as e:

            print(
                f"⚠️ تعذر حفظ source.html: {e}"
            )

        # =================================================
        # إعادة ترقيم IDs للتأكد من الترتيب
        # =================================================

        for index, product in enumerate(
            all_products,
            start=1
        ):

            product["id"] = f"shadhw_{index}"

        # =================================================
        # حفظ products.json
        # =================================================

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

        print("")
        print("=" * 60)
        print("🎉 انتهى الاستخراج")
        print("=" * 60)
        print(
            f"📄 عدد الصفحات: {last_page}"
        )
        print(
            f"🛍️ إجمالي المنتجات: {len(all_products)}"
        )

        if all_products:

            print(
                f"⬅️ أقدم منتج: "
                f"{all_products[0]['title']}"
            )

            print(
                f"➡️ أحدث منتج: "
                f"{all_products[-1]['title']}"
            )

        else:

            print(
                "⚠️ لم يتم العثور على أي منتج."
            )

        print(
            "💾 تم حفظ products.json بنجاح."
        )

        browser.close()


if __name__ == "__main__":
    run_automation()

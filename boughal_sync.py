import os
import json
import time
from playwright.sync_api import sync_playwright

EMAIL = os.environ.get("BOUGHAL_EMAIL")
PASSWORD = os.environ.get("BOUGHAL_PASSWORD")

def run_automation():
    with sync_playwright() as p:
        print("🔗 [1/4] إطلاق الروبوت والاتصال بالمنصة...")
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={'width': 1280, 'height': 1000},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
        page = context.new_page()
        
        # 1. تسجيل الدخول
        page.goto("https://boughalaffiliate.com", wait_until="load")
        time.sleep(3)
        page.fill("input[name='email']", EMAIL)
        page.fill("input[name='password']", PASSWORD)
        page.click("button[type='submit']")
        page.wait_for_load_state("networkidle")
        time.sleep(5)
        
        # 2. الانتقال لصفحة المنتجات
        print("🛍️ [2/4] فتح صفحة المنتجات والنزول التلقائي لتحميل كافة السلع...")
        page.goto("https://boughalaffiliate.com/affiliate/products", wait_until="networkidle")
        time.sleep(5)
        
        # تفعيل خاصية السكرول التلقائي (Scroll) لأسفل الصفحة لتحميل كافة المنتجات المختبئة
        for _ in range(5):  # ينزل لأسفل الصفحة 5 مرات متتالية
            page.evaluate("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)
            
        page.screenshot(path="page_preview.png")
        
        products_list = []
        
        # 3. كشط شامل ودقيق لكروت المنتجات الفعليه
        # البحث عن روابط المنتجات المباشرة داخل كود لارافيل للموقع
        elements = page.query_selector_all("a, div[class*='product'], div[class*='card']")
        counter = 1
        
        for el in elements:
            try:
                text = el.inner_text()
                href = el.get_attribute("href")
                
                # التحقق من أن العنصر يمثل منتجاً حقيقياً وليس رابطاً عادياً
                if href and ("product" in href.lower() or "/p/" in href or "/products/" in href):
                    # الفرز الذكي: تخطي السلع غير المتوفرة تماماً لمنع الـ Redirect للـ Dashboard
                    if "rupture" in text.lower() or "out" in text.lower() or "غير متوفر" in text:
                        continue
                    
                    lines = [line.strip() for line in text.split("\n") if line.strip()]
                    if len(lines) >= 2:
                        title = lines[0]
                        
                        # البحث عن السعر داخل النصوص
                        price_text = ""
                        for line in lines:
                            if any(char.isdigit() for char in line) and any(x in line.lower() for x in ["dh", "د", "درهم"]):
                                price_text = line
                                break
                        if not price_text:
                            price_text = lines[1]
                        
                        # احتساب السعر الجديد مع هامش ربحك (زيادة 50 درهم)
                        digits = ''.join(filter(str.isdigit, price_text))
                        base_price = int(digits) if digits else 120
                        your_price = base_price + 50
                        
                        # سحب الصورة الحقيقية للمنتج من الموقع
                        img_el = el.query_selector("img")
                        img_url = img_el.get_attribute("src") if img_el else "https://unsplash.com"
                        
                        # تفادي تكرار نفس المنتج
                        if not any(p['title'] == title for p in products_list):
                            products_list.append({
                                "id": f"shadhw_{counter}",
                                "title": title,
                                "image": img_url,
                                "price": f"{your_price} DH",
                                "original_link": href,
                                "status": "In Stock"
                            })
                            counter += 1
            except:
                continue
                
        # [4/4] حفظ وحقن البيانات النهائية في المستودع
        print(f"📦 تم استخراج {len(products_list)} منتج حقيقي متوفر بالمخزون.")
        with open("products.json", "w", encoding="utf-8") as f:
            json.dump(products_list, f, ensure_ascii=False, indent=4)
            
        with open("source.html", "w", encoding="utf-8") as f:
            f.write(page.content())
            
        browser.close()

if __name__ == "__main__":
    run_automation()

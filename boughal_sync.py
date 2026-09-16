import os
import json
import time
from playwright.sync_api import sync_playwright

EMAIL = os.environ.get("BOUGHAL_EMAIL")
PASSWORD = os.environ.get("BOUGHAL_PASSWORD")

def run_automation():
    with sync_playwright() as p:
        print("🔗 [1/4] تشغيل المتصفح والاتصال بالمنصة...")
        # تشغيل المتصفح مع إعدادات لتخطي جدران الحماية (Stealth Bypass)
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()
        
        # الدخول لصفحة الدخول الرئيسية
        page.goto("https://boughalaffiliate.com")
        page.wait_for_load_state("networkidle")
        time.sleep(3)
        
        print("🔐 [2/4] إدخال بيانات الحساب وتجاوز نظام الحماية...")
        # ملء الإيميل والباسورد بدقة بناءً على كود لارافيل للموقع
        page.fill("input[name='email']", EMAIL)
        page.fill("input[name='password']", PASSWORD)
        
        # الضغط على زر الاتصال وانتظار الجلسة لتثبيت الـ Cookies
        page.click("button[type='submit']")
        page.wait_for_load_state("networkidle")
        time.sleep(5)
        
        print("🛍️ [3/4] الدخول لصفحة المنتجات وجلب السلع المتوفرة فقط...")
        page.goto("https://boughalaffiliate.com/affiliate/products")
        page.wait_for_load_state("networkidle")
        time.sleep(6)
        
        # التقاط صورة شاشة جديدة للتأكد من تخطي صفحة الحماية بنجاح
        page.screenshot(path="page_preview.png")
        
        products_list = []
        
        # فحص كود الصفحة واستخراج كروت المنتجات تلقائياً بناءً على الهيكلية المحدثة
        # سنبحث عن عناصر الكروت (الأسماء، الصور، الأزرار، وحالة المخزون)
        product_cards = page.query_selector_all("div.card, div.product-item, .box") 
        
        for index, card in enumerate(product_cards):
            try:
                # قراءة النص بالكامل داخل الكرت للتأكد من حالة المخزون
                card_text = card.inner_text().lower()
                
                # فحص ذكي: إذا كان المنتج يحتوي على عبارات نفاد المخزون، نتخطاه فوراً لتفادي الـ Redirect للـ Dashboard
                if "rupture" in card_text or "out of stock" in card_text or "غير متوفر" in card_text:
                    continue
                    
                # استخراج العنوان والصورة والسعر (بناءً على التخمين الهيكلي الذكي للبطاقة)
                title_el = card.query_selector("h4, h5, .title, .name")
                price_el = card.query_selector(".price, span.text-primary, .amount")
                img_el = card.query_selector("img")
                link_el = card.query_selector("a")
                
                if title_el and price_el and img_el:
                    title = title_el.inner_text().strip()
                    price_raw = price_el.inner_text().strip()
                    img_url = img_el.get_attribute("src")
                    # جلب رابط صفحة الهبوط للمنتج إذا توفر
                    landing_url = link_el.get_attribute("href") if link_el else "#"
                    
                    # تنظيف السعر وحساب هامش ربحك (مثال: زيادة 50 درهم)
                    digits = ''.join(filter(str.isdigit, price_raw))
                    base_price = int(digits) if digits else 0
                    your_price = base_price + 50 if base_price > 0 else 150 # سعر افتراضي إذا فشل القراءة الرقمية
                    
                    products_list.append({
                        "id": f"shadhw_{index}",
                        "title": title,
                        "image": img_url,
                        "price": f"{your_price} DH",
                        "original_link": landing_url,
                        "status": "In Stock"
                    })
            except Exception as e:
                continue
                
        # [4/4] حفظ البيانات النهائية المفلترة والمحدثة في ملف JSON للكتالوج
        print(f"📦 [4/4] تم العثور على {len(products_list)} منتج متوفر بالمخزون. تحديث الكتالوج...")
        with open("products.json", "w", encoding="utf-8") as f:
            json.dump(products_list, f, ensure_ascii=False, indent=4)
            
        # حفظ كود الصفحة الجديد للاطلاع الاحتياطي
        with open("source.html", "w", encoding="utf-8") as f:
            f.write(page.content())
            
        print("✅ اكتمل التحديث بنجاح! ملف products.json جاهز لتغذية واجهة موقعك.")
        browser.close()

if __name__ == "__main__":
    run_automation()

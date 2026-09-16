import os
import time
from playwright.sync_api import sync_playwright

# جلب بيانات تسجيل الدخول بشكل آمن من خزنة جيت هاب
EMAIL = os.environ.get("BOUGHAL_EMAIL")
PASSWORD = os.environ.get("BOUGHAL_PASSWORD")

def run_diagnostic():
    with sync_playwright() as p:
        print("🔗 جاري تشغيل المتصفح وفتح صفحة تسجيل الدخول لـ Boughal...")
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        # الانتقال لصفحة تسجيل الدخول
        page.goto("https://boughalaffiliate.com")
        page.wait_for_load_state("networkidle")
        
        # إدخال البيانات وتسجيل الدخول
        print("🔐 جاري إدخال البيانات وتأكيد الدخول...")
        page.fill("input[type='email']", EMAIL)
        page.fill("input[type='password']", PASSWORD)
        page.click("button[type='submit']")
        page.wait_for_load_state("networkidle")
        time.sleep(3)
        
        # الانتقال لصفحة المنتجات الفعلية
        print("🛍️ جاري الانتقال لصفحة المنتجات...")
        page.goto("https://boughalaffiliate.com/affiliate/products")
        page.wait_for_load_state("networkidle")
        time.sleep(5) # وقت إضافي لضمان تحميل جميع الصور بالكامل
        
        # 1. التقاط صورة شاشة لنرى بالضبط ما يراه الروبوت
        page.screenshot(path="page_preview.png")
        print("📸 بنجاح! تم حفظ لقطة الشاشة باسم 'page_preview.png'")
        
        # 2. استخراج كود الصفحة بالكامل لقراءته ومعرفة الكلاسات
        html_content = page.content()
        with open("source.html", "w", encoding="utf-8") as f:
            f.write(html_content)
        print("📄 بنجاح! تم حفظ كود الصفحة بالكامل في ملف 'source.html'")
        
        browser.close()

if __name__ == "__main__":
    run_diagnostic()

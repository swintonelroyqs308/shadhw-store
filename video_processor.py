import json
import os


PRODUCTS_FILE = "products.json"


print("\n========================================")
print("SHADHW — PRODUCT TEST FINDER")
print("========================================")


# ---------------------------------------------------------
# التأكد من وجود products.json
# ---------------------------------------------------------

if not os.path.exists(PRODUCTS_FILE):
    print(f"\nERROR: الملف غير موجود: {PRODUCTS_FILE}")
    raise SystemExit(1)


# ---------------------------------------------------------
# قراءة المنتجات
# ---------------------------------------------------------

with open(PRODUCTS_FILE, "r", encoding="utf-8") as f:
    products = json.load(f)


if not isinstance(products, list):
    print("\nERROR: products.json ليس List من المنتجات.")
    raise SystemExit(1)


print(f"\nعدد المنتجات: {len(products)}")


# ---------------------------------------------------------
# البحث عن أول منتج صالح
# ---------------------------------------------------------

found = None

for index, product in enumerate(products):

    if not isinstance(product, dict):
        continue

    product_id = product.get("id")
    source_id = product.get("source_id")
    price = product.get("price")
    videos = product.get("videos") or []

    if not source_id:
        continue

    if not videos:
        continue

    # أول فيديو فقط
    video_url = videos[0]

    if not video_url:
        continue

    found = {
        "index": index,
        "id": product_id,
        "source_id": source_id,
        "price": price,
        "video_count": len(videos),
        "video_index": 1,
        "video_url": video_url,
    }

    break


# ---------------------------------------------------------
# النتيجة
# ---------------------------------------------------------

if not found:

    print("\nلم يتم العثور على منتج صالح للاختبار.")
    print("الشروط:")
    print("- source_id موجود")
    print("- videos موجودة")
    print("- أول video غير فارغ")

    raise SystemExit(0)


print("\n========================================")
print("PRODUCT FOUND")
print("========================================")

print(f"\nترتيب المنتج: {found['index'] + 1}")
print(f"ID:          {found['id']}")
print(f"source_id:   {found['source_id']}")
print(f"السعر:       {found['price']}")
print(f"عدد الفيديوهات: {found['video_count']}")
print(f"الفيديو المختار: 1")

print("\nVideo URL:")
print(found["video_url"])

print("\n========================================")
print("EXPECTED FILE")
print("========================================")

print(
    f"{found['source_id']}-{found['price']}.mp4"
)

print("\n========================================")
print("READY FOR TEST")
print("========================================")

const WHATSAPP_NUMBER = '212600000000'; // بدّل هذا الرقم برقم واتساب ديالك
const CART_KEY = 'shadhw_cart';
let products = [];
let currentProduct = null;
let mediaItems = [];
let activeMediaIndex = 0;

const $ = (selector) => document.querySelector(selector);

function escapeHtml(value) {
    return String(value ?? '').replace(/[&<>'"]/g, char => ({
        '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#039;', '"': '&quot;'
    }[char]));
}
function parsePrice(value) {
    const match = String(value ?? '').replace(',', '.').match(/[0-9]+(?:\.[0-9]+)?/);
    return match ? Number(match[0]) : 0;
}
function formatPrice(value) { return `${parsePrice(value)} DH`; }
function getImages(product) {
    return (Array.isArray(product.images) ? product.images : []).filter(src => src && !/logo\.png|urlanding-icon/i.test(src));
}
function getVideos(product) { return Array.isArray(product.videos) ? product.videos.filter(Boolean) : []; }
function getCart() {
    try { return JSON.parse(localStorage.getItem(CART_KEY) || '[]'); } catch { return []; }
}
function saveCart(cart) {
    localStorage.setItem(CART_KEY, JSON.stringify(cart));
    updateCartCount();
}
function updateCartCount() {
    const count = getCart().reduce((sum, item) => sum + Number(item.quantity || 1), 0);
    const el = $('#cartCount');
    if (el) el.textContent = count;
}

function addToCart(size) {
    const sizes = Array.isArray(currentProduct.sizes) ? currentProduct.sizes.filter(Boolean) : [];
    if (sizes.length && !size) {
        $('#selectionError')?.classList.add('show');
        document.querySelector('.sizes')?.scrollIntoView({ behavior: 'smooth', block: 'center' });
        return false;
    }
    const cart = getCart();
    const existing = cart.find(item => item.id === currentProduct.id && String(item.size || '') === String(size || ''));
    if (existing) existing.quantity = Number(existing.quantity || 1) + 1;
    else cart.push({ id: currentProduct.id, size: size || '', quantity: 1 });
    saveCart(cart);
    return true;
}

function renderMainMedia(index) {
    activeMediaIndex = index;
    const item = mediaItems[index];
    const wrap = $('#mainMedia');
    if (!item || !wrap) return;
    const content = item.type === 'video'
        ? `<video src="${escapeHtml(item.src)}" controls playsinline preload="metadata"></video>`
        : `<img src="${escapeHtml(item.src)}" alt="${escapeHtml(currentProduct.title)}">`;
    wrap.querySelector('.main-media-content').innerHTML = content;
    wrap.querySelectorAll('.gallery-thumb').forEach((thumb, i) => thumb.classList.toggle('active', i === index));
}

function openLightbox(index = activeMediaIndex) {
    if (!mediaItems.length) return;
    activeMediaIndex = index;
    const lightbox = $('#lightbox');
    lightbox.classList.remove('hidden');
    lightbox.setAttribute('aria-hidden', 'false');
    document.body.style.overflow = 'hidden';
    renderLightbox();
}
function closeLightbox() {
    const lightbox = $('#lightbox');
    lightbox.classList.add('hidden');
    lightbox.setAttribute('aria-hidden', 'true');
    const video = $('#lightboxVideo');
    video.pause();
    video.removeAttribute('src');
    document.body.style.overflow = '';
}
function renderLightbox() {
    const item = mediaItems[activeMediaIndex];
    const img = $('#lightboxImage');
    const video = $('#lightboxVideo');
    if (!item) return;
    if (item.type === 'video') {
        img.classList.add('hidden');
        video.classList.remove('hidden');
        video.src = item.src;
        video.play().catch(() => {});
    } else {
        video.pause();
        video.classList.add('hidden');
        video.removeAttribute('src');
        img.classList.remove('hidden');
        img.src = item.src;
        img.alt = currentProduct.title || '';
    }
}
function moveLightbox(step) {
    if (!mediaItems.length) return;
    activeMediaIndex = (activeMediaIndex + step + mediaItems.length) % mediaItems.length;
    renderLightbox();
    renderMainMedia(activeMediaIndex);
}

function renderGallery(product) {
    const images = getImages(product);
    const videos = getVideos(product);
    mediaItems = [
        ...images.map(src => ({ type: 'image', src })),
        ...videos.map(src => ({ type: 'video', src }))
    ];

    const gallery = $('#gallery');
    if (!mediaItems.length) {
        gallery.innerHTML = '<div class="main-media"><div class="loading">لا توجد صور أو فيديوهات لهذا المنتج</div></div>';
        return;
    }

    gallery.innerHTML = `
        <div class="main-media" id="mainMedia">
            <div class="main-media-content" style="width:100%;height:100%;display:flex;align-items:center;justify-content:center;"></div>
            <button class="zoom-hint" id="zoomButton" type="button">تكبير الصورة ⤢</button>
        </div>
        <div class="gallery-thumbs">
            ${mediaItems.map((item, index) => item.type === 'image'
                ? `<button class="gallery-thumb ${index === 0 ? 'active' : ''}" type="button" data-index="${index}" aria-label="الصورة ${index + 1}"><img src="${escapeHtml(item.src)}" alt=""></button>`
                : `<button class="gallery-thumb gallery-video-button ${index === 0 ? 'active' : ''}" type="button" data-index="${index}" aria-label="الفيديو ${index + 1}"><span class="gallery-video-thumb"><video src="${escapeHtml(item.src)}" muted playsinline preload="metadata"></video><i>▶</i></span></button>`
            ).join('')}
        </div>`;

    gallery.querySelectorAll('.gallery-thumb').forEach(button => {
        button.addEventListener('click', () => renderMainMedia(Number(button.dataset.index)));
    });
    $('#zoomButton').addEventListener('click', () => openLightbox(activeMediaIndex));
    renderMainMedia(0);
}

function renderUpsell() {
    const others = products
        .filter(p => p.id !== currentProduct.id)
        .slice()
        .reverse()
        .slice(0, 10);
    const section = $('#upsell');
    if (!others.length) { section.classList.add('hidden'); return; }
    $('#upsellGrid').innerHTML = others.map(product => {
        const image = getImages(product)[0];
        return `
            <article class="product-card">
                <a href="product.html?id=${encodeURIComponent(product.id)}" class="product-card-image">
                    ${image ? `<img src="${escapeHtml(image)}" alt="${escapeHtml(product.title)}" loading="lazy">` : '<div class="loading">لا توجد صورة</div>'}
                </a>
                <div class="product-card-body">
                    <h3 class="product-card-title">${escapeHtml(product.title || 'القطعة')}</h3>
                    <div class="product-card-price">${formatPrice(product.price)}</div>
                    <a href="product.html?id=${encodeURIComponent(product.id)}" class="product-card-link">عرض التفاصيل</a>
                </div>
            </article>`;
    }).join('');
}

function renderProduct(product) {
    currentProduct = product;
    document.title = product.title || 'المنتج';
    const sizes = Array.isArray(product.sizes) ? product.sizes.filter(Boolean) : [];
    const description = product.description ? escapeHtml(product.description) : 'لا توجد تفاصيل إضافية لهذا المنتج حالياً.';

    $('#productPage').innerHTML = `
        <div class="product-detail-grid">
            <div class="gallery" id="gallery"></div>
            <div class="product-info">
                <h1 class="product-title">${escapeHtml(product.title || 'القطعة')}</h1>
                <div class="product-price">${formatPrice(product.price)}</div>
                <div class="product-description">${description}</div>
                ${sizes.length ? `
                    <div class="option-block">
                        <div class="option-label">
                            <span>اختاري المقاس</span>
                            <span class="option-required">ضروري</span>
                        </div>
                        <div class="sizes" id="sizes">
                            ${sizes.map(size => `<button class="size-button" type="button" data-size="${escapeHtml(size)}">${escapeHtml(size)}</button>`).join('')}
                        </div>
                        <div id="selectionError" class="selection-error">اختاري المقاس أولاً باش نضيفو القطعة للسلة.</div>
                    </div>` : ''}
                <div class="product-actions">
                    <button id="addCart" class="add-cart-button" type="button">أضيفي للسلة</button>
                    <button id="directWhatsApp" class="product-whatsapp" type="button">الطلب مباشرة عبر واتساب</button>
                </div>
            </div>
        </div>
        <section id="upsell" class="upsell-section">
            <div class="upsell-heading">
                <h2>قد تعجبك أيضاً ✨</h2>
            </div>
            <div id="upsellGrid" class="upsell-grid"></div>
        </section>`;

    renderGallery(product);

    let selectedSize = '';
    document.querySelectorAll('.size-button').forEach(button => {
        button.addEventListener('click', () => {
            selectedSize = button.dataset.size;
            document.querySelectorAll('.size-button').forEach(b => b.classList.remove('selected'));
            button.classList.add('selected');
            $('#selectionError')?.classList.remove('show');
        });
    });

    $('#addCart').addEventListener('click', () => {
        if (addToCart(selectedSize)) {
            $('#addCart').textContent = 'تمت الإضافة ✓';
            setTimeout(() => { $('#addCart').textContent = 'أضيفي للسلة'; }, 1400);
        }
    });

    $('#directWhatsApp').addEventListener('click', () => {
        const sizesList = sizes;
        if (sizesList.length && !selectedSize) {
            $('#selectionError').classList.add('show');
            document.querySelector('.sizes').scrollIntoView({ behavior: 'smooth', block: 'center' });
            return;
        }
        const lines = [
            'السلام عليكم، بغيت نطلب هاد القطعة من المتجر:',
            `المنتج: ${product.title}`,
            `الثمن: ${formatPrice(product.price)}`,
            selectedSize ? `المقاس: ${selectedSize}` : '',
            '', 'الاسم:', 'المدينة:', 'العنوان:', 'الهاتف:'
        ].filter(Boolean);
        window.open(`https://wa.me/${WHATSAPP_NUMBER}?text=${encodeURIComponent(lines.join('\n'))}`, '_blank');
    });

    renderUpsell();
}

async function init() {
    updateCartCount();
    const id = new URLSearchParams(location.search).get('id');
    if (!id) {
        $('#productPage').innerHTML = '<div class="empty-message"><h3>المنتج غير موجود</h3><p><a href="index.html">العودة للمنتجات</a></p></div>';
        return;
    }
    try {
        const response = await fetch('products.json', { cache: 'no-store' });
        if (!response.ok) throw new Error('Failed');
        products = await response.json();
        const product = products.find(p => String(p.id) === String(id));
        if (!product) throw new Error('Not found');
        renderProduct(product);
    } catch {
        $('#productPage').innerHTML = '<div class="empty-message"><h3>ما قدرناش نحمّلو هاد المنتج</h3><p><a href="index.html">العودة للمنتجات</a></p></div>';
    }
}

$('#lightboxClose').addEventListener('click', closeLightbox);
$('#lightboxPrev').addEventListener('click', () => moveLightbox(-1));
$('#lightboxNext').addEventListener('click', () => moveLightbox(1));
$('#lightbox').addEventListener('click', event => {
    if (event.target.id === 'lightbox') closeLightbox();
});
document.addEventListener('keydown', event => {
    if (event.key === 'Escape') closeLightbox();
    if (!$('#lightbox').classList.contains('hidden')) {
        if (event.key === 'ArrowLeft') moveLightbox(1);
        if (event.key === 'ArrowRight') moveLightbox(-1);
    }
});
$('#cartButton')?.addEventListener('click', () => {
    // في صفحة المنتج نكتفي بالرجوع للسلة المخزنة؛ السلة الكاملة موجودة في الصفحة الرئيسية.
    location.href = 'index.html?cart=1#products';
});

init();

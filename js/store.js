const WHATSAPP_NUMBER = '212600000000'; // بدّل هذا الرقم برقم واتساب ديالك
const CART_KEY = 'shadhw_cart';
let products = [];

const $ = (selector) => document.querySelector(selector);

function escapeHtml(value) {
    return String(value ?? '').replace(/[&<>'"]/g, char => ({
        '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#039;', '"': '&quot;'
    }[char]));
}

function getProductImage(product) {
    const images = Array.isArray(product.images) ? product.images : [];
    const valid = images.filter(src => src && !/logo\.png|urlanding-icon/i.test(src));
    return valid[0] || '';
}

function getCart() {
    try { return JSON.parse(localStorage.getItem(CART_KEY) || '[]'); }
    catch { return []; }
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
function parsePrice(value) {
    const match = String(value ?? '').replace(',', '.').match(/[0-9]+(?:\.[0-9]+)?/);
    return match ? Number(match[0]) : 0;
}
function formatPrice(value) {
    return `
        <span class="price-display" style="display:inline-flex;direction:ltr;gap:4px;">
            <span dir="rtl">درهم</span>
            <span dir="ltr">${parsePrice(value)}</span>
        </span>
    `;
}

function renderProducts(list) {
    const grid = $('#productsGrid');
    const empty = $('#emptyMessage');
    $('#productsCount').textContent = `${list.length} قطعة`;

    if (!list.length) {
        grid.innerHTML = '';
        empty.classList.remove('hidden');
        return;
    }
    empty.classList.add('hidden');

    grid.innerHTML = list.map(product => {
        const image = getProductImage(product);
        const imageHtml = image
            ? `<img src="${escapeHtml(image)}" alt="${escapeHtml(product.title)}" loading="lazy">`
            : `<div class="loading">لا توجد صورة</div>`;
        return `
            <article class="product-card">
                <a href="product.html?id=${encodeURIComponent(product.id)}" class="product-card-image" aria-label="عرض ${escapeHtml(product.title)}">
                    ${imageHtml}
                </a>
                <div class="product-card-body">
                    <h3 class="product-card-title">${escapeHtml(product.title || 'القطعة')}</h3>
                    <div class="product-card-price">${formatPrice(product.price)}</div>
                    <a href="product.html?id=${encodeURIComponent(product.id)}" class="product-card-link">عرض التفاصيل</a>
                </div>
            </article>`;
    }).join('');
}

function openCart() {
    const overlay = $('#cartOverlay');
    overlay.classList.remove('hidden');
    overlay.setAttribute('aria-hidden', 'false');
    renderCart();
    document.body.style.overflow = 'hidden';
}
function closeCart() {
    const overlay = $('#cartOverlay');
    overlay.classList.add('hidden');
    overlay.setAttribute('aria-hidden', 'true');
    document.body.style.overflow = '';
}

function renderCart() {
    const container = $('#cartItems');
    const cart = getCart();
    if (!cart.length) {
        container.innerHTML = '<div class="cart-empty">السلة خاوية حالياً.<br>اختاري قطعة باش تبداي.</div>';
        $('#cartTotal').innerHTML = formatPrice(0);
        return;
    }

    let total = 0;
    container.innerHTML = cart.map((item, index) => {
        const product = products.find(p => p.id === item.id);
        if (!product) return '';
        const quantity = Number(item.quantity || 1);
        const price = parsePrice(product.price);
        total += price * quantity;
        const sizeText = item.size ? `المقاس: ${escapeHtml(item.size)}` : 'بدون مقاس';
        return `
            <div class="cart-item">
                ${getProductImage(product) ? `<img src="${escapeHtml(getProductImage(product))}" alt="">` : '<div></div>'}
                <div>
                    <p class="cart-item-title">${escapeHtml(product.title)}</p>
                    <div class="cart-item-meta">${sizeText} · الكمية: ${quantity}</div>
                    <button class="cart-remove" type="button" data-index="${index}">حذف</button>
                </div>
                <div class="cart-item-price">${formatPrice(price * quantity)}</div>
            </div>`;
    }).join('');
    $('#cartTotal').innerHTML = formatPrice(total);

    container.querySelectorAll('.cart-remove').forEach(button => {
        button.addEventListener('click', () => {
            const current = getCart();
            current.splice(Number(button.dataset.index), 1);
            saveCart(current);
            renderCart();
        });
    });
}

function orderViaWhatsApp() {
    const cart = getCart();
    if (!cart.length) return;
    let total = 0;
    const lines = ['السلام عليكم، بغيت نطلب من المتجر:', ''];
    cart.forEach((item, i) => {
        const product = products.find(p => p.id === item.id);
        if (!product) return;
        const qty = Number(item.quantity || 1);
        const price = parsePrice(product.price) * qty;
        total += price;
        lines.push(`${i + 1}. ${product.title}`);
        if (item.size) lines.push(`المقاس: ${item.size}`);
        lines.push(`الكمية: ${qty}`);
        lines.push(`الثمن: درهم ${price}`);
        lines.push('');
    });
    lines.push(`المجموع: درهم ${total}`);
    lines.push('', 'الاسم:', 'المدينة:', 'العنوان:', 'الهاتف:');
    window.open(`https://wa.me/${WHATSAPP_NUMBER}?text=${encodeURIComponent(lines.join('\n'))}`, '_blank');
}

async function loadProducts() {
    try {
        const response = await fetch('products.json', { cache: 'no-store' });
        if (!response.ok) throw new Error('Failed to load products');
        products = await response.json();
        renderProducts(products);
        updateCartCount();
    } catch (error) {
        $('#productsGrid').innerHTML = '<div class="loading">وقع مشكل في تحميل المنتجات. عاودي المحاولة.</div>';
        $('#productsCount').textContent = '';
    }
}

$('#searchInput')?.addEventListener('input', event => {
    const query = event.target.value.trim().toLowerCase();
    const filtered = products.filter(product => {
        const text = `${product.title || ''} ${product.description || ''}`.toLowerCase();
        return text.includes(query);
    });
    renderProducts(filtered);
});
$('#cartButton')?.addEventListener('click', openCart);
$('#closeCart')?.addEventListener('click', closeCart);
$('#cartBackdrop')?.addEventListener('click', closeCart);
$('#whatsappOrder')?.addEventListener('click', orderViaWhatsApp);

document.addEventListener('keydown', event => {
    if (event.key === 'Escape') closeCart();
});

loadProducts().then(() => {
    if (new URLSearchParams(location.search).get('cart') === '1') openCart();
});

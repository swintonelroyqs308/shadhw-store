const WHATSAPP_NUMBER = '212630000552';
const CART_KEY = 'shadhw_cart';

let products = [];
let currentProduct = null;
let mediaItems = [];
let activeMediaIndex = 0;

const $ = (selector) => document.querySelector(selector);

function escapeHtml(value) {
    return String(value ?? '').replace(/[&<>'"]/g, char => ({
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        "'": '&#039;',
        '"': '&quot;'
    }[char]));
}

function parsePrice(value) {
    const match = String(value ?? '')
        .replace(',', '.')
        .match(/[0-9]+(?:\.[0-9]+)?/);

    return match ? Number(match[0]) : 0;
}

function formatPrice(value) {
    return `درهم ${parsePrice(value)}`;
}

function getImages(product) {
    if (!Array.isArray(product?.images)) {
        return [];
    }

    return product.images.filter(
        src => src && !/logo\.png|urlanding-icon/i.test(src)
    );
}

function getVideos(product) {
    if (!Array.isArray(product?.videos)) {
        return [];
    }

    return product.videos.filter(Boolean);
}

function getCart() {
    try {
        return JSON.parse(localStorage.getItem(CART_KEY) || '[]');
    } catch {
        return [];
    }
}

function saveCart(cart) {
    localStorage.setItem(CART_KEY, JSON.stringify(cart));
    updateCartCount();
}

function updateCartCount() {
    const count = getCart().reduce(
        (sum, item) => sum + Number(item.quantity || 1),
        0
    );

    const el = $('#cartCount');

    if (el) {
        el.textContent = count;
    }
}

function getProductId() {
    return new URLSearchParams(location.search).get('id');
}

function findProduct(id) {
    return products.find(product => String(product.id) === String(id));
}

function addToCart(product, size = '') {
    const cart = getCart();

    const existing = cart.find(item =>
        String(item.id) === String(product.id) &&
        String(item.size || '') === String(size || '')
    );

    if (existing) {
        existing.quantity = Number(existing.quantity || 1) + 1;
    } else {
        cart.push({
            id: product.id,
            size: size || '',
            quantity: 1
        });
    }

    saveCart(cart);
}

function openCart() {
    const overlay = $('#cartOverlay');

    if (!overlay) return;

    overlay.classList.remove('hidden');
    overlay.setAttribute('aria-hidden', 'false');

    renderCart();

    document.body.style.overflow = 'hidden';
}

function closeCart() {
    const overlay = $('#cartOverlay');

    if (!overlay) return;

    overlay.classList.add('hidden');
    overlay.setAttribute('aria-hidden', 'true');

    document.body.style.overflow = '';
}

function renderCart() {
    const container = $('#cartItems');

    if (!container) return;

    const cart = getCart();

    if (!cart.length) {
        container.innerHTML = `
            <div class="cart-empty">
                السلة خاوية حالياً.<br>
                اختاري قطعة باش تبداي.
            </div>
        `;

        if ($('#cartTotal')) {
            $('#cartTotal').textContent = 'درهم 0';
        }

        return;
    }

    let total = 0;

    container.innerHTML = cart.map((item, index) => {
        const product = products.find(
            p => String(p.id) === String(item.id)
        );

        if (!product) return '';

        const quantity = Number(item.quantity || 1);
        const price = parsePrice(product.price);
        const itemTotal = price * quantity;

        total += itemTotal;

        const sizeText = item.size
            ? `المقاس: ${escapeHtml(item.size)}`
            : 'بدون مقاس';

        const image = getImages(product)[0] || '';

        return `
            <div class="cart-item">

                ${
                    image
                        ? `<img src="${escapeHtml(image)}" alt="">`
                        : '<div></div>'
                }

                <div>
                    <p class="cart-item-title">
                        ${escapeHtml(product.title)}
                    </p>

                    <div class="cart-item-meta">
                        ${sizeText} · الكمية: ${quantity}
                    </div>

                    <button
                        class="cart-remove"
                        type="button"
                        data-index="${index}"
                    >
                        حذف
                    </button>
                </div>

                <div class="cart-item-price">
                    ${formatPrice(itemTotal)}
                </div>

            </div>
        `;
    }).join('');

    if ($('#cartTotal')) {
        $('#cartTotal').textContent = `درهم ${total}`;
    }

    container.querySelectorAll('.cart-remove').forEach(button => {
        button.addEventListener('click', () => {
            const current = getCart();

            current.splice(
                Number(button.dataset.index),
                1
            );

            saveCart(current);
            renderCart();
        });
    });
}

function renderGallery(product) {
    const gallery = $('#productGallery');

    if (!gallery) return;

    const images = getImages(product);
    const videos = getVideos(product);

    mediaItems = [
        ...images.map(src => ({
            type: 'image',
            src
        })),
        ...videos.map(src => ({
            type: 'video',
            src
        }))
    ];

    activeMediaIndex = 0;

    if (!mediaItems.length) {
        gallery.innerHTML = `
            <div class="loading">
                لا توجد صورة
            </div>
        `;
        return;
    }

    gallery.innerHTML = mediaItems.map((media, index) => {
        if (media.type === 'video') {
            return `
                <video
                    class="product-media"
                    src="${escapeHtml(media.src)}"
                    controls
                    playsinline
                    preload="metadata"
                    data-media-index="${index}"
                ></video>
            `;
        }

        return `
            <img
                class="product-media"
                src="${escapeHtml(media.src)}"
                alt="${escapeHtml(product.title)}"
                data-media-index="${index}"
            >
        `;
    }).join('');
}

function renderProduct(product) {
    currentProduct = product;

    const title = $('#productTitle');
    const description = $('#productDescription');
    const price = $('#productPrice');
    const sizesContainer = $('#sizes');

    if (title) {
        title.textContent = product.title || 'القطعة';
    }

    if (description) {
        description.innerHTML = escapeHtml(
            product.description || ''
        ).replace(/\n/g, '<br>');
    }

    if (price) {
        price.textContent = formatPrice(product.price);
    }

    renderGallery(product);

    const sizes =
        Array.isArray(product.sizes)
            ? product.sizes.filter(Boolean)
            : [];

    if (sizesContainer) {
        sizesContainer.innerHTML = sizes.length
            ? sizes.map(size => `
                <button
                    class="size-button"
                    type="button"
                    data-size="${escapeHtml(size)}"
                >
                    ${escapeHtml(size)}
                </button>
            `).join('')
            : '';
    }

    const optionBlock = sizesContainer?.closest('.option-block');

    if (optionBlock) {
        optionBlock.classList.toggle(
            'hidden',
            sizes.length === 0
        );
    }

    const addButton = $('#addToCart');

    if (addButton) {
        addButton.onclick = () => {
            let selectedSize = '';

            const selected = document.querySelector(
                '.size-button.selected'
            );

            if (sizes.length && !selected) {
                alert('اختاري المقاس أولاً');
                return;
            }

            if (selected) {
                selectedSize = selected.dataset.size || '';
            }

            addToCart(product, selectedSize);

            openCart();
        };
    }

    sizesContainer?.querySelectorAll('.size-button')
        .forEach(button => {
            button.addEventListener('click', () => {
                sizesContainer
                    .querySelectorAll('.size-button')
                    .forEach(item => {
                        item.classList.remove('selected');
                    });

                button.classList.add('selected');
            });
        });

    renderUpsell(product);
}

function renderUpsell(product) {
    const container = $('#upsellProducts');

    if (!container) return;

    const others = products
        .filter(item => String(item.id) !== String(product.id))
        .slice(0, 4);

    container.innerHTML = others.map(item => {
        const image = getImages(item)[0] || '';

        return `
            <article class="upsell-card">

                ${
                    image
                        ? `<img
                            src="${escapeHtml(image)}"
                            alt="${escapeHtml(item.title)}"
                            loading="lazy"
                        >`
                        : ''
                }

                <h3>
                    ${escapeHtml(item.title || 'القطعة')}
                </h3>

                <div class="upsell-price">
                    ${formatPrice(item.price)}
                </div>

                <a
                    href="product.html?id=${encodeURIComponent(item.id)}"
                >
                    عرض التفاصيل
                </a>

            </article>
        `;
    }).join('');
}

async function loadProducts() {
    try {
        const response = await fetch(
            'products.json',
            { cache: 'no-store' }
        );

        if (!response.ok) {
            throw new Error('Failed to load products');
        }

        products = await response.json();

        const product = findProduct(getProductId());

        if (!product) {
            document.body.innerHTML = `
                <main class="loading">
                    المنتج غير موجود.
                </main>
            `;
            return;
        }

        renderProduct(product);
        updateCartCount();

    } catch (error) {
        const target =
            $('#productPage') ||
            $('#productContent') ||
            document.body;

        target.innerHTML = `
            <div class="loading">
                وقع مشكل في تحميل المنتج. عاودي المحاولة.
            </div>
        `;
    }
}

$('#cartButton')?.addEventListener('click', openCart);

$('#closeCart')?.addEventListener('click', closeCart);

$('#cartBackdrop')?.addEventListener('click', closeCart);

document.addEventListener('keydown', event => {
    if (event.key === 'Escape') {
        closeCart();
    }
});

loadProducts();

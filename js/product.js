const WHATSAPP_NUMBER = '212630000552'; // بدّل هذا الرقم برقم واتساب ديالك
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

function formatPrice(value) {
    return `<span class="price-display" dir="ltr">درهم&nbsp;${parsePrice(value)}</span>`;
}

function getImages(product) {
    return (Array.isArray(product.images) ? product.images : [])
        .filter(src => src && !/logo\.png|urlanding-icon/i.test(src));
}

function getVideos(product) {
    return Array.isArray(product.videos)
        ? product.videos.filter(Boolean)
        : [];
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

function addToCart(size) {
    const sizes = Array.isArray(currentProduct.sizes)
        ? currentProduct.sizes.filter(Boolean)
        : [];

    if (sizes.length && !size) {
        $('#selectionError')?.classList.add('show');

        document.querySelector('.sizes')?.scrollIntoView({
            behavior: 'smooth',
            block: 'center'
        });

        return false;
    }

    const cart = getCart();

    const existing = cart.find(
        item =>
            item.id === currentProduct.id &&
            String(item.size || '') === String(size || '')
    );

    if (existing) {
        existing.quantity = Number(existing.quantity || 1) + 1;
    } else {
        cart.push({
            id: currentProduct.id,
            size: size || '',
            quantity: 1
        });
    }

    saveCart(cart);

    return true;
}


/* =========================================================
   MAIN GALLERY
   ========================================================= */

function renderMainMedia(index) {
    activeMediaIndex = index;

    const item = mediaItems[index];
    const wrap = $('#mainMedia');

    if (!item || !wrap) return;

    const content = item.type === 'video'
        ? `<video src="${escapeHtml(item.src)}" controls playsinline preload="metadata"></video>`
        : `<img src="${escapeHtml(item.src)}" alt="${escapeHtml(currentProduct.title)}">`;

    wrap.querySelector('.main-media-content').innerHTML = content;

    wrap.querySelectorAll('.gallery-thumb').forEach((thumb, i) => {
        thumb.classList.toggle('active', i === index);
    });
}


/* =========================================================
   LIGHTBOX
   ========================================================= */

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

    activeMediaIndex =
        (activeMediaIndex + step + mediaItems.length) %
        mediaItems.length;

    renderLightbox();
    renderMainMedia(activeMediaIndex);
}


/* =========================================================
   GALLERY ARROWS STYLE
   ========================================================= */

function ensureGalleryNavigationStyles() {
    if (document.getElementById('galleryNavigationStyles')) return;

    const style = document.createElement('style');

    style.id = 'galleryNavigationStyles';

    style.textContent = `
        #mainMedia {
            position: relative;
            overflow: hidden;
            touch-action: pan-y;
        }

        #mainMedia .gallery-nav {
            position: absolute;
            top: 50%;
            transform: translateY(-50%);
            z-index: 4;

            width: 42px;
            height: 42px;

            border: 0;
            border-radius: 50%;

            background: rgba(255,255,255,.88);
            color: #333;

            font-size: 30px;
            line-height: 1;

            display: flex;
            align-items: center;
            justify-content: center;

            cursor: pointer;

            box-shadow: 0 3px 14px rgba(0,0,0,.12);

            transition: transform .2s ease;

            padding: 0;
        }

        #mainMedia .gallery-nav:hover {
            transform: translateY(-50%) scale(1.06);
        }

        #mainMedia .gallery-prev {
            left: 12px;
        }

        #mainMedia .gallery-next {
            right: 12px;
        }

        @media (max-width: 600px) {

            #mainMedia .gallery-nav {
                width: 36px;
                height: 36px;
                font-size: 26px;
            }

            #mainMedia .gallery-prev {
                left: 8px;
            }

            #mainMedia .gallery-next {
                right: 8px;
            }
        }
    `;

    document.head.appendChild(style);
}


/* =========================================================
   GALLERY
   ========================================================= */

function renderGallery(product) {
    ensureGalleryNavigationStyles();

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

    const gallery = $('#gallery');

    if (!mediaItems.length) {
        gallery.innerHTML = `
            <div class="main-media">
                <div class="loading">
                    لا توجد صور أو فيديوهات لهذا المنتج
                </div>
            </div>
        `;

        return;
    }

    gallery.innerHTML = `
        <div class="main-media" id="mainMedia">

            <div
                class="main-media-content"
                style="width:100%;height:100%;display:flex;align-items:center;justify-content:center;"
            ></div>

            <button
                class="gallery-nav gallery-prev"
                id="galleryPrev"
                type="button"
                aria-label="الصورة السابقة"
            >
                ‹
            </button>

            <button
                class="gallery-nav gallery-next"
                id="galleryNext"
                type="button"
                aria-label="الصورة التالية"
            >
                ›
            </button>

            <button
                class="zoom-hint"
                id="zoomButton"
                type="button"
            >
                تكبير الصورة ⤢
            </button>

        </div>

        <div class="gallery-thumbs">

            ${mediaItems.map((item, index) =>

                item.type === 'image'

                    ? `
                        <button
                            class="gallery-thumb ${index === 0 ? 'active' : ''}"
                            type="button"
                            data-index="${index}"
                            aria-label="الصورة ${index + 1}"
                        >
                            <img
                                src="${escapeHtml(item.src)}"
                                alt=""
                            >
                        </button>
                    `

                    : `
                        <button
                            class="gallery-thumb gallery-video-button ${index === 0 ? 'active' : ''}"
                            type="button"
                            data-index="${index}"
                            aria-label="الفيديو ${index + 1}"
                        >

                            <span class="gallery-video-thumb">

                                <video
                                    src="${escapeHtml(item.src)}"
                                    muted
                                    playsinline
                                    preload="metadata"
                                ></video>

                                <i aria-hidden="true"></i>

                            </span>

                        </button>
                    `

            ).join('')}

        </div>
    `;


    /* thumbnails */

    gallery.querySelectorAll('.gallery-thumb').forEach(button => {

        button.addEventListener('click', () => {

            renderMainMedia(
                Number(button.dataset.index)
            );

        });

    });


    /* video thumbnails */

    gallery
        .querySelectorAll('.gallery-video-thumb video')
        .forEach(video => {

            const showFrame = () => {

                try {
                    video.currentTime =
                        Math.min(
                            0.1,
                            video.duration || 0.1
                        );
                } catch {}

            };

            video.addEventListener(
                'loadedmetadata',
                showFrame,
                { once: true }
            );

            video.addEventListener(
                'loadeddata',
                showFrame,
                { once: true }
            );

        });


    /* arrows */

    $('#galleryPrev').addEventListener(
        'click',
        () => moveGallery(-1)
    );

    $('#galleryNext').addEventListener(
        'click',
        () => moveGallery(1)
    );


    /* zoom */

    $('#zoomButton').addEventListener(
        'click',
        () => openLightbox(activeMediaIndex)
    );


    /* =====================================================
       MOBILE SWIPE
       ===================================================== */

    let touchStartX = 0;
    let touchStartY = 0;
    let touchMoved = false;

    const mainMedia = $('#mainMedia');


    mainMedia.addEventListener(
        'touchstart',
        event => {

            if (event.touches.length !== 1) return;

            touchStartX =
                event.touches[0].clientX;

            touchStartY =
                event.touches[0].clientY;

            touchMoved = false;

        },
        { passive: true }
    );


    mainMedia.addEventListener(
        'touchmove',
        event => {

            if (event.touches.length !== 1) return;

            const dx =
                event.touches[0].clientX -
                touchStartX;

            const dy =
                event.touches[0].clientY -
                touchStartY;

            if (
                Math.abs(dx) > 10 &&
                Math.abs(dx) > Math.abs(dy)
            ) {
                touchMoved = true;
            }

        },
        { passive: true }
    );


    mainMedia.addEventListener(
        'touchend',
        event => {

            if (!touchMoved) return;

            const dx =
                event.changedTouches[0].clientX -
                touchStartX;

            if (Math.abs(dx) >= 45) {

                // السحب لليسار = التالية
                // السحب لليمين = السابقة

                moveGallery(
                    dx < 0 ? 1 : -1
                );

            }

            touchMoved = false;

        },
        { passive: true }
    );


    renderMainMedia(0);
}


/* =========================================================
   GALLERY NEXT / PREVIOUS
   ========================================================= */

function moveGallery(step) {

    if (!mediaItems.length) return;

    activeMediaIndex =
        (activeMediaIndex + step + mediaItems.length) %
        mediaItems.length;

    renderMainMedia(activeMediaIndex);
}


/* =========================================================
   UPSELL
   ========================================================= */

function renderUpsell() {

    const section = $('#upsell');

    const others = products.filter(
        p => p.id !== currentProduct.id
    );


    if (!others.length) {

        section.classList.add('hidden');

        return;
    }


    /*
     * كلمات لا تفيد كثيراً في حساب التشابه
     */

    const stopWords = new Set([

        'من',
        'في',
        'و',
        'أو',
        'على',
        'مع',
        'هذا',
        'هذه',
        'ذلك',
        'تلك',
        'التي',
        'الذي',
        'الى',
        'إلى',
        'عن',
        'هو',
        'هي',
        'ما',
        'لا',
        'كل',

        'de',
        'du',
        'des',
        'la',
        'le',
        'les',
        'et',
        'ou',
        'avec',
        'pour',
        'une',
        'un',

        'the',
        'and',
        'or',
        'with',
        'for',
        'a',
        'an'

    ]);


    /*
     * تحويل العنوان والوصف إلى كلمات
     */

    const tokenize = value =>

        String(value || '')
            .toLowerCase()
            .normalize('NFKC')

            .replace(
                /[\u064B-\u065F\u0670]/g,
                ''
            )

            .replace(
                /[^\p{L}\p{N}]+/gu,
                ' '
            )

            .split(/\s+/)

            .filter(
                word =>
                    word.length > 1 &&
                    !stopWords.has(word)
            );


    /*
     * كلمات المنتج الحالي
     */

    const currentTokens = new Set([

        ...tokenize(currentProduct.title),

        ...tokenize(currentProduct.description)

    ]);


    /*
     * حساب التشابه لكل منتج
     */

    const ranked = others.map(product => {

        const candidateTokens = new Set([

            ...tokenize(product.title),

            ...tokenize(product.description)

        ]);


        let shared = 0;


        candidateTokens.forEach(token => {

            if (currentTokens.has(token)) {
                shared++;
            }

        });


        const union = new Set([

            ...currentTokens,

            ...candidateTokens

        ]).size;


        const similarity =
            union
                ? shared / union
                : 0;


        return {

            product,

            /*
             * التشابه مهم،
             * لكن العشوائية تجعل النتائج تتغير
             * في كل زيارة.
             */

            score :
                similarity * 100 +
                Math.random() * 35

        };

    });


    /*
     * ترتيب حسب النتيجة
     */

    ranked.sort(
        (a, b) => b.score - a.score
    );


    /*
     * 20 منتج كحد أقصى
     */

    const selected =
        ranked
            .slice(0, 20)
            .map(item => item.product);


    /*
     * عرض المنتجات
     */

    $('#upsellGrid').innerHTML =

        selected.map(product => {

            const image =
                getImages(product)[0];


            return `

                <article class="product-card">

                    <a
                        href="product.html?id=${encodeURIComponent(product.id)}"
                        class="product-card-image"
                    >

                        ${
                            image

                                ? `
                                    <img
                                        src="${escapeHtml(image)}"
                                        alt="${escapeHtml(product.title)}"
                                        loading="lazy"
                                    >
                                  `

                                : `
                                    <div class="loading">
                                        لا توجد صورة
                                    </div>
                                  `
                        }

                    </a>


                    <div class="product-card-body">

                        <h3 class="product-card-title">

                            ${escapeHtml(
                                product.title || 'القطعة'
                            )}

                        </h3>


                        <div class="product-card-price">

                            ${formatPrice(product.price)}

                        </div>


                        <a
                            href="product.html?id=${encodeURIComponent(product.id)}"
                            class="product-card-link"
                        >
                            عرض التفاصيل
                        </a>

                    </div>

                </article>

            `;

        }).join('');
}


/* =========================================================
   PRODUCT
   ========================================================= */

function renderProduct(product) {

    currentProduct = product;

    document.title =
        product.title || 'المنتج';


    const sizes =
        Array.isArray(product.sizes)
            ? product.sizes.filter(Boolean)
            : [];


    const description =
        product.description

            ? escapeHtml(product.description)

            : 'لا توجد تفاصيل إضافية لهذا المنتج حالياً.';


    $('#productPage').innerHTML = `

        <div class="product-detail-grid">


            <div
                class="gallery"
                id="gallery"
            ></div>


            <div class="product-info">


                <h1 class="product-title">

                    ${escapeHtml(
                        product.title || 'القطعة'
                    )}

                </h1>


                <div class="product-price">

                    ${formatPrice(product.price)}

                </div>


                <div class="product-description">

                    ${description}

                </div>


                ${
                    sizes.length

                        ? `

                            <div class="option-block">


                                <div class="option-label">

                                    <span>
                                        اختاري المقاس
                                    </span>

                                    <span class="option-required">
                                        ضروري
                                    </span>

                                </div>


                                <div
                                    class="sizes"
                                    id="sizes"
                                >

                                    ${sizes.map(size => `

                                        <button
                                            class="size-button"
                                            type="button"
                                            data-size="${escapeHtml(size)}"
                                        >
                                            ${escapeHtml(size)}
                                        </button>

                                    `).join('')}

                                </div>


                                <div
                                    id="selectionError"
                                    class="selection-error"
                                >
                                    اختاري المقاس أولاً باش نضيفو القطعة للسلة.
                                </div>


                            </div>

                          `

                        : ''
                }


                <div class="product-actions">


                    <button
                        id="addCart"
                        class="add-cart-button"
                        type="button"
                    >
                        أضيفي للسلة
                    </button>


                    <button
                        id="directWhatsApp"
                        class="product-whatsapp"
                        type="button"
                    >
                        الطلب مباشرة عبر واتساب
                    </button>


                </div>


            </div>


        </div>


        <section
            id="upsell"
            class="upsell-section"
        >


            <div class="upsell-heading">

                <h2>
                    قد تعجبك أيضاً
                </h2>

            </div>


            <div
                id="upsellGrid"
                class="upsell-grid"
            ></div>


        </section>

    `;


    renderGallery(product);


    let selectedSize = '';


    document
        .querySelectorAll('.size-button')
        .forEach(button => {

            button.addEventListener(
                'click',
                () => {

                    selectedSize =
                        button.dataset.size;


                    document
                        .querySelectorAll('.size-button')
                        .forEach(b =>
                            b.classList.remove(
                                'selected'
                            )
                        );


                    button.classList.add(
                        'selected'
                    );


                    $('#selectionError')
                        ?.classList.remove(
                            'show'
                        );

                }
            );

        });


    /* add to cart */

    $('#addCart').addEventListener(
        'click',
        () => {

            if (addToCart(selectedSize)) {

                $('#addCart').textContent =
                    'تمت الإضافة ';

                setTimeout(
                    () => {

                        $('#addCart').textContent =
                            'أضيفي للسلة';

                    },
                    1400
                );

            }

        }
    );


    /* WhatsApp */

    $('#directWhatsApp').addEventListener(
        'click',
        () => {

            const sizesList = sizes;


            if (
                sizesList.length &&
                !selectedSize
            ) {

                $('#selectionError')
                    .classList.add('show');


                document
                    .querySelector('.sizes')
                    .scrollIntoView({
                        behavior: 'smooth',
                        block: 'center'
                    });


                return;
            }


            const lines = [

                'السلام عليكم، بغيت نطلب هاد القطعة من المتجر:',

                `المنتج: ${product.title}`,

                `الثمن: ${formatPrice(product.price)}`,

                selectedSize
                    ? `المقاس: ${selectedSize}`
                    : '',

                '',

                'الاسم:',

                'المدينة:',

                'العنوان:',

                'الهاتف:'

            ].filter(Boolean);


            window.open(

                `https://wa.me/${WHATSAPP_NUMBER}?text=${encodeURIComponent(
                    lines.join('\n')
                )}`,

                '_blank'

            );

        }
    );


    renderUpsell();
}


/* =========================================================
   INIT
   ========================================================= */

async function init() {

    updateCartCount();


    const id =
        new URLSearchParams(
            location.search
        ).get('id');


    if (!id) {

        $('#productPage').innerHTML = `

            <div class="empty-message">

                <h3>
                    المنتج غير موجود
                </h3>

                <p>
                    <a href="index.html">
                        العودة للمنتجات
                    </a>
                </p>

            </div>

        `;

        return;
    }


    try {

        const response =
            await fetch(
                'products.json',
                {
                    cache: 'no-store'
                }
            );


        if (!response.ok) {
            throw new Error('Failed');
        }


        products =
            await response.json();


        const product =
            products.find(
                p =>
                    String(p.id) ===
                    String(id)
            );


        if (!product) {
            throw new Error('Not found');
        }


        renderProduct(product);


    } catch {

        $('#productPage').innerHTML = `

            <div class="empty-message">

                <h3>
                    ما قدرناش نحمّلو هاد المنتج
                </h3>

                <p>
                    <a href="index.html">
                        العودة للمنتجات
                    </a>
                </p>

            </div>

        `;

    }

}


/* =========================================================
   LIGHTBOX EVENTS
   ========================================================= */

$('#lightboxClose')
    .addEventListener(
        'click',
        closeLightbox
    );


$('#lightboxPrev')
    .addEventListener(
        'click',
        () => moveLightbox(-1)
    );


$('#lightboxNext')
    .addEventListener(
        'click',
        () => moveLightbox(1)
    );


$('#lightbox')
    .addEventListener(
        'click',
        event => {

            if (
                event.target.id ===
                'lightbox'
            ) {
                closeLightbox();
            }

        }
    );


/* keyboard */

document.addEventListener(
    'keydown',
    event => {

        if (event.key === 'Escape') {
            closeLightbox();
        }


        if (
            !$('#lightbox')
                .classList
                .contains('hidden')
        ) {

            if (
                event.key ===
                'ArrowLeft'
            ) {
                moveLightbox(1);
            }


            if (
                event.key ===
                'ArrowRight'
            ) {
                moveLightbox(-1);
            }

        }

    }
);


/* cart */

$('#cartButton')?.addEventListener(
    'click',
    () => {

        // في صفحة المنتج نكتفي بالرجوع للسلة المخزنة؛
        // السلة الكاملة موجودة في الصفحة الرئيسية.

        location.href =
            'index.html?cart=1#products';

    }
);


/* start */

init();

let products = [];
let currentProduct = null;

const productPage = document.getElementById("productPage");


/* =========================
   LOAD PRODUCTS
========================= */

async function loadProduct() {

    try {

        const response = await fetch("products.json", {
            cache: "no-store"
        });

        if (!response.ok) {
            throw new Error("products.json not found");
        }

        products = await response.json();

        const params = new URLSearchParams(
            window.location.search
        );

        const productId = params.get("id");

        currentProduct = products.find(
            product => String(product.id) === String(productId)
        );


        if (!currentProduct) {

            showNotFound();

            return;
        }


        renderProduct(currentProduct);

    } catch (error) {

        console.error(error);

        productPage.innerHTML = `
            <div class="loading">
                وقع مشكل في تحميل المنتج.
            </div>
        `;

    }

}


/* =========================
   PRODUCT
========================= */

function renderProduct(product) {

    const images = getImages(product);

    const videos = Array.isArray(product.videos)
        ? product.videos.filter(Boolean)
        : [];


    const firstImage =
        images.length
            ? images[0]
            : "";


    productPage.innerHTML = `

        <div class="product-detail">


            <!-- MEDIA -->

            <div class="product-media-section">

                <div
                    class="main-media"
                    id="mainMedia"
                >

                    ${
                        firstImage
                        ?
                        `
                        <img
                            src="${escapeHtml(firstImage)}"
                            alt="${escapeHtml(product.title || "منتج")}"
                        >
                        `
                        :
                        `
                        <div class="loading">
                            لا توجد صورة
                        </div>
                        `
                    }

                </div>


                <div class="gallery" id="gallery">

                    ${renderImageButtons(images)}

                    ${renderVideoButtons(videos)}

                </div>

            </div>


            <!-- INFO -->

            <div class="product-info">

                <h1>
                    ${escapeHtml(product.title || "منتج")}
                </h1>


                <div class="price-row">

                    <strong class="detail-price">
                        ${escapeHtml(product.price || "")}
                    </strong>

                    ${
                        product.original_price
                        ?
                        `
                        <span class="detail-old-price">
                            ${escapeHtml(product.original_price)}
                        </span>
                        `
                        :
                        ""
                    }

                </div>


                ${
                    product.description
                    ?
                    `
                    <div class="product-description">
                        ${escapeHtml(product.description)}
                    </div>
                    `
                    :
                    ""
                }


                ${
                    Array.isArray(product.sizes)
                    && product.sizes.length
                    ?
                    `
                    <div class="sizes">

                        <h3>
                            المقاسات المتوفرة
                        </h3>

                        <div class="size-list">

                            ${
                                product.sizes
                                    .map(size =>
                                        `
                                        <span class="size">
                                            ${escapeHtml(size)}
                                        </span>
                                        `
                                    )
                                    .join("")
                            }

                        </div>

                    </div>
                    `
                    :
                    ""
                }


                ${
                    product.status
                    ?
                    `
                    <p>
                        ${escapeHtml(product.status)}
                    </p>
                    `
                    :
                    ""
                }


                <button
                    class="add-cart-button"
                    id="addToCartButton"
                >
                    🛒 أضف إلى السلة
                </button>


                <button
                    class="whatsapp-button"
                    id="directWhatsapp"
                >
                    طلب هذا المنتج عبر واتساب
                </button>

            </div>

        </div>

    `;


    setupGallery(images, videos);


    document
        .getElementById("addToCartButton")
        .addEventListener(
            "click",
            () => addToCart(product)
        );


    document
        .getElementById("directWhatsapp")
        .addEventListener(
            "click",
            () => orderDirectly(product)
        );

}


/* =========================
   IMAGES
========================= */

function getImages(product) {

    const images =
        Array.isArray(product.images)
            ? product.images
            : [];


    return images.filter(url => {

        if (!url) return false;

        const lower =
            String(url).toLowerCase();

        /*
         * كنحيدو الصور العامة ديال Boughal
         * ونخليو غير صور المنتج.
         */

        return !lower.includes("logo.png")
            && !lower.includes("urlanding-icon");

    });

}


/* =========================
   IMAGE BUTTONS
========================= */

function renderImageButtons(images) {

    return images
        .map((image, index) => {

            return `

                <button
                    type="button"
                    class="media-thumb"
                    data-type="image"
                    data-index="${index}"
                >

                    <img
                        src="${escapeHtml(image)}"
                        alt=""
                        loading="lazy"
                    >

                </button>

            `;

        })
        .join("");

}


/* =========================
   VIDEO BUTTONS
========================= */

function renderVideoButtons(videos) {

    return videos
        .map((video, index) => {

            return `

                <button
                    type="button"
                    class="media-thumb"
                    data-type="video"
                    data-index="${index}"
                >

                    <div
                        style="
                            width:100%;
                            height:100%;
                            display:flex;
                            align-items:center;
                            justify-content:center;
                            font-size:24px;
                        "
                    >
                        ▶️
                    </div>

                </button>

            `;

        })
        .join("");

}


/* =========================
   GALLERY
========================= */

function setupGallery(images, videos) {

    const buttons =
        document.querySelectorAll(
            ".media-thumb"
        );


    buttons.forEach(button => {

        button.addEventListener(
            "click",
            () => {

                const type =
                    button.dataset.type;

                const index =
                    Number(button.dataset.index);


                if (type === "image") {

                    showImage(
                        images[index]
                    );

                }


                if (type === "video") {

                    showVideo(
                        videos[index]
                    );

                }

            }
        );

    });

}


/* =========================
   SHOW IMAGE
========================= */

function showImage(url) {

    const mainMedia =
        document.getElementById("mainMedia");


    mainMedia.innerHTML = `

        <img
            src="${escapeHtml(url)}"
            alt="${escapeHtml(currentProduct.title || "منتج")}"
        >

    `;

}


/* =========================
   SHOW VIDEO
========================= */

function showVideo(url) {

    const mainMedia =
        document.getElementById("mainMedia");


    mainMedia.innerHTML = `

        <video
            src="${escapeHtml(url)}"
            controls
            autoplay
            playsinline
        >
            المتصفح ديالك ما كيدعمش تشغيل الفيديو.
        </video>

    `;

}


/* =========================
   ADD TO CART
========================= */

function addToCart(product) {

    let cart =
        JSON.parse(
            localStorage.getItem("shadhw_cart") || "[]"
        );


    const existing =
        cart.find(
            item => item.id === product.id
        );


    if (existing) {

        existing.quantity += 1;

    } else {

        cart.push({

            id: product.id,

            title: product.title,

            price: product.price,

            image: getProductImage(product),

            quantity: 1

        });

    }


    localStorage.setItem(
        "shadhw_cart",
        JSON.stringify(cart)
    );


    alert("تمت إضافة المنتج إلى السلة 🛒");

}


/* =========================
   DIRECT WHATSAPP
========================= */

function orderDirectly(product) {

    /*
     * بدّل الرقم من بعد برقم واتساب
     * ديال SHADHW JEWELS.
     */

    const phone =
        "212600000000";


    const message =
        "السلام عليكم، بغيت نطلب هاد المنتج:%0A%0A"
        +
        `المنتج: ${encodeURIComponent(product.title || "")}%0A`
        +
        `الثمن: ${encodeURIComponent(product.price || "")}`;


    const url =
        `https://wa.me/${phone}?text=${message}`;


    window.open(
        url,
        "_blank"
    );

}


/* =========================
   PRODUCT IMAGE
========================= */

function getProductImage(product) {

    const images =
        Array.isArray(product.images)
            ? product.images
            : [];


    const valid =
        images.filter(url => {

            if (!url) return false;

            const lower =
                String(url).toLowerCase();

            return !lower.includes("logo.png")
                && !lower.includes("urlanding-icon");

        });


    if (valid.length) {
        return valid[0];
    }


    if (
        product.image
        &&
        !product.image.includes("logo.png")
    ) {

        return product.image;

    }


    return "";

}


/* =========================
   NOT FOUND
========================= */

function showNotFound() {

    productPage.innerHTML = `

        <div class="empty-message">

            <h2>
                المنتج غير موجود
            </h2>

            <p>
                يمكن أن يكون المنتج تحيد أو الرابط غير صحيح.
            </p>

            <br>

            <a
                href="index.html"
                class="product-link"
            >
                العودة للمنتجات
            </a>

        </div>

    `;

}


/* =========================
   ESCAPE HTML
========================= */

function escapeHtml(value) {

    return String(value ?? "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");

}


/* =========================
   START
========================= */

loadProduct();

let products = [];
let cart = JSON.parse(localStorage.getItem("shadhw_cart") || "[]");

const productsGrid = document.getElementById("productsGrid");
const searchInput = document.getElementById("searchInput");
const productsCount = document.getElementById("productsCount");
const emptyMessage = document.getElementById("emptyMessage");

const cartButton = document.getElementById("cartButton");
const cartOverlay = document.getElementById("cartOverlay");
const closeCart = document.getElementById("closeCart");

const cartItems = document.getElementById("cartItems");
const cartTotal = document.getElementById("cartTotal");
const cartCount = document.getElementById("cartCount");

const whatsappOrder = document.getElementById("whatsappOrder");


/* =========================
   LOAD PRODUCTS
========================= */

async function loadProducts() {

    try {

        const response = await fetch("products.json", {
            cache: "no-store"
        });

        if (!response.ok) {
            throw new Error("products.json not found");
        }

        products = await response.json();

        renderProducts(products);

        updateCart();

    } catch (error) {

        console.error(error);

        productsGrid.innerHTML = `
            <div class="loading">
                وقع مشكل في تحميل المنتجات.
                <br>
                تأكد أن ملف products.json موجود.
            </div>
        `;

    }

}


/* =========================
   IMAGE
========================= */

function getProductImage(product) {

    const images = Array.isArray(product.images)
        ? product.images
        : [];

    const validImages = images.filter(url => {
        if (!url) return false;

        const lower = url.toLowerCase();

        return !lower.includes("logo.png")
            && !lower.includes("urlanding-icon");
    });

    if (validImages.length) {
        return validImages[0];
    }

    if (product.image && !product.image.includes("logo.png")) {
        return product.image;
    }

    return "";
}


/* =========================
   PRODUCTS
========================= */

function renderProducts(list) {

    productsGrid.innerHTML = "";

    productsCount.textContent =
        `${list.length} منتج`;

    if (!list.length) {

        emptyMessage.classList.remove("hidden");

        return;
    }

    emptyMessage.classList.add("hidden");


    list.forEach(product => {

        const card = document.createElement("article");

        card.className = "product-card";


        const image = getProductImage(product);


        card.innerHTML = `

            <a href="product.html?id=${encodeURIComponent(product.id)}">

                <div class="product-image">

                    ${
                        image
                        ?
                        `<img
                            src="${escapeHtml(image)}"
                            alt="${escapeHtml(product.title || "منتج")}"
                            loading="lazy"
                        >`
                        :
                        `<div class="loading">
                            لا توجد صورة
                        </div>`
                    }

                </div>

            </a>


            <div class="product-content">

                <h3 class="product-title">
                    ${escapeHtml(product.title || "منتج")}
                </h3>


                <div class="price-row">

                    <strong class="price">
                        ${escapeHtml(product.price || "")}
                    </strong>

                    ${
                        product.original_price
                        ?
                        `<span class="old-price">
                            ${escapeHtml(product.original_price)}
                        </span>`
                        :
                        ""
                    }

                </div>


                <a
                    class="product-link"
                    href="product.html?id=${encodeURIComponent(product.id)}"
                >
                    عرض المنتج
                </a>

            </div>

        `;


        productsGrid.appendChild(card);

    });

}


/* =========================
   SEARCH
========================= */

searchInput.addEventListener("input", function () {

    const query = this.value
        .trim()
        .toLowerCase();


    if (!query) {

        renderProducts(products);

        return;
    }


    const filtered = products.filter(product => {

        const title =
            String(product.title || "").toLowerCase();

        const description =
            String(product.description || "").toLowerCase();

        return title.includes(query)
            || description.includes(query);

    });


    renderProducts(filtered);

});


/* =========================
   CART
========================= */

function addToCart(productId) {

    const product = products.find(
        p => p.id === productId
    );

    if (!product) return;


    const existing = cart.find(
        item => item.id === productId
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


    saveCart();

    updateCart();

    openCart();

}


function removeFromCart(productId) {

    cart = cart.filter(
        item => item.id !== productId
    );

    saveCart();

    updateCart();

}


function saveCart() {

    localStorage.setItem(
        "shadhw_cart",
        JSON.stringify(cart)
    );

}


function parsePrice(value) {

    if (typeof value === "number") {
        return value;
    }

    const number =
        String(value || "")
            .replace(",", ".")
            .match(/[\d.]+/);

    return number
        ? parseFloat(number[0])
        : 0;

}


function updateCart() {

    cartItems.innerHTML = "";

    let total = 0;

    let count = 0;


    if (!cart.length) {

        cartItems.innerHTML = `
            <div class="loading">
                السلة خاوية.
            </div>
        `;

    }


    cart.forEach(item => {

        const quantity =
            Number(item.quantity) || 1;

        const price =
            parsePrice(item.price);

        total += price * quantity;

        count += quantity;


        const div =
            document.createElement("div");

        div.className = "cart-item";


        div.innerHTML = `

            ${
                item.image
                ?
                `<img
                    class="cart-item-image"
                    src="${escapeHtml(item.image)}"
                    alt=""
                >`
                :
                ""
            }


            <div class="cart-item-info">

                <div class="cart-item-title">
                    ${escapeHtml(item.title || "منتج")}
                </div>

                <div class="cart-item-price">
                    ${escapeHtml(item.price || "")}
                    × ${quantity}
                </div>

            </div>


            <button
                class="remove-cart-item"
                data-id="${escapeHtml(item.id)}"
            >
                حذف
            </button>

        `;


        cartItems.appendChild(div);

    });


    cartTotal.textContent =
        `${total.toFixed(0)} DH`;

    cartCount.textContent =
        count;


    document
        .querySelectorAll(".remove-cart-item")
        .forEach(button => {

            button.addEventListener(
                "click",
                () => {

                    removeFromCart(
                        button.dataset.id
                    );

                }
            );

        });

}


/* =========================
   CART OPEN / CLOSE
========================= */

function openCart() {

    cartOverlay.classList.remove("hidden");

}

function closeCartPanel() {

    cartOverlay.classList.add("hidden");

}


cartButton.addEventListener(
    "click",
    openCart
);

closeCart.addEventListener(
    "click",
    closeCartPanel
);


cartOverlay.addEventListener(
    "click",
    event => {

        if (event.target === cartOverlay) {
            closeCartPanel();
        }

    }
);


/* =========================
   WHATSAPP
========================= */

whatsappOrder.addEventListener(
    "click",
    function () {

        if (!cart.length) {

            alert("السلة خاوية.");

            return;
        }


        let message =
            "السلام عليكم، بغيت نطلب:%0A%0A";


        cart.forEach(item => {

            message +=
                `• ${encodeURIComponent(item.title)}`
                +
                ` × ${item.quantity}`
                +
                `%0A`;

        });


        message +=
            `%0Aالمجموع: ${encodeURIComponent(cartTotal.textContent)}`;


        /*
          بدّل الرقم من بعد برقم واتساب ديال المتجر.
          مثال:
          2126XXXXXXXX
        */

        const phone =
            "212600000000";


        const url =
            `https://wa.me/${phone}?text=${message}`;


        window.open(url, "_blank");

    }
);


/* =========================
   SECURITY / TEXT
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

loadProducts();

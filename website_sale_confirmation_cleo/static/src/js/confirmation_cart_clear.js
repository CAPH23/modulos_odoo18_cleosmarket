/** @odoo-module **/

(function () {
    "use strict";

    let alreadyCleared = false;

    function isConfirmationPage() {
        return window.location.pathname.includes("/shop/confirmation");
    }

    function clearBrowserCartCache() {
        try {
            window.sessionStorage.setItem("website_sale_cart_quantity", "0");
            window.localStorage.removeItem("website_sale_cart_quantity");
        } catch (error) {
            // No bloquear si el navegador no permite tocar storage.
        }
    }

    function clearCartBadges() {
        const selectors = [
            ".my_cart_quantity",
            ".o_mycart_quantity",
            ".o_wsale_my_cart .badge",
            ".o_wsale_my_cart sup",
            "a[href='/shop/cart'] .badge",
            "a[href*='/shop/cart'] .badge",
            "a[href='/shop/cart'] sup",
            "a[href*='/shop/cart'] sup",
        ];

        document.querySelectorAll(selectors.join(",")).forEach(function (badge) {
            badge.textContent = "";
            badge.classList.add("d-none");
            badge.setAttribute("aria-hidden", "true");
            badge.dataset.orderId = "";
        });

        document.querySelectorAll(".o_wsale_my_cart, a[href='/shop/cart'], a[href*='/shop/cart']").forEach(function (cartLink) {
            cartLink.dataset.cartQuantity = "0";
            cartLink.setAttribute("data-cart-quantity", "0");
        });
    }

    async function clearServerCartSession() {
        const response = await fetch("/cleo/cart/clear_confirmed", {
            method: "POST",
            credentials: "same-origin",
            headers: {
                "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
            },
            body: "",
        });

        const result = await response.json();

        if (!response.ok || !result.success) {
            throw new Error(result.error || result.message || "No se pudo limpiar la sesión del carrito.");
        }

        return result;
    }

    async function initConfirmationCartClear() {
        if (!isConfirmationPage() || alreadyCleared) {
            return;
        }

        alreadyCleared = true;

        try {
            await clearServerCartSession();
            clearBrowserCartCache();
            clearCartBadges();

            setTimeout(clearCartBadges, 250);
            setTimeout(clearCartBadges, 800);
            setTimeout(clearCartBadges, 1500);
        } catch (error) {
            console.warn("No se pudo limpiar realmente el carrito confirmado:", error);

            // Aunque falle el endpoint, no bloquear la página.
            clearBrowserCartCache();
            clearCartBadges();
        }
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", initConfirmationCartClear);
    } else {
        initConfirmationCartClear();
    }
})();

/** @odoo-module **/

/*
 * Mantiene reactivo el aviso de monto mínimo para entrega a domicilio en
 * /shop/cart. El mensaje se renderiza inicialmente en el servidor
 * (checkout_templates.xml), pero al cambiar cantidades o eliminar productos
 * el tema base de Odoo (website_sale.js) solo reemplaza `.js_cart_lines` y
 * `#cart_total` vía AJAX, sin recargar la página; este script vuelve a
 * evaluar el total y actualiza el aviso cuando eso ocurre.
 */
(function () {
    "use strict";

    var NOTE_SELECTOR = ".cleo-cart-delivery-minimum-note";
    var BELOW_SELECTOR = ".cleo-cart-delivery-minimum-below";
    var REACHED_SELECTOR = ".cleo-cart-delivery-minimum-reached";
    var MISSING_SELECTOR = ".cleo-cart-delivery-minimum-missing";
    var TOTAL_SELECTOR = "#cart_total #order_total .oe_currency_value";

    function parseMoneyToNumber(raw) {
        if (raw == null) { return null; }
        var s = String(raw).replace(/[^0-9.,]/g, "");
        if (!s) { return null; }
        var hasDot = s.indexOf(".") !== -1;
        var hasComma = s.indexOf(",") !== -1;
        if (hasDot && hasComma) {
            if (s.lastIndexOf(",") > s.lastIndexOf(".")) {
                s = s.replace(/\./g, "").replace(",", ".");
            } else {
                s = s.replace(/,/g, "");
            }
        } else if (hasComma) {
            s = s.replace(/\./g, "").replace(",", ".");
        }
        var n = parseFloat(s);
        return isNaN(n) ? null : n;
    }

    function formatoMoneda(n) {
        try { return "$" + n.toFixed(2); } catch (e) { return "$" + n; }
    }

    function totalDelCarrito() {
        var el = document.querySelector(TOTAL_SELECTOR);
        if (!el) { return null; }
        return parseMoneyToNumber(el.textContent);
    }

    function actualizar() {
        var note = document.querySelector(NOTE_SELECTOR);
        if (!note) { return; }

        var min = parseMoneyToNumber(note.getAttribute("data-cleo-delivery-minimum"));
        var total = totalDelCarrito();
        if (min == null || total == null) { return; }

        var below = note.querySelector(BELOW_SELECTOR);
        var reached = note.querySelector(REACHED_SELECTOR);
        var superoMinimo = total >= min - 0.0001;

        if (below) { below.classList.toggle("d-none", superoMinimo); }
        if (reached) { reached.classList.toggle("d-none", !superoMinimo); }

        if (!superoMinimo) {
            var missing = note.querySelector(MISSING_SELECTOR);
            if (missing) { missing.textContent = (min - total).toFixed(2); }
        }
    }

    // Debounce: el reemplazo AJAX de `.js_cart_lines` y `#cart_total` puede
    // disparar varias mutaciones seguidas.
    var pendiente = null;
    function actualizarDebounced() {
        if (pendiente) { return; }
        pendiente = window.setTimeout(function () {
            pendiente = null;
            actualizar();
        }, 120);
    }

    function init() {
        if (!document.querySelector(NOTE_SELECTOR)) { return; }

        var root = document.querySelector(".oe_website_sale") || document.body;
        try {
            var observer = new MutationObserver(actualizarDebounced);
            observer.observe(root, {
                subtree: true,
                childList: true,
                characterData: true,
            });
        } catch (e) { /* MutationObserver no disponible: sin reactividad AJAX */ }

        // Red de seguridad ante interacciones que no disparen mutaciones
        // detectables a tiempo (p. ej. justo tras el click en +/-/eliminar).
        document.addEventListener("change", actualizarDebounced, true);
        document.addEventListener("click", actualizarDebounced, true);
    }

    if (document.readyState !== "loading") {
        init();
    } else {
        document.addEventListener("DOMContentLoaded", init);
    }
})();

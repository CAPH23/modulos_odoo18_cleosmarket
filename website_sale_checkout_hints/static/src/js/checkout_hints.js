/* Part of the "Ayudas de checkout" module.
 * Copyright 2026 Carlos Palacios. License LGPL-3.
 *
 * Muestra, encima del botón "Proceder a comprar" del checkout de Odoo 18,
 * UN SOLO texto de ayuda a la vez: el de mayor prioridad entre las condiciones
 * que aún impiden habilitar el botón. Al resolverse una condición, aparece la
 * siguiente; al habilitarse el botón, el mensaje desaparece.
 *
 * No requiere plantillas: el contenedor del mensaje se inserta por JS justo
 * antes del botón, y se reevalúa de forma reactiva ante cambios del DOM.
 */
(function () {
    "use strict";

    // =========================================================================
    // CONFIGURACIÓN — Ajusta estos selectores si tu tema/pasarela personalizada
    // (p. ej. el módulo de Pedidos Ya) usa una estructura distinta.
    // =========================================================================
    var CONFIG = {
        // Botón "Proceder a comprar" / continuar del checkout.
        buttonSelectors: [
            'a[name="website_sale_main_button"]',
            'button[name="website_sale_main_button"]',
            'a.btn-primary[href*="/shop/payment"]',
            'button.btn-primary[href*="/shop/payment"]',
            'a.btn-primary[href*="/shop/confirm_order"]',
        ],
        // Checkbox de términos y condiciones (existe solo si está activado).
        tcCheckbox: '#website_sale_tc_checkbox, input[name="website_sale_tc_checkbox"]',
        // Radios de método de entrega.
        deliveryRadios: 'input[name="o_delivery_radio"], input.o_delivery_radio',
        // Contenedores de opciones de entrega (para detectar que existen métodos).
        deliveryContainers: '#o_delivery_methods, .o_delivery_methods, ul.o_delivery_carrier_select',
        // Tarjeta de opción de entrega marcada como activa/seleccionada (fallback).
        deliverySelectedCards: '.o_delivery_carrier_select.border-primary, .o_delivery_carrier_select .active',
        // Selector de una dirección seleccionada (fallback, muy dependiente del tema).
        addressSelected: 'input[name="selected_pdv"]:checked, .o_wsale_addr_selected, .card.border-primary .o_wsale_address_row',
        // Cada cuánto reevaluar como red de seguridad (ms). El grueso del trabajo
        // lo hace el MutationObserver; esto solo cubre casos límite.
        safetyIntervalMs: 1200,
    };

    // =========================================================================
    // CONDICIONES — mayor "prioridad" = más importante = se muestra primero.
    // Cada condición "falla" (bloquea) cuando su función devuelve true.
    // =========================================================================
    var CONDICIONES = [
        {
            // Dirección seleccionada pero incompleta (falta país, departamento,
            // calle o ubicación en el mapa). Se lee del guard real del sitio.
            id: "direccion_incompleta",
            prioridad: 95,
            falla: function () { return direccionIncompleta(); },
            texto: function () {
                return "Completa los datos de tu dirección de entrega (usa \u201CEditar\u201D) para continuar.";
            },
        },
        {
            id: "direccion",
            prioridad: 90,
            falla: function () { return direccionNoSeleccionada(); },
            texto: function () { return "Selecciona o añade una dirección de entrega para continuar."; },
        },
        {
            id: "metodo",
            prioridad: 80,
            falla: function () { return hayMetodosEntrega() && !metodoEntregaSeleccionado(); },
            texto: function () { return "Elige un método de entrega para continuar."; },
        },
        {
            // Monto mínimo para entrega a domicilio: se VALIDA contra el mínimo
            // real del sitio y el total real del pedido. Solo aplica si hay un
            // método a domicilio (no "en tienda") seleccionado y el total es menor.
            id: "minimo",
            prioridad: 70,
            falla: function () {
                if (!metodoEntregaSeleccionado() || entregaEnTiendaSeleccionada()) { return false; }
                var min = minimoDelSitio();
                if (min == null) { return false; }
                var total = totalDelPedido();
                if (total == null) { return false; }
                return total < min - 0.0001;
            },
            texto: function () { return textoMinimo(); },
        },
        {
            id: "terminos",
            prioridad: 60,
            falla: function () { return terminosExisten() && !terminosAceptados(); },
            texto: function () { return "Acepta los términos y condiciones para continuar."; },
        },
        {
            id: "generico",
            prioridad: 10,
            falla: function (ctx) { return ctx.disabled; },
            texto: function () { return "Revisa los datos de entrega para poder continuar con tu compra."; },
        },
    ];

    // =========================================================================
    // DETECCIÓN DE ESTADO
    // =========================================================================
    function q(selector, root) {
        try { return (root || document).querySelector(selector); } catch (e) { return null; }
    }
    function qa(selector, root) {
        try { return Array.prototype.slice.call((root || document).querySelectorAll(selector)); } catch (e) { return []; }
    }

    function findButton() {
        for (var i = 0; i < CONFIG.buttonSelectors.length; i++) {
            var el = q(CONFIG.buttonSelectors[i]);
            if (el) { return el; }
        }
        return null;
    }

    function isDisabled(btn) {
        if (!btn) { return false; }
        if (btn.classList && btn.classList.contains("disabled")) { return true; }
        if (btn.hasAttribute && btn.hasAttribute("disabled")) { return true; }
        if (btn.getAttribute && btn.getAttribute("aria-disabled") === "true") { return true; }
        return false;
    }

    function hayMetodosEntrega() {
        if (qa(CONFIG.deliveryRadios).length) { return true; }
        return qa(CONFIG.deliveryContainers).length > 0;
    }

    function metodoEntregaSeleccionado() {
        var radios = qa(CONFIG.deliveryRadios);
        if (radios.length) {
            for (var i = 0; i < radios.length; i++) {
                if (radios[i].checked) { return true; }
            }
            return false;
        }
        // Sin radios reconocibles: intenta detectar una tarjeta activa.
        if (qa(CONFIG.deliverySelectedCards).length) { return true; }
        // Si no podemos saberlo, no bloqueamos por este motivo.
        return false;
    }

    function direccionNoSeleccionada() {
        // Conservador: solo "falla" si detectamos positivamente que NO hay
        // dirección elegida, para no mostrar el mensaje por error.
        var radiosDireccion = qa('input[name="selected_pdv"], input[name="shipping_id"], input.o_wsale_address_radio');
        if (radiosDireccion.length) {
            for (var i = 0; i < radiosDireccion.length; i++) {
                if (radiosDireccion[i].checked) { return false; }
            }
            return true; // hay opciones de dirección pero ninguna elegida
        }
        // Si no reconocemos la estructura de direcciones, asumimos que está bien.
        return false;
    }

    function terminosExisten() {
        return !!q(CONFIG.tcCheckbox);
    }
    function terminosAceptados() {
        var cb = q(CONFIG.tcCheckbox);
        return cb ? !!cb.checked : true;
    }

    // ---- Monto mínimo (motivo #70) -----------------------------------------
    function parseMoneyToNumber(raw) {
        if (raw == null) { return null; }
        var s = String(raw).replace(/[^0-9.,]/g, "");
        if (!s) { return null; }
        var hasDot = s.indexOf(".") !== -1;
        var hasComma = s.indexOf(",") !== -1;
        if (hasDot && hasComma) {
            // El último separador es el decimal.
            if (s.lastIndexOf(",") > s.lastIndexOf(".")) {
                s = s.replace(/\./g, "").replace(",", ".");
            } else {
                s = s.replace(/,/g, "");
            }
        } else if (hasComma) {
            // Coma como decimal (formato "6,66").
            s = s.replace(/\./g, "").replace(",", ".");
        }
        var n = parseFloat(s);
        return isNaN(n) ? null : n;
    }

    // Mínimo REAL del sitio: se lee del elemento que ya renderiza el checkout
    // ("Las entregas a domicilio se habilitan para compras desde $9.99").
    function minimoDelSitio() {
        var el = q(".cleo-delivery-minimum-amount");
        if (el) { return parseMoneyToNumber(el.textContent); }
        return null;
    }

    // Total REAL del pedido, leído del resumen del checkout.
    function totalDelPedido() {
        var scope = q(".cleo-checkout-summary-card") || q("#o_wsale_total_accordion");
        var valores = qa(".oe_currency_value", scope || undefined)
            .map(function (el) { return parseMoneyToNumber(el.textContent); })
            .filter(function (n) { return n != null; });
        if (!valores.length) {
            valores = qa(".oe_currency_value")
                .map(function (el) { return parseMoneyToNumber(el.textContent); })
                .filter(function (n) { return n != null; });
        }
        if (!valores.length) { return null; }
        // En el resumen, el mayor valor monetario corresponde al Total.
        return Math.max.apply(null, valores);
    }

    function formatoMoneda(n) {
        try { return "$" + n.toFixed(2); } catch (e) { return "$" + n; }
    }

    function textoMinimo() {
        var min = minimoDelSitio();
        var total = totalDelPedido();
        if (min != null && total != null && total < min) {
            var falt = min - total;
            return "La entrega a domicilio requiere una compra mínima de " + formatoMoneda(min) +
                ". Te faltan " + formatoMoneda(falt) + " o elige \u201CEntrega en tienda\u201D.";
        }
        if (min != null) {
            return "La entrega a domicilio requiere una compra mínima de " + formatoMoneda(min) +
                ". Ajusta tu pedido o elige \u201CEntrega en tienda\u201D.";
        }
        return "El método de entrega seleccionado aún no está disponible para tu pedido. " +
            "Elige \u201CEntrega en tienda\u201D u otro método.";
    }

    // ---- Estado real de la dirección y del método (guard del sitio) --------
    function guardDelSitio() {
        return document.getElementById("cleo_checkout_address_guard");
    }

    function radioEntregaSeleccionado() {
        var radios = qa(CONFIG.deliveryRadios);
        for (var i = 0; i < radios.length; i++) {
            if (radios[i].checked) { return radios[i]; }
        }
        return null;
    }

    function entregaEnTiendaSeleccionada() {
        var r = radioEntregaSeleccionado();
        if (r && r.dataset && r.dataset.deliveryType === "in_store") { return true; }
        var g = guardDelSitio();
        if (g && g.dataset && g.dataset.isInStore === "1") { return true; }
        return false;
    }

    function direccionIncompleta() {
        var g = guardDelSitio();
        if (g && g.dataset) {
            if (g.dataset.isInStore === "1") { return false; } // en tienda no exige dirección
            if (g.dataset.addressComplete === "0") { return true; }
            if (g.dataset.addressComplete === "1") { return false; }
        }
        // Respaldo: tarjeta de dirección seleccionada marcada como incompleta.
        var card = q(".cleo-checkout-address-card[data-cleo-selected='1']") ||
            q(".cleo-checkout-address-card--selected");
        if (card && card.dataset && card.dataset.cleoAddressComplete === "0") { return true; }
        return false;
    }

    // =========================================================================
    // RENDER DEL MENSAJE (uno a la vez, encima del botón)
    // =========================================================================
    var BOX_ID = "o_checkout_hint";

    function iconSvg() {
        return '<span class="o_checkout_hint_icon" aria-hidden="true">' +
            '<svg width="16" height="16" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">' +
            '<circle cx="8" cy="8" r="7" stroke="currentColor" stroke-width="1.4"/>' +
            '<rect x="7.25" y="6.7" width="1.5" height="4.6" rx="0.75" fill="currentColor"/>' +
            '<circle cx="8" cy="4.7" r="0.95" fill="currentColor"/>' +
            "</svg></span>";
    }

    function ensureBox(btn) {
        var box = document.getElementById(BOX_ID);
        if (box && box.nextElementSibling !== btn && box.parentNode) {
            // Reubica el mensaje justo antes del botón si el DOM se re-renderizó.
            box.parentNode.removeChild(box);
            box = null;
        }
        if (!box) {
            box = document.createElement("div");
            box.id = BOX_ID;
            box.setAttribute("role", "status");
            box.setAttribute("aria-live", "polite");
            box.innerHTML = iconSvg() + '<span class="o_checkout_hint_text"></span>';
        }
        if (box.nextElementSibling !== btn) {
            btn.parentNode.insertBefore(box, btn);
        }
        return box;
    }

    function show(box, texto) {
        var span = box.querySelector(".o_checkout_hint_text");
        if (span && span.textContent !== texto) { span.textContent = texto; }
        box.classList.add("o_visible");
    }

    function hide() {
        var box = document.getElementById(BOX_ID);
        if (box) { box.classList.remove("o_visible"); }
    }

    // =========================================================================
    // EVALUACIÓN
    // =========================================================================
    function evaluar() {
        var btn = findButton();
        if (!btn) { hide(); return; }
        var ctx = { btn: btn, disabled: isDisabled(btn) };
        if (!ctx.disabled) { hide(); return; }

        var fallando = [];
        for (var i = 0; i < CONDICIONES.length; i++) {
            var c = CONDICIONES[i];
            var f = false;
            try { f = c.falla(ctx); } catch (e) { f = false; }
            if (f) { fallando.push(c); }
        }
        if (!fallando.length) { hide(); return; }

        fallando.sort(function (a, b) { return b.prioridad - a.prioridad; });
        var top = fallando[0];
        var texto = "";
        try { texto = top.texto(ctx); } catch (e) { texto = ""; }
        if (!texto) { hide(); return; }

        var box = ensureBox(btn);
        show(box, texto);
    }

    // Debounce para no reevaluar en exceso ante ráfagas de mutaciones.
    var pendiente = null;
    function evaluarDebounced() {
        if (pendiente) { return; }
        pendiente = window.setTimeout(function () {
            pendiente = null;
            evaluar();
        }, 80);
    }

    // =========================================================================
    // INICIALIZACIÓN
    // =========================================================================
    function esPaginaTienda() {
        if (q(".oe_website_sale")) { return true; }
        return /\/shop(\/|$)/.test(window.location.pathname);
    }

    function init() {
        if (!esPaginaTienda()) { return; }

        // Reevaluación reactiva ante cambios del DOM (Odoo recalcula tarifas de
        // envío por RPC y reemplaza nodos; también alterna la clase "disabled").
        try {
            var observer = new MutationObserver(function () { evaluarDebounced(); });
            observer.observe(document.body, {
                subtree: true,
                childList: true,
                attributes: true,
                attributeFilter: ["class", "disabled", "aria-disabled", "checked"],
            });
        } catch (e) { /* MutationObserver no disponible: usamos el intervalo */ }

        // Interacciones directas del cliente.
        document.addEventListener("change", evaluarDebounced, true);
        document.addEventListener("click", evaluarDebounced, true);

        // Red de seguridad.
        window.setInterval(evaluar, CONFIG.safetyIntervalMs);

        // Primeras evaluaciones (la página puede seguir cargando/rehidratando).
        evaluar();
        window.setTimeout(evaluar, 400);
        window.setTimeout(evaluar, 1200);
    }

    if (document.readyState !== "loading") {
        init();
    } else {
        document.addEventListener("DOMContentLoaded", init);
    }
})();

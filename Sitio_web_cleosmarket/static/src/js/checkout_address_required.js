/** @odoo-module **/

(function () {
    "use strict";

    let observer = null;
    let debounceTimer = null;
    let lastAppliedAt = 0;

    // La página tiene varios MutationObserver independientes (de este módulo
    // y de website_sale_checkout_hints) que reaccionan entre sí: uno cambia
    // una clase, eso dispara al otro, que cambia otra clase, etc. Con un
    // debounce puro esa ráfaga continua puede reiniciar el temporizador
    // indefinidamente y dejar a applyButtonState() sin ejecutarse nunca
    // mientras dure el "ruido". DEBOUNCE_MS agrupa mutaciones cercanas;
    // MAX_WAIT_MS garantiza que, sin importar cuánto ruido haya, el estado
    // real se vuelva a aplicar como máximo cada MAX_WAIT_MS.
    const DEBOUNCE_MS = 120;
    const MAX_WAIT_MS = 300;

    const REQUIRED_FIELDS = [
        ["country", "país"],
        ["state", "departamento"],
        ["street", "dirección / calle"],
        ["latitude", "ubicación en mapa"],
        ["longitude", "ubicación en mapa"],
    ];

    function isCheckoutPage() {
        return window.location.pathname.includes("/shop/checkout");
    }

    function normalizeText(value) {
        return String(value || "").replace(/\s+/g, " ").trim();
    }

    function getGuard() {
        return document.getElementById("cleo_checkout_address_guard");
    }

    function getSelectedAddressCard() {
        // Orden importante: ".cleo-address-card-selected" es la única marca que
        // se actualiza en vivo (la aplica checkout_address_selection.js al
        // hacer clic en una tarjeta). Las demás (data-cleo-selected,
        // bg-primary, border-primary, --selected) se calculan una sola vez en
        // el render del servidor y quedan congeladas en la tarjeta que estaba
        // seleccionada al cargar la página, aunque el cliente elija otra
        // después sin recargar. Por eso van como respaldo, no como primera
        // opción.
        return (
            document.querySelector(".cleo-address-card-selected") ||
            document.querySelector(".cleo-checkout-address-card[data-cleo-selected='1']") ||
            document.querySelector(".cleo-checkout-address-card--selected") ||
            document.querySelector(".cleo-checkout-address-card.bg-primary") ||
            document.querySelector(".cleo-checkout-address-card.border-primary") ||
            document.querySelector("[name='address_card'].bg-primary") ||
            document.querySelector("[name='address_card'].border-primary")
        );
    }

    function readStatusFromGuard() {
        const guard = getGuard();

        if (!guard) {
            return null;
        }

        const dataset = guard.dataset || {};
        const missing = [];
        const uniqueLabels = new Set();

        REQUIRED_FIELDS.forEach(function ([key, label]) {
            if (dataset[`has${key.charAt(0).toUpperCase()}${key.slice(1)}`] === "0") {
                uniqueLabels.add(label);
            }
        });

        uniqueLabels.forEach(function (label) {
            missing.push(label);
        });

        return {
            isInStore: dataset.isInStore === "1",
            isComplete: dataset.addressComplete === "1",
            missing: missing,
            editUrl: dataset.editUrl || "/shop/address?address_type=delivery&callback=/shop/payment",
        };
    }

    function getEditUrlForCard(card) {
        const editLink = card.querySelector &&
            card.querySelector("a[href*='/shop/address'][href*='partner_id=']");

        return (editLink && editLink.getAttribute("href")) ||
            "/shop/address?address_type=delivery&use_delivery_as_billing=true&callback=/shop/payment";
    }

    function readStatusFromSelectedCard() {
        const card = getSelectedAddressCard();

        if (!card || !card.dataset) {
            return null;
        }

        const dataset = card.dataset;
        const missing = [];
        const checks = [
            ["cleoHasCountry", "país"],
            ["cleoHasState", "departamento"],
            ["cleoHasStreet", "dirección / calle"],
            ["cleoHasLatitude", "ubicación en mapa"],
            ["cleoHasLongitude", "ubicación en mapa"],
        ];
        const uniqueLabels = new Set();

        checks.forEach(function ([key, label]) {
            if (dataset[key] === "0") {
                uniqueLabels.add(label);
            }
        });

        uniqueLabels.forEach(function (label) {
            missing.push(label);
        });

        return {
            isInStore: false,
            isComplete: dataset.cleoAddressComplete === "1",
            missing: missing,
            editUrl: getEditUrlForCard(card),
            hasCountry: dataset.cleoHasCountry,
            hasState: dataset.cleoHasState,
            hasStreet: dataset.cleoHasStreet,
            hasLatitude: dataset.cleoHasLatitude,
            hasLongitude: dataset.cleoHasLongitude,
        };
    }

    function isInStoreSelectedClientSide() {
        const radios = Array.from(document.querySelectorAll("input[name='o_delivery_radio']"));
        const checked = radios.find(function (r) { return r.checked; });

        if (checked && checked.dataset && checked.dataset.deliveryType === "in_store") {
            return true;
        }

        // Opción rediseñada de tipo pickup marcada como seleccionada.
        if (document.querySelector(".cleo-delivery-option.is-selected[data-delivery-type='pickup']")) {
            return true;
        }

        // Respaldo por el texto de la opción seleccionada.
        if (checked) {
            const block = checked.closest("label, li, .cleo-checkout-delivery-method") || checked.parentElement;
            const text = normalizeText(block && block.textContent).toLowerCase();
            if (text.includes("entrega en tienda") || text.includes("retiro en tienda")) {
                return true;
            }
        }

        return false;
    }

    function syncGuardDataset(status) {
        const guard = getGuard();

        if (!guard) {
            return;
        }

        // El guard del servidor solo se calcula una vez por carga completa de
        // /shop/checkout. Cualquier cambio de método de entrega o de dirección
        // ocurre después por AJAX (nativo de Odoo o rutas propias de este
        // módulo) sin recargar la página, así que ese guard queda obsoleto de
        // inmediato. Otro módulo instalado (website_sale_checkout_hints) lee
        // ese mismo div directamente, así que lo mantenemos sincronizado aquí
        // en vez de duplicar esta lógica en cada consumidor.
        guard.dataset.isInStore = status.isInStore ? "1" : "0";
        guard.dataset.addressComplete = status.isComplete ? "1" : "0";

        if (status.hasCountry !== undefined) {
            guard.dataset.hasCountry = status.hasCountry;
        }
        if (status.hasState !== undefined) {
            guard.dataset.hasState = status.hasState;
        }
        if (status.hasStreet !== undefined) {
            guard.dataset.hasStreet = status.hasStreet;
        }
        if (status.hasLatitude !== undefined) {
            guard.dataset.hasLatitude = status.hasLatitude;
        }
        if (status.hasLongitude !== undefined) {
            guard.dataset.hasLongitude = status.hasLongitude;
        }
        if (status.editUrl) {
            guard.dataset.editUrl = status.editUrl;
        }
    }

    function computeLiveStatus() {
        const inStore = isInStoreSelectedClientSide();

        // La tarjeta de dirección seleccionada (si existe) ya trae, para TODA
        // tarjeta renderizada, sus propios data-cleo-has-* — no hace falta
        // ningún viaje al servidor para saber si la dirección activa está
        // completa: ya está en el DOM en el momento en que el cliente elige
        // método de entrega o tarjeta de dirección.
        const cardStatus = readStatusFromSelectedCard();

        if (cardStatus) {
            cardStatus.isInStore = inStore;

            if (inStore) {
                cardStatus.isComplete = true;
                cardStatus.missing = [];
            }

            return cardStatus;
        }

        // No hay tarjeta de dirección visible todavía (p. ej. primer render
        // antes de que el resto del checkout termine de hidratarse): usamos
        // el guard del servidor como mejor aproximación disponible.
        const guardStatus = readStatusFromGuard();

        if (guardStatus) {
            if (inStore) {
                guardStatus.isInStore = true;
                guardStatus.isComplete = true;
                guardStatus.missing = [];
            }
            return guardStatus;
        }

        return {
            isInStore: inStore,
            isComplete: true,
            missing: [],
            editUrl: "/shop/address?address_type=delivery&callback=/shop/payment",
        };
    }

    function getAddressStatus() {
        const status = computeLiveStatus();

        // Mantiene el guard del servidor al día para que otros scripts que lo
        // leen (dentro o fuera de este módulo) siempre encuentren datos
        // vigentes, sin depender de una recarga completa de la página.
        syncGuardDataset(status);

        return status;
    }

    function isProceedButton(element) {
        if (!element || !element.matches || !element.matches("a, button")) {
            return false;
        }

        if (element.getAttribute("name") === "website_sale_main_button") {
            return true;
        }

        const href = String(element.getAttribute("href") || "").toLowerCase();
        const text = normalizeText(element.textContent).toLowerCase();

        return (
            href.includes("/shop/payment") ||
            href.includes("/shop/confirm_order") ||
            text.includes("proceder a comprar") ||
            text.includes("continuar") ||
            text.includes("pagar")
        );
    }

    function getProceedButtons() {
        return Array.from(document.querySelectorAll("a, button")).filter(isProceedButton);
    }

    function ensureAlert(status) {
        let alert = document.getElementById("cleo_checkout_address_required_alert");

        if (status.isComplete) {
            if (alert) {
                alert.remove();
            }
            return null;
        }

        if (!alert) {
            alert = document.createElement("div");
            alert.id = "cleo_checkout_address_required_alert";
            alert.className = "cleo-checkout-address-required-alert alert alert-warning";
            alert.setAttribute("role", "alert");

            const guard = getGuard();
            const section = document.querySelector(".cleo-checkout-address-section") ||
                document.getElementById("delivery_address_row") ||
                (guard && guard.parentElement) ||
                document.getElementById("shop_checkout") ||
                document.body;

            if (section.firstElementChild) {
                section.insertBefore(alert, section.firstElementChild.nextSibling);
            } else {
                section.appendChild(alert);
            }
        }

        const missingText = status.missing.length ? status.missing.join(", ") : "los datos obligatorios";

        alert.innerHTML = `
            <div class="cleo-checkout-address-required-alert__icon">
                <i class="fa fa-map-marker" aria-hidden="true"></i>
            </div>
            <div class="cleo-checkout-address-required-alert__body">
                <strong>Completa tu dirección antes de continuar.</strong>
                <span>Falta completar: ${missingText}.</span>
                <a class="cleo-checkout-address-required-alert__link" href="${status.editUrl}">
                    Editar dirección
                </a>
            </div>
        `;

        return alert;
    }

    function updateAddressCards() {
        const cards = Array.from(document.querySelectorAll(".cleo-checkout-address-card, [name='address_card']"));

        cards.forEach(function (card) {
            const complete = card.dataset && card.dataset.cleoAddressComplete === "1";
            const selected = card.dataset && card.dataset.cleoSelected === "1";

            card.classList.toggle("cleo-checkout-address-card--incomplete", !complete);

            let badge = card.querySelector(".cleo-address-required-badge");
            if (complete) {
                if (badge) {
                    badge.remove();
                }
                return;
            }

            if (!badge) {
                badge = document.createElement("span");
                badge.className = "cleo-address-required-badge";
                card.appendChild(badge);
            }

            badge.innerHTML = selected
                ? `<i class="fa fa-exclamation-triangle me-1" aria-hidden="true"></i> Completar para continuar`
                : `<i class="fa fa-exclamation-triangle me-1" aria-hidden="true"></i> Dirección incompleta`;
        });
    }

    function applyButtonState() {
        if (!isCheckoutPage()) {
            return;
        }

        lastAppliedAt = Date.now();

        const status = getAddressStatus();
        const buttons = getProceedButtons();

        // Mismo criterio que usa el widget nativo de Odoo para considerar
        // "listo" el método de envío (this._isDeliveryMethodReady): si hay
        // radios de método de entrega, al menos uno debe estar marcado; si no
        // hay ninguno (pedido de solo servicios, por ejemplo), no bloqueamos
        // por este motivo.
        const deliveryRadios = document.querySelectorAll("input[name='o_delivery_radio']");
        const hasDeliveryMethodSelected = deliveryRadios.length === 0 ||
            Array.from(deliveryRadios).some(function (radio) { return radio.checked; });

        ensureAlert(status);
        updateAddressCards();

        buttons.forEach(function (button) {
            if (!status.isComplete) {
                button.classList.add("disabled", "cleo-address-required-disabled");
                button.setAttribute("aria-disabled", "true");
                button.dataset.cleoAddressGuardDisabled = "1";
                button.title = "Completa tu dirección de entrega antes de continuar.";

                if (button.tagName === "BUTTON") {
                    button.disabled = true;
                }
            } else if (hasDeliveryMethodSelected) {
                // Dirección (o entrega en tienda) completa y método de envío
                // elegido: nos encargamos de habilitar el botón aunque el
                // "disabled" lo haya puesto el widget nativo del checkout.
                // Su propio re-chequeo tras seleccionar el método no siempre
                // se cumple con el flujo propio de "Entrega en tienda", que
                // no pasa por el selector de ubicación nativo de Odoo.
                button.classList.remove("cleo-address-required-disabled", "disabled");
                button.removeAttribute("aria-disabled");
                button.removeAttribute("title");
                delete button.dataset.cleoAddressGuardDisabled;

                if (button.tagName === "BUTTON") {
                    button.disabled = false;
                }
            }
        });
    }

    function blockInvalidNavigation(event) {
        const button = event.target.closest && event.target.closest("a, button");

        if (!isProceedButton(button)) {
            return;
        }

        const status = getAddressStatus();

        if (status.isComplete) {
            return;
        }

        event.preventDefault();
        event.stopPropagation();
        event.stopImmediatePropagation();

        const alert = ensureAlert(status);
        applyButtonState();

        if (alert && alert.scrollIntoView) {
            alert.scrollIntoView({ behavior: "smooth", block: "center" });
        }
    }

    function watchChanges() {
        if (observer || !isCheckoutPage()) {
            return;
        }

        observer = new MutationObserver(function () {
            // Si ya pasó MAX_WAIT_MS desde la última aplicación real del
            // estado, lo forzamos de inmediato en vez de seguir postergando:
            // en ráfagas continuas de mutaciones (varios scripts reaccionando
            // entre sí) un debounce puro puede reiniciarse indefinidamente y
            // dejar el botón con un estado que ya no corresponde a la
            // realidad, sin margen de tiempo para autocorregirse.
            if (Date.now() - lastAppliedAt >= MAX_WAIT_MS) {
                window.clearTimeout(debounceTimer);
                applyButtonState();
                return;
            }

            window.clearTimeout(debounceTimer);
            debounceTimer = window.setTimeout(applyButtonState, DEBOUNCE_MS);
        });

        observer.observe(document.body, {
            childList: true,
            subtree: true,
            attributes: true,
            attributeFilter: ["class", "style", "disabled", "aria-disabled"],
        });
    }

    function init() {
        if (!isCheckoutPage()) {
            return;
        }

        document.addEventListener("click", blockInvalidNavigation, true);
        applyButtonState();
        watchChanges();

        // computeLiveStatus() ya recalcula el estado real desde el DOM (radio
        // de entrega marcado + tarjeta de dirección seleccionada) en cada
        // llamada, así que estos reintentos son solo una red de seguridad
        // para mutaciones que el observer no capture (attributeFilter
        // limitado); ya no son el mecanismo del que depende la corrección.
        setTimeout(applyButtonState, 300);
        setTimeout(applyButtonState, 900);
        setTimeout(applyButtonState, 1800);
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }
})();

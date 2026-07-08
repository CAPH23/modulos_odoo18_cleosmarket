/** @odoo-module **/

(function () {
    "use strict";

    let observer = null;
    let debounceTimer = null;

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
        return (
            document.querySelector(".cleo-checkout-address-card[data-cleo-selected='1']") ||
            document.querySelector(".cleo-checkout-address-card--selected") ||
            document.querySelector(".cleo-address-card-selected") ||
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
            editUrl: "/shop/address?address_type=delivery&use_delivery_as_billing=true&callback=/shop/payment",
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

    function getAddressStatus() {
        const status = readStatusFromGuard() || readStatusFromSelectedCard();

        if (!status) {
            return {
                isInStore: false,
                isComplete: true,
                missing: [],
                editUrl: "/shop/address?address_type=delivery&callback=/shop/payment",
            };
        }

        // NUEVO: reconoce "en tienda" también desde la selección del cliente,
        // aunque el guard del servidor aún no se haya actualizado.
        if (isInStoreSelectedClientSide()) {
            status.isInStore = true;
        }

        // Para retiro/entrega en tienda se mantiene el flujo actual del módulo:
        // se usa la dirección de la tienda y no se obliga la ubicación del cliente.
        if (status.isInStore) {
            status.isComplete = true;
            status.missing = [];
        }

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

        const status = getAddressStatus();
        const buttons = getProceedButtons();

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
            } else if (button.dataset.cleoAddressGuardDisabled === "1") {
                button.classList.remove("cleo-address-required-disabled");
                button.removeAttribute("aria-disabled");
                button.removeAttribute("title");
                delete button.dataset.cleoAddressGuardDisabled;

                if (button.tagName === "BUTTON") {
                    button.disabled = false;
                }

                // Solo quitamos la clase disabled si fue puesta por este control.
                button.classList.remove("disabled");
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
            window.clearTimeout(debounceTimer);
            debounceTimer = window.setTimeout(applyButtonState, 120);
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

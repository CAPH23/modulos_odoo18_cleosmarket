/** @odoo-module **/

(function () {
    "use strict";

    let addressObserver = null;
    let initTimer = null;

    function isCheckoutPage() {
        return window.location.pathname.includes("/shop/checkout");
    }

    function normalizeText(value) {
        return String(value || "").replace(/\s+/g, " ").trim();
    }

    function isAddressActionClick(target) {
        const action = target.closest("a, button");

        if (!action) {
            return false;
        }

        const text = normalizeText(action.textContent).toLowerCase();
        const href = String(action.getAttribute("href") || "").toLowerCase();

        return (
            action.classList.contains("cleo-address-delete-link") ||
            text.includes("editar") ||
            text.includes("edit") ||
            text.includes("eliminar") ||
            text.includes("delete") ||
            text.includes("añadir dirección") ||
            text.includes("anadir direccion") ||
            text.includes("add address") ||
            href.includes("/shop/address")
        );
    }

    function getAddressCardFromEditLink(editLink) {
        return (
            editLink.closest(".card") ||
            editLink.closest("[class*='card']") ||
            editLink.closest(".col") ||
            editLink.parentElement
        );
    }

    function getAddressCards() {
        const cards = new Set();

        const editLinks = Array.from(
            document.querySelectorAll("a[href*='/shop/address'][href*='partner_id=']")
        );

        editLinks.forEach(function (editLink) {
            const text = normalizeText(editLink.textContent).toLowerCase();

            if (!text.includes("editar") && !text.includes("edit")) {
                return;
            }

            const card = getAddressCardFromEditLink(editLink);

            if (!card) {
                return;
            }

            const cardText = normalizeText(card.textContent).toLowerCase();

            if (
                cardText.includes("añadir dirección") ||
                cardText.includes("anadir direccion") ||
                cardText.includes("add address")
            ) {
                return;
            }

            cards.add(card);
        });

        return Array.from(cards);
    }

    function cardLooksSelected(card) {
        const className = String(card.className || "").toLowerCase();

        if (
            card.classList.contains("cleo-address-card-selected") ||
            className.includes("border-primary") ||
            className.includes("border-danger") ||
            className.includes("border-success") ||
            className.includes("border-2") ||
            className.includes("border-3") ||
            className.includes("active")
        ) {
            return true;
        }

        const style = window.getComputedStyle(card);
        const borderColor = String(style.borderTopColor || "").toLowerCase();

        return (
            borderColor.includes("233") ||
            borderColor.includes("220") ||
            borderColor.includes("241") ||
            borderColor.includes("rgb(233") ||
            borderColor.includes("rgb(220") ||
            borderColor.includes("rgb(241")
        );
    }

    function ensureSelectedBadge(card) {
        if (card.querySelector(".cleo-address-selected-badge")) {
            return;
        }

        const badge = document.createElement("span");
        badge.className = "cleo-address-selected-badge";
        badge.innerHTML = `<i class="fa fa-check me-1" aria-hidden="true"></i> Seleccionada`;

        card.appendChild(badge);
    }

    function markCards() {
        if (!isCheckoutPage()) {
            return;
        }

        const cards = getAddressCards();

        cards.forEach(function (card) {
            card.classList.add("cleo-checkout-address-card");
            ensureSelectedBadge(card);
        });

        const alreadySelected = cards.find(function (card) {
            return card.classList.contains("cleo-address-card-selected");
        });

        if (alreadySelected) {
            return;
        }

        const selectedByOdoo = cards.find(cardLooksSelected);

        if (selectedByOdoo) {
            setSelectedAddressCard(selectedByOdoo);
        }
    }

    function setSelectedAddressCard(selectedCard) {
        const cards = getAddressCards();

        cards.forEach(function (card) {
            card.classList.add("cleo-checkout-address-card");
            ensureSelectedBadge(card);

            const isSelected = card === selectedCard;

            card.classList.toggle("cleo-address-card-selected", isSelected);
            card.classList.toggle("cleo-address-card-not-selected", !isSelected);

            if (!isSelected) {
                card.classList.remove("border-primary", "border-danger", "border-success", "border-2", "border-3", "active");
            }
        });
    }

    function bindAddressCardClicks() {
        if (!isCheckoutPage()) {
            return;
        }

        if (document.body.dataset.cleoAddressSelectionReady === "1") {
            return;
        }

        document.body.dataset.cleoAddressSelectionReady = "1";

        document.addEventListener("click", function (event) {
            const card = event.target.closest(".cleo-checkout-address-card");

            if (!card) {
                return;
            }

            if (isAddressActionClick(event.target)) {
                return;
            }

            setSelectedAddressCard(card);

            setTimeout(markCards, 300);
            setTimeout(markCards, 900);
        }, true);
    }

    function watchAddressChanges() {
        if (addressObserver || !isCheckoutPage()) {
            return;
        }

        addressObserver = new MutationObserver(function () {
            window.clearTimeout(initTimer);

            initTimer = window.setTimeout(function () {
                markCards();
            }, 250);
        });

        addressObserver.observe(document.body, {
            childList: true,
            subtree: true,
            attributes: true,
            attributeFilter: ["class", "style"],
        });
    }

    function initAddressSelection() {
        if (!isCheckoutPage()) {
            return;
        }

        markCards();
        bindAddressCardClicks();
        watchAddressChanges();

        setTimeout(markCards, 600);
        setTimeout(markCards, 1200);
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", initAddressSelection);
    } else {
        initAddressSelection();
    }
})();

/** @odoo-module **/

(function () {
    "use strict";

    let deliveryObserver = null;
    let deliveryInitTimer = null;
    let applyingDefaultPickup = false;
    let buildingDeliverySection = false;

    function isCheckoutPage() {
        return window.location.pathname.includes("/shop/checkout");
    }

    function normalizeText(value) {
        return String(value || "").replace(/\s+/g, " ").trim();
    }

    function getCsrfToken() {
        if (window.odoo && window.odoo.csrf_token) {
            return window.odoo.csrf_token;
        }

        const input = document.querySelector("input[name='csrf_token']");
        return input && input.value ? input.value : "";
    }

    function getPartnerIdFromHref(href) {
        try {
            const url = new URL(href, window.location.origin);
            return url.searchParams.get("partner_id");
        } catch (error) {
            return null;
        }
    }

    function getCarrierIdFromRadio(radio) {
        if (!radio) {
            return "";
        }

        return radio.dataset.dmId || radio.value || String(radio.id || "").replace("o_delivery_", "");
    }

    function createDeleteButton(partnerId) {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "cleo-address-delete-link";
        button.dataset.partnerId = partnerId;
        button.innerHTML = `<i class="fa fa-trash-o me-1" aria-hidden="true"></i>Eliminar`;

        button.addEventListener("click", async function () {
            const confirmed = window.confirm(
                "¿Deseas eliminar esta dirección? Esta acción quitará la tarjeta del checkout."
            );

            if (!confirmed) {
                return;
            }

            button.disabled = true;
            button.classList.add("is-loading");

            try {
                const body = new URLSearchParams();
                body.append("partner_id", partnerId);

                const csrfToken = getCsrfToken();
                if (csrfToken) {
                    body.append("csrf_token", csrfToken);
                }

                const response = await fetch("/cleo/address/archive", {
                    method: "POST",
                    credentials: "same-origin",
                    headers: {
                        "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
                    },
                    body: body.toString(),
                });

                const result = await response.json();

                if (!response.ok || !result.success) {
                    throw new Error(result.error || "No se pudo eliminar la dirección.");
                }

                window.location.reload();
            } catch (error) {
                alert(error.message || "No se pudo eliminar la dirección.");
                button.disabled = false;
                button.classList.remove("is-loading");
            }
        });

        return button;
    }

    function addDeleteLinksToAddressCards() {
        if (!isCheckoutPage()) {
            return;
        }

        const editLinks = Array.from(
            document.querySelectorAll("a[href*='/shop/address'][href*='partner_id=']")
        );

        editLinks.forEach(function (editLink) {
            const text = normalizeText(editLink.textContent).toLowerCase();

            if (!text.includes("editar") && !text.includes("edit")) {
                return;
            }

            const partnerId = getPartnerIdFromHref(editLink.href);

            if (!partnerId) {
                return;
            }

            const parent = editLink.parentElement;

            if (!parent || parent.querySelector(".cleo-address-delete-link")) {
                return;
            }

            // Envolvemos "Editar" y "Eliminar" en una fila de acciones para
            // evitar que se solapen entre sí y con el badge de estado.
            let actions = parent.querySelector(".cleo-address-actions");
            if (!actions) {
                actions = document.createElement("div");
                actions.className = "cleo-address-actions";
                editLink.parentElement.insertBefore(actions, editLink);
                actions.appendChild(editLink);
            }

            actions.appendChild(createDeleteButton(partnerId));
        });
    }

    function getDeliveryIcon(type) {
        if (type === "pickup" || type === "in_store") {
            return `
                <svg class="cleo-delivery-svg" viewBox="0 0 64 64" aria-hidden="true">
                    <path d="M14 26h36"/>
                    <path d="M18 26l4-12h20l4 12"/>
                    <path d="M18 26v26h28V26"/>
                    <path d="M26 52V38h12v14"/>
                    <path d="M22 14h20"/>
                    <path d="M20 30h6"/>
                    <path d="M38 30h6"/>
                    <path d="M28 14v12"/>
                    <path d="M36 14v12"/>
                </svg>
            `;
        }

        if (type === "express") {
            return `
                <svg class="cleo-delivery-svg" viewBox="0 0 64 64" aria-hidden="true">
                    <path d="M8 22h29v21H8z"/>
                    <path d="M37 29h9l8 8v6H37z"/>
                    <circle cx="20" cy="48" r="5"/>
                    <circle cx="47" cy="48" r="5"/>
                    <path d="M5 29h13"/>
                    <path d="M3 36h15"/>
                    <path d="M7 43h8"/>
                </svg>
            `;
        }

        return `
            <svg class="cleo-delivery-svg" viewBox="0 0 64 64" aria-hidden="true">
                <path d="M10 18h31v25H10z"/>
                <path d="M41 27h8l7 8v8H41z"/>
                <circle cx="22" cy="48" r="5"/>
                <circle cx="48" cy="48" r="5"/>
                <path d="M17 48h-4"/>
                <path d="M36 48H27"/>
                <path d="M43 48h-2"/>
            </svg>
        `;
    }

    function inferVisualType(method) {
        const name = String(method.title || "").toLowerCase();

        if (method.type === "pickup" || method.type === "in_store") {
            return "pickup";
        }

        if (name.includes("express") || name.includes("exprés")) {
            return "express";
        }

        return "delivery";
    }

    function findMethodBlock(radio) {
        let node = radio.parentElement;
        let best = null;

        for (let i = 0; node && i < 10; i += 1, node = node.parentElement) {
            const hasRadio = node.contains(radio);
            const hasPrice = Boolean(node.querySelector("[name='price'], .cleo-checkout-delivery-price"));
            const hasPickup = Boolean(node.querySelector("[name='o_pickup_location']"));
            const hasLabel = radio.id ? Boolean(node.querySelector(`label[for="${radio.id}"]`)) : false;

            if (hasRadio && (hasPrice || hasPickup || hasLabel)) {
                best = node;
            }

            if (hasRadio && hasPrice) {
                return node;
            }
        }

        return best || radio.closest("label") || radio.parentElement;
    }

    function readTitleFromDom(radio, block) {
        const selectors = [];

        if (radio.id) {
            selectors.push(`label[for="${radio.id}"]`);
        }

        selectors.push(
            ".cleo-checkout-delivery-label",
            ".o_wsale_delivery_method_name",
            "[name='delivery_method_name']",
            "label"
        );

        for (const selector of selectors) {
            const element = block.querySelector(selector);

            if (!element) {
                continue;
            }

            let text = normalizeText(element.textContent);

            text = text
                .replace(/\$\s*[0-9]+(?:[,.][0-9]{1,2})?/g, "")
                .replace(/Gratuito/gi, "")
                .replace(/Select a location/gi, "")
                .replace(/Seleccionar ubicación/gi, "")
                .replace(/Seleccione ubicación/gi, "")
                .trim();

            if (text && text.length <= 80) {
                return text;
            }
        }

        return "";
    }

    function readPriceFromDom(block) {
        const priceElement = block.querySelector(
            "[name='price'], .cleo-checkout-delivery-price, .o_wsale_delivery_badge"
        );

        if (priceElement) {
            const priceText = normalizeText(priceElement.textContent);
            if (priceText) {
                return priceText;
            }
        }

        const text = normalizeText(block.textContent);
        const freeMatch = text.match(/gratuito/i);

        if (freeMatch) {
            return "Gratuito";
        }

        const priceMatch = text.match(/\$\s*[0-9]+(?:[,.][0-9]{1,2})?/);

        if (priceMatch) {
            return priceMatch[0].replace(/\s+/g, " ");
        }

        return "";
    }

    function findPickupLocationTrigger(method) {
        const exactSelector = [
            "button[name='o_pickup_location_selector']",
            "span[name='o_pickup_location_selector']"
        ].join(",");

        const candidates = [];

        if (method && method.block) {
            candidates.push(...Array.from(method.block.querySelectorAll(exactSelector)));
        }

        candidates.push(...Array.from(document.querySelectorAll(exactSelector)));

        return candidates.find(function (element) {
            if (!element) {
                return false;
            }

            if (element.closest(".cleo-delivery-redesign")) {
                return false;
            }

            if (element.closest("header") || element.closest("footer")) {
                return false;
            }

            return Boolean(element.closest("[name='o_pickup_location']"));
        }) || null;
    }

    function findDeliveryMethods() {
        const radios = Array.from(document.querySelectorAll("input[name='o_delivery_radio']"));
        const methods = [];

        radios.forEach(function (radio) {
            const block = findMethodBlock(radio);

            if (!block) {
                return;
            }

            const carrierId = getCarrierIdFromRadio(radio);
            const deliveryType = radio.dataset.deliveryType || "";
            const titleFromDom = readTitleFromDom(radio, block);
            const priceFromDom = readPriceFromDom(block);

            const isPickup =
                deliveryType === "in_store" ||
                normalizeText(block.textContent).toLowerCase().includes("entrega en tienda");

            methods.push({
                radio: radio,
                block: block,
                carrierId: carrierId,
                type: isPickup ? "pickup" : "delivery",
                deliveryType: deliveryType,
                title: titleFromDom || "Método de entrega",
                description: isPickup
                    ? "Retira tu pedido en nuestra tienda cuando tu compra esté confirmada."
                    : "Recibe tu pedido en la dirección seleccionada.",
                price: priceFromDom,
                pickupTrigger: null,
            });
        });

        const unique = [];
        const seen = new Set();

        methods.forEach(function (method) {
            const key = method.carrierId || method.radio.id;

            if (seen.has(key)) {
                return;
            }

            seen.add(key);
            unique.push(method);
        });

        return unique;
    }

    async function hydrateMethodsFromServer(methods) {
        const carrierIds = methods
            .map(function (method) { return method.carrierId; })
            .filter(Boolean);

        if (!carrierIds.length) {
            return methods;
        }

        try {
            const body = new URLSearchParams();
            const csrfToken = getCsrfToken();

            if (csrfToken) {
                body.append("csrf_token", csrfToken);
            }

            body.append("carrier_ids", JSON.stringify(carrierIds));

            const response = await fetch("/cleo/delivery/methods/info", {
                method: "POST",
                credentials: "same-origin",
                headers: {
                    "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
                },
                body: body.toString(),
            });

            const result = await response.json();

            if (!response.ok || !result.success) {
                return methods;
            }

            methods.forEach(function (method) {
                const info = result.methods[String(method.carrierId)];

                if (!info) {
                    return;
                }

                method.title = info.name || method.title;
                method.deliveryType = info.delivery_type || method.deliveryType;
                method.type = info.delivery_type === "in_store" ? "pickup" : "delivery";
                method.description = info.description || method.description;
                method.price = info.price_label || method.price;
            });
        } catch (error) {
            console.warn("No se pudieron obtener datos reales de métodos de entrega:", error);
        }

        return methods;
    }

    function findCommonParent(elements) {
        if (!elements.length) {
            return null;
        }

        let parent = elements[0].parentElement;

        while (parent && !elements.every(function (element) { return parent.contains(element); })) {
            parent = parent.parentElement;
        }

        return parent;
    }

    function enableProceedButtons() {
        const buttons = Array.from(document.querySelectorAll("a, button"));

        buttons.forEach(function (button) {
            const text = normalizeText(button.textContent).toLowerCase();

            if (
                text.includes("proceder a comprar") ||
                text.includes("continuar") ||
                text.includes("pagar")
            ) {
                button.classList.remove("disabled");
                button.removeAttribute("disabled");
                button.removeAttribute("aria-disabled");
            }
        });
    }

    async function openOriginalPickupSelector(method) {
        if (!method.radio.checked) {
            method.radio.click();
        } else {
            method.radio.dispatchEvent(new Event("change", { bubbles: true }));
        }

        await new Promise(function (resolve) {
            setTimeout(resolve, 350);
        });

        let trigger = findPickupLocationTrigger(method);

        if (trigger) {
            trigger.dispatchEvent(new MouseEvent("click", {
                bubbles: true,
                cancelable: true,
                view: window,
            }));
            return true;
        }

        await new Promise(function (resolve) {
            setTimeout(resolve, 900);
        });

        trigger = findPickupLocationTrigger(method);

        if (trigger) {
            trigger.dispatchEvent(new MouseEvent("click", {
                bubbles: true,
                cancelable: true,
                view: window,
            }));
            return true;
        }

        return false;
    }

    async function applyDefaultPickup(method, wrapper) {
        if (applyingDefaultPickup) {
            return;
        }

        applyingDefaultPickup = true;

        const pickupInfo = wrapper.querySelector(".cleo-pickup-info");
        if (pickupInfo) {
            pickupInfo.classList.add("is-loading");
        }

        try {
            const body = new URLSearchParams();
            const csrfToken = getCsrfToken();
            const carrierId = getCarrierIdFromRadio(method.radio);

            if (csrfToken) {
                body.append("csrf_token", csrfToken);
            }

            if (carrierId) {
                body.append("carrier_id", carrierId);
            }

            const response = await fetch("/cleo/pickup/default", {
                method: "POST",
                credentials: "same-origin",
                headers: {
                    "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
                },
                body: body.toString(),
            });

            const result = await response.json();

            if (!response.ok || !result.success) {
                throw new Error(result.error || "No se pudo seleccionar Super Tienda Cleo.");
            }

            if (pickupInfo) {
                pickupInfo.classList.remove("is-loading");
                pickupInfo.classList.add("is-ready");
            }

            enableProceedButtons();
        } catch (error) {
            console.warn("No se pudo seleccionar la ubicación por defecto:", error);
            if (pickupInfo) {
                pickupInfo.classList.remove("is-loading");
            }
        } finally {
            applyingDefaultPickup = false;
        }
    }

    function buildDeliveryRedesign(methods) {
        const wrapper = document.createElement("div");
        wrapper.className = "cleo-delivery-redesign";
        wrapper.setAttribute("aria-label", "Métodos de entrega");

        methods.forEach(function (method) {
            const visualType = inferVisualType(method);

            const option = document.createElement("button");
            option.type = "button";
            option.className = "cleo-delivery-option";
            option.dataset.radioId = method.radio.id || "";
            option.dataset.deliveryType = method.type;
            option.dataset.carrierId = method.carrierId || "";

            const pickupPanel = method.type === "pickup"
                ? `
                    <span class="cleo-pickup-info">
                        <span class="cleo-pickup-selected">
                            <i class="fa fa-map-marker me-1" aria-hidden="true"></i>
                            Super Tienda Cleo seleccionada
                        </span>
                        <span class="cleo-pickup-change" role="button">
                            Cambiar
                        </span>
                    </span>
                `
                : "";

            const descriptionHtml = method.description
	        ? `<span class="cleo-delivery-description">${method.description}</span>`
	        : "";

	    option.innerHTML = `
	        <span class="cleo-delivery-radio-dot" aria-hidden="true">
	            <span></span>
	        </span>

	        <span class="cleo-delivery-main">
	            <span class="cleo-delivery-title">${method.title}</span>
	            ${descriptionHtml}
	            ${pickupPanel}
	        </span>

	        <span class="cleo-delivery-icon-badge" aria-hidden="true">
	            ${getDeliveryIcon(visualType)}
	        </span>

	        <span class="cleo-delivery-price">${method.price || "Calculando..."}</span>
	    `;

            option.addEventListener("click", async function (event) {
                const changeButton = event.target.closest(".cleo-pickup-change");

                if (changeButton) {
                    event.preventDefault();
                    event.stopPropagation();

                    const opened = await openOriginalPickupSelector(method);

                    if (!opened) {
                        alert("No se encontró el selector original de ubicación de Odoo: o_pickup_location_selector.");
                    }

                    return;
                }

                if (!method.radio.checked) {
                    method.radio.click();
                } else {
                    method.radio.dispatchEvent(new Event("change", { bubbles: true }));
                }

                syncDeliverySelection(wrapper, methods);

                if (method.type === "pickup") {
                    await applyDefaultPickup(method, wrapper);
                }

                setTimeout(function () {
                    syncDeliverySelection(wrapper, methods);
                }, 120);
            });

            wrapper.appendChild(option);
        });

        syncDeliverySelection(wrapper, methods);
        return wrapper;
    }

    function syncDeliverySelection(wrapper, methods) {
        const options = Array.from(wrapper.querySelectorAll(".cleo-delivery-option"));

        options.forEach(function (option, index) {
            const method = methods[index];

            if (!method) {
                return;
            }

            option.classList.toggle("is-selected", method.radio.checked);
        });
    }

    async function improveDeliverySection() {
        if (!isCheckoutPage() || buildingDeliverySection) {
            return;
        }

        const existing = document.querySelector(".cleo-delivery-redesign");
        if (existing) {
            return;
        }

        buildingDeliverySection = true;

        try {
            let methods = findDeliveryMethods();

            if (methods.length < 1) {
                return;
            }

            methods = await hydrateMethodsFromServer(methods);

            const blocks = methods.map(function (method) {
                return method.block;
            });

            const originalContainer = findCommonParent(blocks);

            if (!originalContainer) {
                return;
            }

            const redesigned = buildDeliveryRedesign(methods);

            originalContainer.parentNode.insertBefore(redesigned, originalContainer);
            originalContainer.classList.add("cleo-delivery-original-hidden");

            methods.forEach(function (method) {
                method.radio.addEventListener("change", function () {
                    syncDeliverySelection(redesigned, methods);

                    if (method.type === "pickup" && method.radio.checked) {
                        applyDefaultPickup(method, redesigned);
                    }
                });
            });

            const selectedPickup = methods.find(function (method) {
                return method.type === "pickup" && method.radio.checked;
            });

            if (selectedPickup) {
                applyDefaultPickup(selectedPickup, redesigned);
            }
        } finally {
            buildingDeliverySection = false;
        }
    }

    function watchDeliveryChanges() {
        if (deliveryObserver || !isCheckoutPage()) {
            return;
        }

        deliveryObserver = new MutationObserver(function () {
            window.clearTimeout(deliveryInitTimer);
            deliveryInitTimer = window.setTimeout(function () {
                addDeleteLinksToAddressCards();
                improveDeliverySection();
            }, 350);
        });

        deliveryObserver.observe(document.body, {
            childList: true,
            subtree: true,
        });
    }

    function initCheckoutAddressImprovements() {
        addDeleteLinksToAddressCards();
        improveDeliverySection();
        watchDeliveryChanges();

        setTimeout(addDeleteLinksToAddressCards, 600);
        setTimeout(improveDeliverySection, 600);
        setTimeout(improveDeliverySection, 1300);
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", initCheckoutAddressImprovements);
    } else {
        initCheckoutAddressImprovements();
    }
})();

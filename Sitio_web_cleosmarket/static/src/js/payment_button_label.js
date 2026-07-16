/** @odoo-module **/

(function () {
    "use strict";

    // Códigos técnicos de payment.method (ver payment_cobro_entrega/const.py y
    // website_sale_collect/data/payment_method_data.xml).
    const COD_METHOD_CODE = "cleo_cod";
    const ON_SITE_METHOD_CODE = "pay_on_site";

    const LABEL_BY_METHOD_CODE = {
        [COD_METHOD_CODE]: "Enviar mi pedido",
        [ON_SITE_METHOD_CODE]: "Preparar mi pedido",
    };

    const DEFAULT_LABEL = "Pagar Ahora";

    function isPaymentPage() {
        return window.location.pathname.includes("/shop/payment");
    }

    function normalizeText(value) {
        return String(value || "").replace(/\s+/g, " ").trim().toLowerCase();
    }

    function getSubmitButton() {
        return document.querySelector('button[name="o_payment_submit_button"]');
    }

    function getRadioLabelText(radio) {
        if (!radio || !radio.id) {
            return "";
        }
        const label = document.querySelector(`label[for="${radio.id}"]`);
        return normalizeText(label && label.textContent);
    }

    function labelForRadio(radio) {
        if (!radio) {
            return DEFAULT_LABEL;
        }

        const methodCode = radio.dataset.paymentMethodCode || "";
        if (LABEL_BY_METHOD_CODE[methodCode]) {
            return LABEL_BY_METHOD_CODE[methodCode];
        }

        // Respaldo por texto visible, por si el código técnico no coincide
        // (p. ej. método reconfigurado en el backend).
        const text = getRadioLabelText(radio);
        if (text.includes("cobro contra entrega")) {
            return LABEL_BY_METHOD_CODE[COD_METHOD_CODE];
        }
        if (text.includes("pagar en la tienda") || text.includes("pagar en el sitio")) {
            return LABEL_BY_METHOD_CODE[ON_SITE_METHOD_CODE];
        }

        return DEFAULT_LABEL;
    }

    function updateButtonLabel() {
        const button = getSubmitButton();
        if (!button) {
            return;
        }

        const checkedRadio = document.querySelector('input[name="o_payment_radio"]:checked');
        button.textContent = labelForRadio(checkedRadio);
    }

    function onRadioChange(event) {
        const target = event.target;
        if (target && target.matches && target.matches('input[name="o_payment_radio"]')) {
            updateButtonLabel();
        }
    }

    function init() {
        if (!isPaymentPage()) {
            return;
        }

        document.addEventListener("change", onRadioChange, true);
        document.addEventListener("click", onRadioChange, true);

        updateButtonLabel();
        // El formulario de pago puede terminar de montar sus opciones
        // (tokens/proveedores) un instante después del primer render.
        setTimeout(updateButtonLabel, 300);
        setTimeout(updateButtonLabel, 900);
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }
})();

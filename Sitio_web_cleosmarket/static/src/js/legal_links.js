/** @odoo-module **/

/*
 * Ajusta automáticamente los enlaces de términos y condiciones del checkout/pago
 * para que apunten a la página legal de Super Tienda Cleo.
 */
(function () {
    "use strict";

    function normalizeText(value) {
        return (value || "")
            .toLowerCase()
            .normalize("NFD")
            .replace(/[\u0300-\u036f]/g, "");
    }

    function updateTermsLinks() {
        const anchors = document.querySelectorAll("a");

        anchors.forEach(function (anchor) {
            const text = normalizeText(anchor.textContent);
            const href = normalizeText(anchor.getAttribute("href") || "");

            const looksLikeTermsLink =
                (text.includes("terminos") && text.includes("condiciones")) ||
                (text.includes("terms") && text.includes("conditions")) ||
                href.includes("/terms") ||
                href.includes("terms-and-conditions") ||
                href.includes("terminos-y-condiciones");

            if (looksLikeTermsLink) {
                anchor.setAttribute("href", "/terminos-y-condiciones");
                anchor.setAttribute("target", "_blank");
                anchor.setAttribute("rel", "noopener");
            }
        });
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", updateTermsLinks);
    } else {
        updateTermsLinks();
    }

    window.addEventListener("load", updateTermsLinks);
    setTimeout(updateTermsLinks, 500);
})();

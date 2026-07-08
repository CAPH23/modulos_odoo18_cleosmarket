/** @odoo-module **/

(function () {
    "use strict";

    function postJsonRpc(url, params) {
        return fetch(url, {
            method: "POST",
            credentials: "same-origin",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify({
                jsonrpc: "2.0",
                method: "call",
                params: params || {},
            }),
        });
    }

    function initCleoTermsAcceptance() {
        const checkbox = document.querySelector("#website_sale_tc_checkbox");

        if (!checkbox || checkbox.dataset.cleoTermsReady === "1") {
            return;
        }

        checkbox.dataset.cleoTermsReady = "1";

        const termsLinks = document.querySelectorAll(
            "a[href='/terms'], a[href='/terminos-y-condiciones']"
        );

        termsLinks.forEach(function (link) {
            if (link.textContent.toLowerCase().includes("términos")) {
                link.setAttribute("href", "/terminos-y-condiciones");
                link.setAttribute("target", "_blank");
            }
        });

        checkbox.addEventListener("change", function () {
            if (!checkbox.checked) {
                return;
            }

            postJsonRpc("/cleo/terms/accept", {
                accepted: true,
            }).catch(function () {
                console.warn("No se pudo guardar la aceptación de términos.");
            });
        });
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", initCleoTermsAcceptance);
    } else {
        initCleoTermsAcceptance();
    }

    window.addEventListener("load", initCleoTermsAcceptance);
})();

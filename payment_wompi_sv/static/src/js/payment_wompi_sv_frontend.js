/** @odoo-module **/

/*
 * Wompi El Salvador - Mejora visual del logo en /shop/payment.
 *
 * Esta lógica NO toca métodos globales ni cambia imágenes de otros proveedores:
 * 1) Consulta el ID real del método propio `wompi_sv_card`.
 * 2) Busca únicamente la imagen cuyo src pertenece a ese payment.method.
 * 3) Reemplaza ese thumbnail por el PNG original incluido en este módulo.
 */
(function () {
    "use strict";

    const INFO_URL = "/payment_wompi_sv/payment_method_logo_info";
    const LOGO_CLASS = "cleo-wompi-payment-method-logo";

    async function getWompiLogoInfo() {
        const response = await fetch(INFO_URL, {
            method: "GET",
            credentials: "same-origin",
            cache: "no-store",
        });
        if (!response.ok) {
            return null;
        }
        return response.json();
    }

    function applyLogo(info) {
        if (!info || !info.payment_method_id || !info.logo_url) {
            return;
        }
        const methodId = String(info.payment_method_id);
        const selectors = [
            `img[src*="/web/image/payment.method/${methodId}/"]`,
            `img[src*="/web/image/payment.method/${methodId}-"]`,
            `img[src*="model=payment.method"][src*="id=${methodId}"]`,
        ];
        document.querySelectorAll(selectors.join(",")).forEach((img) => {
            img.src = `${info.logo_url}?v=hd-2`;
            img.removeAttribute("srcset");
            img.classList.add(LOGO_CLASS);
            img.alt = "Tarjetas aceptadas por Wompi";
            img.loading = "eager";
        });
    }

    async function run() {
        if (!window.location.pathname.includes("/shop/payment")) {
            return;
        }
        try {
            const info = await getWompiLogoInfo();
            applyLogo(info);
            // Odoo puede re-renderizar opciones de pago después de cargar la página.
            setTimeout(() => applyLogo(info), 300);
            setTimeout(() => applyLogo(info), 1000);
        } catch (error) {
            // Silencioso para no afectar el checkout si algo externo falla.
            console.warn("Wompi logo HD no pudo aplicarse", error);
        }
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", run);
    } else {
        run();
    }
})();

/** @odoo-module **/

/*
 * Super Tienda Cleo
 * - Control del menú activo del encabezado.
 * - Carrusel manual de categorías de la Home.
 */

(function () {
    "use strict";

    function setActiveMenu() {
        const currentPath = window.location.pathname || "/";
        const menuLinks = document.querySelectorAll(".cleo-menu__links .nav-link");

        if (!menuLinks.length) {
            return;
        }

        menuLinks.forEach(function (link) {
            const href = link.getAttribute("href") || "";

            link.classList.remove("active");

            if ((currentPath === "/" || currentPath === "/-1" || currentPath === "/-2") && href === "/") {
                link.classList.add("active");
            }

            if (currentPath.startsWith("/shop") && href === "/shop") {
                link.classList.add("active");
            }

            if (currentPath.startsWith("/sobre-nosotros") && href === "/sobre-nosotros") {
                link.classList.add("active");
            }

            if (currentPath.startsWith("/contactus") && href === "/contactus") {
                link.classList.add("active");
            }
        });
    }

    function initCategoryCarousel() {
        const carousel = document.querySelector('[data-cleo-carousel="categories"]');
        if (!carousel) {
            return;
        }

        const viewport = carousel.querySelector('[data-cleo-carousel-viewport="categories"]');
        const prevBtn = carousel.querySelector('[data-cleo-carousel-prev="categories"]');
        const nextBtn = carousel.querySelector('[data-cleo-carousel-next="categories"]');

        if (!viewport || !prevBtn || !nextBtn) {
            return;
        }

        function getScrollStep() {
            const firstCard = viewport.querySelector(".cleo-category-tile");
            if (!firstCard) {
                return viewport.clientWidth;
            }

            const cardStyle = window.getComputedStyle(firstCard);
            const cardWidth = firstCard.getBoundingClientRect().width;
            const gap = parseFloat(cardStyle.marginRight || "0") || 18;
            const visibleCards = Math.max(1, Math.floor(viewport.clientWidth / (cardWidth + gap)));

            return visibleCards * (cardWidth + gap);
        }

        function updateButtons() {
            const maxScroll = viewport.scrollWidth - viewport.clientWidth;
            const current = viewport.scrollLeft;

            prevBtn.classList.toggle("is-disabled", current <= 2);
            nextBtn.classList.toggle("is-disabled", current >= maxScroll - 2);
        }

        prevBtn.addEventListener("click", function () {
            viewport.scrollBy({ left: -getScrollStep(), behavior: "smooth" });
        });

        nextBtn.addEventListener("click", function () {
            viewport.scrollBy({ left: getScrollStep(), behavior: "smooth" });
        });

        viewport.addEventListener("scroll", updateButtons, { passive: true });
        window.addEventListener("resize", updateButtons);

        updateButtons();
        setTimeout(updateButtons, 300);
    }

    function initCleoWebsite() {
        setActiveMenu();
        initCategoryCarousel();
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", initCleoWebsite);
    } else {
        initCleoWebsite();
    }

    setTimeout(initCleoWebsite, 500);
})();

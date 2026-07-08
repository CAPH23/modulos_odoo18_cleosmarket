/** @odoo-module **/

/*
 * Carrusel dinámico de productos Lácteos y Huevos.
 * - Botones anterior/siguiente.
 * - Avance automático cada 5 segundos.
 * - Al llegar al final vuelve al primer producto.
 * - Compatible con carga tardía de assets en Odoo.
 */

(function () {
    "use strict";

    function initCleoDairyCarousel() {
        const carousels = document.querySelectorAll("[data-cleo-dairy-carousel='1']");

        carousels.forEach(function (carousel) {
            if (carousel.dataset.cleoCarouselReady === "1") {
                return;
            }

            carousel.dataset.cleoCarouselReady = "1";

            const viewport = carousel.querySelector(".cleo-dairy-carousel__viewport");
            const track = carousel.querySelector(".cleo-dairy-carousel__track");
            const prevButton = carousel.querySelector(".cleo-dairy-carousel__btn--prev");
            const nextButton = carousel.querySelector(".cleo-dairy-carousel__btn--next");

            if (!viewport || !track) {
                console.warn("Cleo Dairy Carousel: faltan viewport o track.");
                return;
            }

            function getStep() {
                const firstCard = track.querySelector(".cleo-dairy-product-card");

                if (!firstCard) {
                    return 0;
                }

                const cardWidth = firstCard.getBoundingClientRect().width;
                const trackStyles = window.getComputedStyle(track);
                const gap = parseFloat(trackStyles.columnGap || trackStyles.gap || "0");

                return cardWidth + gap;
            }

            function getMaxScroll() {
                return Math.max(0, viewport.scrollWidth - viewport.clientWidth);
            }

            function goNext() {
                const step = getStep();
                const maxScroll = getMaxScroll();

                if (!step || maxScroll <= 0) {
                    return;
                }

                const isAtEnd = viewport.scrollLeft >= maxScroll - 10;

                if (isAtEnd) {
                    viewport.scrollTo({
                        left: 0,
                        behavior: "smooth",
                    });
                } else {
                    viewport.scrollBy({
                        left: step,
                        behavior: "smooth",
                    });
                }
            }

            function goPrev() {
                const step = getStep();
                const maxScroll = getMaxScroll();

                if (!step || maxScroll <= 0) {
                    return;
                }

                const isAtStart = viewport.scrollLeft <= 10;

                if (isAtStart) {
                    viewport.scrollTo({
                        left: maxScroll,
                        behavior: "smooth",
                    });
                } else {
                    viewport.scrollBy({
                        left: -step,
                        behavior: "smooth",
                    });
                }
            }

            if (nextButton) {
                nextButton.addEventListener("click", function (ev) {
                    ev.preventDefault();
                    goNext();
                });
            }

            if (prevButton) {
                prevButton.addEventListener("click", function (ev) {
                    ev.preventDefault();
                    goPrev();
                });
            }

            let autoplay = window.setInterval(goNext, 5000);

            carousel.addEventListener("mouseenter", function () {
                window.clearInterval(autoplay);
            });

            carousel.addEventListener("mouseleave", function () {
                window.clearInterval(autoplay);
                autoplay = window.setInterval(goNext, 5000);
            });

            carousel.addEventListener(
                "touchstart",
                function () {
                    window.clearInterval(autoplay);
                },
                { passive: true }
            );

            carousel.addEventListener(
                "touchend",
                function () {
                    window.clearInterval(autoplay);
                    autoplay = window.setInterval(goNext, 5000);
                },
                { passive: true }
            );
        });
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", initCleoDairyCarousel);
    } else {
        initCleoDairyCarousel();
    }

    window.addEventListener("load", initCleoDairyCarousel);
})();

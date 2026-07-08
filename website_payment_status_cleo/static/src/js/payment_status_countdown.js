/** Super Tienda Cleo - contador de redirección en /payment/status */
(function () {
    'use strict';

    function initCleoPaymentCountdown() {
        const pages = document.querySelectorAll('.cleo-payment-status-page[data-cleo-countdown]');
        pages.forEach((page) => {
            if (page.dataset.cleoCountdownStarted === '1') {
                return;
            }
            page.dataset.cleoCountdownStarted = '1';

            const numberEl = page.querySelector('.cleo-countdown-number');
            const secondsAttr = parseInt(page.dataset.cleoCountdown || '5', 10);
            let seconds = Number.isFinite(secondsAttr) && secondsAttr >= 0 ? secondsAttr : 5;
            const redirectUrl = page.dataset.cleoRedirectUrl || '/shop/confirmation';

            if (numberEl) {
                numberEl.textContent = String(seconds);
            }

            const interval = window.setInterval(() => {
                seconds -= 1;
                if (numberEl) {
                    numberEl.textContent = String(Math.max(seconds, 0));
                }
                if (seconds <= 0) {
                    window.clearInterval(interval);
                    window.location.href = redirectUrl;
                }
            }, 1000);
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initCleoPaymentCountdown);
    } else {
        initCleoPaymentCountdown();
    }
})();

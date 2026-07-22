/* Boxful - refresco de la barra de seguimiento del portal cada 30 segundos. */
(function () {
    'use strict';

    var POLL_MS = 30000;

    function updateCard(card, data) {
        if (!data || !Array.isArray(data.steps)) {
            return;
        }
        data.steps.forEach(function (step) {
            var el = card.querySelector('[data-step-key="' + step.key + '"]');
            if (!el) {
                return;
            }
            var wasDone = el.classList.contains('cleo-bf-done');
            el.classList.remove('cleo-bf-done', 'cleo-bf-active', 'cleo-bf-pending');
            el.classList.add('cleo-bf-' + step.state);
            var icon = el.querySelector('.cleo-bf-icon i');
            if (icon) {
                var base = icon.getAttribute('data-step-icon') || 'fa-circle';
                icon.className = 'fa ' + (step.state === 'done' ? 'fa-check' : base);
            }
            var status = el.querySelector('.cleo-bf-step-status');
            if (status) {
                status.textContent = step.label;
            }
            if (step.state === 'done' && !wasDone) {
                var wrap = el.querySelector('.cleo-bf-icon');
                if (wrap) {
                    wrap.style.animation = 'none';
                    void wrap.offsetWidth;
                    wrap.style.animation = '';
                }
            }
            var line = card.querySelector('[data-step-line="' + step.key + '"]');
            if (line) {
                line.classList.toggle('cleo-bf-line-done', step.state === 'done');
            }
        });
        if (data.finished || data.cancelled) {
            card.setAttribute('data-finished', '1');
        }
    }

    function startPolling(card) {
        var orderId = card.getAttribute('data-order-id');
        var token = card.getAttribute('data-access-token');
        if (!orderId || card.getAttribute('data-finished') === '1') {
            return;
        }
        var url = '/my/orders/' + orderId + '/goboxful_status' +
            (token ? '?access_token=' + encodeURIComponent(token) : '');
        var timer = window.setInterval(function () {
            if (document.hidden || card.getAttribute('data-finished') === '1') {
                if (card.getAttribute('data-finished') === '1') {
                    window.clearInterval(timer);
                }
                return;
            }
            window.fetch(url, {credentials: 'same-origin'})
                .then(function (response) { return response.ok ? response.json() : null; })
                .then(function (data) { updateCard(card, data); })
                .catch(function () { /* reintenta en el siguiente ciclo */ });
        }, POLL_MS);
    }

    function init() {
        document.querySelectorAll('.cleo-bf-card[data-order-id]').forEach(startPolling);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();

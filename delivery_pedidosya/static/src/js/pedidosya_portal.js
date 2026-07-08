/* PedidosYa - refresco en vivo de la barra de seguimiento (/my/orders/<id>)
 *
 * Sondea el endpoint /my/orders/<id>/pedidosya_status cada 30 s y actualiza
 * las clases/íconos de los pasos. Cuando un paso pasa a "done" se reinicia la
 * animación pop para que el usuario vea el cambio en vivo. Se detiene cuando
 * el pedido finaliza/cancela o la pestaña queda oculta.
 */
(function () {
    'use strict';

    var POLL_MS = 30000;

    function updateCard(card, data) {
        if (!data || !data.steps) {
            return;
        }
        data.steps.forEach(function (step) {
            var el = card.querySelector('[data-step-key="' + step.key + '"]');
            if (!el) {
                return;
            }
            var wasDone = el.classList.contains('cleo-py-done');
            el.classList.remove('cleo-py-done', 'cleo-py-active', 'cleo-py-pending');
            el.classList.add('cleo-py-' + step.state);

            var icon = el.querySelector('.cleo-py-icon i');
            if (icon) {
                var base = icon.getAttribute('data-step-icon') || 'fa-circle';
                icon.className = 'fa ' + (step.state === 'done' ? 'fa-check' : base);
            }
            var status = el.querySelector('.cleo-py-step-status');
            if (status) {
                status.textContent = step.label;
            }
            // reiniciar animación pop cuando el paso ACABA de completarse
            if (step.state === 'done' && !wasDone) {
                var iconWrap = el.querySelector('.cleo-py-icon');
                if (iconWrap) {
                    iconWrap.style.animation = 'none';
                    void iconWrap.offsetWidth; /* reflow para reiniciar */
                    iconWrap.style.animation = '';
                }
            }
            // conector previo al paso
            var line = card.querySelector('[data-step-line="' + step.key + '"]');
            if (line) {
                line.classList.toggle('cleo-py-line-done', step.state === 'done');
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
        var url = '/my/orders/' + orderId + '/pedidosya_status' +
            (token ? '?access_token=' + encodeURIComponent(token) : '');

        var timer = setInterval(function () {
            if (document.hidden) {
                return;
            }
            if (card.getAttribute('data-finished') === '1') {
                clearInterval(timer);
                return;
            }
            fetch(url, { credentials: 'same-origin' })
                .then(function (resp) { return resp.ok ? resp.json() : null; })
                .then(function (data) { updateCard(card, data); })
                .catch(function () { /* silencioso: reintenta en el próximo tick */ });
        }, POLL_MS);
    }

    function init() {
        document.querySelectorAll('.cleo-py-card[data-order-id]').forEach(startPolling);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();

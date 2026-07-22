/** @odoo-module **/

import publicWidget from '@web/legacy/js/public/public_widget';

// Sitio_web_cleosmarket reconstruye la lista de métodos de entrega en tarjetas
// ".cleo-delivery-option" y oculta la lista original de Odoo (donde vive
// ".o_goboxful_checkout_details"). Guardamos el último rateData por dm.id para
// poder reflejarlo también en la tarjeta visible en cuanto exista.
const goboxfulRateCache = new Map();
let goboxfulCardObserver = null;

function buildGoboxfulDetailsContent(rateData) {
    const header = document.createElement('div');
    header.className = 'o_goboxful_checkout_header';
    if (rateData.courier_logo) {
        const img = document.createElement('img');
        img.src = rateData.courier_logo;
        img.alt = rateData.courier_name;
        img.className = 'o_goboxful_courier_logo';
        header.appendChild(img);
    }
    const name = document.createElement('span');
    name.className = 'o_goboxful_courier_name';
    name.textContent = rateData.courier_name;
    header.appendChild(name);

    const rows = [];
    if (rateData.pickup_at) {
        rows.push(['Recolección estimada', rateData.pickup_at]);
    }
    if (rateData.estimated_delivery) {
        rows.push(['Entrega estimada', rateData.estimated_delivery]);
    }
    if (rateData.max_weight) {
        const unit = rateData.max_weight_unit === 'kg' ? 'kg' : 'lb';
        rows.push(['Peso máximo del courier', `${rateData.max_weight} ${unit}`]);
    }
    if (rateData.delivery_type) {
        const label = rateData.delivery_type === 'same-day' ? 'Mismo día' : rateData.delivery_type;
        rows.push(['Tipo de entrega', label]);
    }

    const list = document.createElement('ul');
    list.className = 'o_goboxful_checkout_list';
    rows.forEach(([label, value]) => {
        const li = document.createElement('li');
        const b = document.createElement('b');
        b.textContent = `${label}: `;
        li.appendChild(b);
        li.appendChild(document.createTextNode(value));
        list.appendChild(li);
    });

    return [header, list];
}

function renderGoboxfulDetails(box, rateData) {
    if (!box) {
        return;
    }
    box.replaceChildren();
    if (!rateData || !rateData.success || !rateData.courier_name) {
        box.classList.add('d-none');
        return;
    }
    buildGoboxfulDetailsContent(rateData).forEach((node) => box.appendChild(node));
    box.classList.remove('d-none');
}

function syncGoboxfulCard(dmId) {
    const option = document.querySelector(
        `.cleo-delivery-option[data-carrier-id="${dmId}"]`
    );
    if (!option) {
        return;
    }
    const main = option.querySelector('.cleo-delivery-main') || option;
    let box = main.querySelector('.o_goboxful_checkout_details');
    const rateData = goboxfulRateCache.get(dmId);
    const signature = JSON.stringify(rateData && rateData.success ? rateData : null);
    if (box && box.dataset.rateSignature === signature) {
        return; // Ya refleja este rateData: no tocar el DOM (evita bucles del observer).
    }
    if (!rateData || !rateData.success || !rateData.courier_name) {
        if (box) {
            box.remove();
        }
        return;
    }
    if (!box) {
        box = document.createElement('div');
        box.className = 'o_goboxful_checkout_details mt-2 small';
        main.appendChild(box);
    }
    box.dataset.rateSignature = signature;
    renderGoboxfulDetails(box, rateData);
}

function watchGoboxfulCards() {
    if (goboxfulCardObserver) {
        return;
    }
    let debounceTimer = null;
    goboxfulCardObserver = new MutationObserver(() => {
        window.clearTimeout(debounceTimer);
        debounceTimer = window.setTimeout(() => {
            goboxfulRateCache.forEach((rateData, dmId) => syncGoboxfulCard(dmId));
        }, 150);
    });
    goboxfulCardObserver.observe(document.body, { childList: true, subtree: true });
}

publicWidget.registry.WebsiteSaleCheckout.include({

    /**
     * @override
     */
    async _updateDeliveryMethod(radio) {
        await this._super(...arguments);
        if (radio.dataset.deliveryType === 'goboxful') {
            const rateData = await this._getDeliveryRate(radio);
            this._updateGoboxfulDetails(radio, rateData);
        }
    },

    /**
     * @override
     */
    _updateAmountBadge(radio, rateData) {
        this._super(...arguments);
        if (radio.dataset.deliveryType === 'goboxful') {
            this._updateGoboxfulDetails(radio, rateData);
        }
    },

    /**
     * Rellena la tarjeta de Boxful con el courier elegido, fechas y peso máximo.
     *
     * Se refleja tanto en la lista original de Odoo (oculta cuando
     * Sitio_web_cleosmarket rediseña el checkout) como en la tarjeta
     * ".cleo-delivery-option" que ve realmente el cliente.
     *
     * @private
     * @param {HTMLInputElement} radio
     * @param {Object} rateData
     */
    _updateGoboxfulDetails(radio, rateData) {
        const container = this._getDeliveryMethodContainer(radio);
        const box = container && container.querySelector('.o_goboxful_checkout_details');
        renderGoboxfulDetails(box, rateData);

        const dmId = radio.dataset.dmId;
        if (dmId) {
            goboxfulRateCache.set(dmId, rateData);
            watchGoboxfulCards();
            syncGoboxfulCard(dmId);
        }
    },

});

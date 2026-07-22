/** @odoo-module **/

import { rpc } from '@web/core/network/rpc';
import publicWidget from '@web/legacy/js/public/public_widget';

// Sitio_web_cleosmarket reconstruye la lista de métodos de entrega en tarjetas
// ".cleo-delivery-option" y oculta la lista original de Odoo (donde vive
// ".o_goboxful_checkout_details"). Guardamos el último rateData por dm.id para
// poder reflejarlo también en la tarjeta visible en cuanto exista.
const goboxfulRateCache = new Map();
let goboxfulCardObserver = null;

const GOBOXFUL_LOGO_URL = '/delivery_goboxful/static/src/img/goboxful_logo.svg';

function courierInitial(name) {
    return (String(name || '?').trim().charAt(0) || '?').toUpperCase();
}

function applyGoboxfulIcon(dmId) {
    const option = document.querySelector(`.cleo-delivery-option[data-carrier-id="${dmId}"]`);
    const badge = option && option.querySelector('.cleo-delivery-icon-badge');
    if (!badge || badge.dataset.goboxfulIconApplied === '1') {
        return;
    }
    badge.replaceChildren();
    const img = document.createElement('img');
    img.src = GOBOXFUL_LOGO_URL;
    img.alt = 'Boxful';
    img.className = 'o_goboxful_carrier_icon';
    badge.appendChild(img);
    badge.dataset.goboxfulIconApplied = '1';
}

function setSingleSelected(list, selectedRow) {
    list.querySelectorAll('.o_goboxful_courier_row').forEach((row) => {
        const checkbox = row.querySelector('.o_goboxful_courier_checkbox');
        const isSelected = row === selectedRow;
        row.classList.toggle('is-selected', isSelected);
        if (checkbox) {
            checkbox.checked = isSelected;
        }
    });
}

async function selectGoboxfulCourier(dmId, courierExternalId, list, row) {
    if (list.dataset.loading === '1') {
        return;
    }
    list.dataset.loading = '1';
    list.classList.add('is-loading');
    try {
        const result = await rpc('/goboxful/select_courier', {
            dm_id: dmId,
            courier_external_id: courierExternalId,
        });
        if (!result || result.success === false) {
            return;
        }
        setSingleSelected(list, row);

        const option = document.querySelector(`.cleo-delivery-option[data-carrier-id="${dmId}"]`);
        if (option) {
            const priceBadge = option.querySelector('.cleo-delivery-price');
            if (priceBadge && result.amount_delivery) {
                priceBadge.innerHTML = result.amount_delivery;
            }
        }

        const amountDelivery = document.querySelector('#order_delivery .monetary_field');
        const amountUntaxed = document.querySelector('#order_total_untaxed .monetary_field');
        const amountTax = document.querySelector('#order_total_taxes .monetary_field');
        const amountTotal = document.querySelectorAll(
            '#order_total .monetary_field, #amount_total_summary.monetary_field'
        );
        if (amountDelivery && result.amount_delivery) {
            amountDelivery.innerHTML = result.amount_delivery;
        }
        if (amountUntaxed && result.amount_untaxed) {
            amountUntaxed.innerHTML = result.amount_untaxed;
        }
        if (amountTax && result.amount_tax) {
            amountTax.innerHTML = result.amount_tax;
        }
        if (result.amount_total) {
            amountTotal.forEach((total) => { total.innerHTML = result.amount_total; });
        }

        const cached = goboxfulRateCache.get(dmId);
        if (cached && result.options) {
            cached.options = result.options;
            goboxfulRateCache.set(dmId, cached);
        }
    } catch (error) {
        console.warn('No se pudo cambiar el courier Boxful:', error);
    } finally {
        list.dataset.loading = '0';
        list.classList.remove('is-loading');
    }
}

function buildCourierRow(option, dmId, list) {
    const row = document.createElement('label');
    row.className = 'o_goboxful_courier_row';
    row.dataset.courierId = option.courier_external_id;
    if (option.selected) {
        row.classList.add('is-selected');
    }

    const checkbox = document.createElement('input');
    checkbox.type = 'checkbox';
    checkbox.className = 'o_goboxful_courier_checkbox';
    checkbox.checked = Boolean(option.selected);
    checkbox.setAttribute('aria-label', option.courier_name);
    row.appendChild(checkbox);

    if (option.courier_logo) {
        const img = document.createElement('img');
        img.src = option.courier_logo;
        img.alt = option.courier_name;
        img.className = 'o_goboxful_courier_logo';
        row.appendChild(img);
    } else {
        const avatar = document.createElement('span');
        avatar.className = 'o_goboxful_courier_logo o_goboxful_courier_avatar';
        avatar.textContent = courierInitial(option.courier_name);
        row.appendChild(avatar);
    }

    const info = document.createElement('span');
    info.className = 'o_goboxful_courier_info';

    const name = document.createElement('span');
    name.className = 'o_goboxful_courier_name';
    name.textContent = option.courier_name || '';
    info.appendChild(name);

    const meta = document.createElement('span');
    meta.className = 'o_goboxful_courier_meta';
    const metaParts = [];
    if (option.pickup_at) {
        metaParts.push(`<b>Recolección: </b>${option.pickup_at}`);
    }
    if (option.estimated_delivery) {
        metaParts.push(`<b>Entrega: </b>${option.estimated_delivery}`);
    }
    if (option.max_weight) {
        const unit = option.max_weight_unit === 'kg' ? 'kg' : 'lb';
        metaParts.push(`<b>Peso máximo: </b>${option.max_weight} ${unit}`);
    }
    if (option.price_label) {
        metaParts.push(`<b>Costo: </b>${option.price_label}`);
    }
    meta.innerHTML = metaParts.join(' &nbsp; ');
    info.appendChild(meta);

    row.appendChild(info);

    checkbox.addEventListener('click', (event) => {
        // Evita el doble disparo del "change" del label + del propio checkbox.
        event.stopPropagation();
    });
    checkbox.addEventListener('change', async () => {
        if (!checkbox.checked) {
            // Solo puede haber un courier seleccionado: no se permite
            // desmarcar sin elegir otro en su lugar.
            checkbox.checked = true;
            return;
        }
        await selectGoboxfulCourier(dmId, option.courier_external_id, list, row);
    });

    return row;
}

function buildGoboxfulDetailsContent(rateData, dmId) {
    const list = document.createElement('div');
    list.className = 'o_goboxful_courier_list';
    list.setAttribute('role', 'group');
    list.setAttribute('aria-label', 'Elige tu courier');

    const options = rateData.options || [];
    options.forEach((option) => {
        list.appendChild(buildCourierRow(option, dmId, list));
    });

    return [list];
}

function renderGoboxfulDetails(box, rateData, dmId) {
    if (!box) {
        return;
    }
    box.replaceChildren();
    if (!rateData || !rateData.success || !(rateData.options || []).length) {
        box.classList.add('d-none');
        return;
    }
    buildGoboxfulDetailsContent(rateData, dmId).forEach((node) => box.appendChild(node));
    box.classList.remove('d-none');
}

function syncGoboxfulCard(dmId) {
    const option = document.querySelector(
        `.cleo-delivery-option[data-carrier-id="${dmId}"]`
    );
    if (!option) {
        return;
    }
    applyGoboxfulIcon(dmId);
    // La caja de couriers se cuelga directamente de ".cleo-delivery-option" (no de
    // ".cleo-delivery-main") para poder ocupar su propia fila del grid de la tarjeta,
    // abarcando desde la columna del título hasta la del precio (ver
    // "grid-column: 2 / -1" en goboxful_checkout.scss). Anidarla dentro de
    // ".cleo-delivery-main" la limitaba al ancho de esa única columna (título/
    // descripción), sin poder llegar nunca al borde derecho de la tarjeta.
    let box = option.querySelector(':scope > .o_goboxful_checkout_details');
    const rateData = goboxfulRateCache.get(dmId);
    const signature = JSON.stringify(rateData && rateData.success ? rateData : null);
    if (box && box.dataset.rateSignature === signature) {
        return; // Ya refleja este rateData: no tocar el DOM (evita bucles del observer).
    }
    if (!rateData || !rateData.success || !(rateData.options || []).length) {
        if (box) {
            box.remove();
        }
        return;
    }
    if (!box) {
        box = document.createElement('div');
        box.className = 'o_goboxful_checkout_details mt-2 small';
        option.appendChild(box);
    }
    box.dataset.rateSignature = signature;
    renderGoboxfulDetails(box, rateData, dmId);
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
     * Rellena la tarjeta de Boxful con la lista completa de couriers devueltos
     * por Boxful (checkbox, logo, fechas, peso máximo y tipo de entrega),
     * dejando preseleccionado el que corresponda según el criterio configurado.
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
        const dmId = radio.dataset.dmId;
        const container = this._getDeliveryMethodContainer(radio);
        const box = container && container.querySelector('.o_goboxful_checkout_details');
        renderGoboxfulDetails(box, rateData, dmId);

        if (dmId) {
            goboxfulRateCache.set(dmId, rateData);
            watchGoboxfulCards();
            syncGoboxfulCard(dmId);
        }
    },

});

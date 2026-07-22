# -*- coding: utf-8 -*-
from odoo.http import Controller, request, route

from odoo.addons.Sitio_web_cleosmarket.controllers.checkout_flow import CleosmarketCheckoutFlow


class GoBoxfulCheckoutFlow(CleosmarketCheckoutFlow):
    """No lista Boxful ni siquiera como opción deshabilitada para congelados."""

    def _cleo_hidden_home_delivery_methods(self, order_sudo, available_dms):
        hidden = super()._cleo_hidden_home_delivery_methods(order_sudo, available_dms)
        if order_sudo and order_sudo._goboxful_has_blocked_products():
            hidden = hidden.filtered(lambda carrier: carrier.delivery_type != "goboxful")
        return hidden


class GoBoxfulCourierSelectionController(Controller):
    """Permite al cliente elegir, entre los couriers que Boxful devolvió para su
    dirección, cuál usar en vez del preseleccionado automáticamente."""

    @route("/goboxful/select_courier", type="json", auth="public", website=True)
    def goboxful_select_courier(self, dm_id=None, courier_external_id=None, **kwargs):
        order_sudo = request.website.sale_get_order()
        if not order_sudo or not dm_id or not courier_external_id:
            return {"success": False}

        try:
            dm_id = int(dm_id)
        except (TypeError, ValueError):
            return {"success": False}

        carrier_sudo = request.env["delivery.carrier"].sudo().browse(dm_id).exists()
        if (
            not carrier_sudo
            or carrier_sudo.delivery_type != "goboxful"
            or dm_id not in order_sudo._get_delivery_methods().ids
        ):
            return {"success": False}

        order_sudo.sudo().goboxful_selected_courier_id = courier_external_id
        rate = carrier_sudo.rate_shipment(order_sudo)
        if rate.get("success"):
            order_sudo._set_delivery_method(carrier_sudo, rate=rate)

        Monetary = request.env["ir.qweb.field.monetary"]
        currency = order_sudo.currency_id
        result = dict(rate)
        result.update({
            "amount_delivery": Monetary.value_to_html(
                order_sudo.amount_delivery, {"display_currency": currency}
            ),
            "amount_untaxed": Monetary.value_to_html(
                order_sudo.amount_untaxed, {"display_currency": currency}
            ),
            "amount_tax": Monetary.value_to_html(
                order_sudo.amount_tax, {"display_currency": currency}
            ),
            "amount_total": Monetary.value_to_html(
                order_sudo.amount_total, {"display_currency": currency}
            ),
            "is_free_delivery": not bool(order_sudo.amount_delivery),
        })
        return result

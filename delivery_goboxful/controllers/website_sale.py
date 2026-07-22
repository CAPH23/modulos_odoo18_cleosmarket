# -*- coding: utf-8 -*-
from odoo.addons.Sitio_web_cleosmarket.controllers.checkout_flow import CleosmarketCheckoutFlow


class GoBoxfulCheckoutFlow(CleosmarketCheckoutFlow):
    """No lista Boxful ni siquiera como opción deshabilitada para congelados."""

    def _cleo_hidden_home_delivery_methods(self, order_sudo, available_dms):
        hidden = super()._cleo_hidden_home_delivery_methods(order_sudo, available_dms)
        if order_sudo and order_sudo._goboxful_has_blocked_products():
            hidden = hidden.filtered(lambda carrier: carrier.delivery_type != "goboxful")
        return hidden

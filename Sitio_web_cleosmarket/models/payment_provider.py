# -*- coding: utf-8 -*-

from odoo import models

# xmlid del proveedor "Pagar en la Tienda" (payment_provider_on_site de website_sale_collect).
PAY_ON_SITE_XMLID = "website_sale_collect.payment_provider_on_site"
# Proveedores permitidos cuando el pedido usa "Entrega en tienda" (delivery_type = in_store).
IN_STORE_PROVIDER_XMLIDS = (
    PAY_ON_SITE_XMLID,
    "payment_wompi_sv.payment_provider_wompi_sv",
)


class PaymentProvider(models.Model):
    _inherit = "payment.provider"

    def _get_compatible_providers(self, *args, **kwargs):
        """Ajusta los proveedores de pago según el método de entrega del pedido.

        - "Entrega en tienda" (delivery_type = in_store): solo Wompi (tarjeta) y
          "Pagar en la Tienda".
        - Cualquier otro método de entrega: todos los proveedores compatibles
          excepto "Pagar en la Tienda".
        """
        providers = super()._get_compatible_providers(*args, **kwargs)

        order_sudo = self.env["sale.order"].sudo().browse(kwargs.get("sale_order_id")).exists()
        if not order_sudo:
            return providers

        is_in_store = bool(
            order_sudo.carrier_id and order_sudo.carrier_id.delivery_type == "in_store"
        )

        if is_in_store:
            allowed = self.env["payment.provider"]
            for xmlid in IN_STORE_PROVIDER_XMLIDS:
                allowed |= self.env.ref(xmlid, raise_if_not_found=False) or self.env["payment.provider"]
            return providers & allowed

        pay_on_site = self.env.ref(PAY_ON_SITE_XMLID, raise_if_not_found=False)
        if pay_on_site:
            return providers - pay_on_site
        return providers

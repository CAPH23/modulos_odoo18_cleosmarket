# -*- coding: utf-8 -*-

from odoo import models


class SaleOrder(models.Model):
    _inherit = "sale.order"

    def _get_pickup_locations(self, zip_code=None, country=None, **kwargs):
        """Use a default ZIP/country for anonymous carts.

        In website_sale_collect, the popup searches pickup locations using the ZIP
        from the current order or from the customer address. Public users usually
        do not have a shipping address yet, so the search may return no results.
        This fallback lets the pickup point appear before login/checkout.
        """
        self.ensure_one()

        carrier = self.carrier_id
        has_no_zip_context = not zip_code and not self.partner_shipping_id.zip

        if carrier and carrier.delivery_type == "in_store" and has_no_zip_context:
            icp = self.env["ir.config_parameter"].sudo()
            default_zip = icp.get_param(
                "website_sale_collect_public_default.zip_code",
                default="01101",
            )
            default_country_code = icp.get_param(
                "website_sale_collect_public_default.country_code",
                default="SV",
            )

            zip_code = default_zip

            if not country:
                country = self.env["res.country"].sudo().search(
                    [("code", "=", default_country_code)],
                    limit=1,
                )

        return super()._get_pickup_locations(
            zip_code=zip_code,
            country=country,
            **kwargs,
        )

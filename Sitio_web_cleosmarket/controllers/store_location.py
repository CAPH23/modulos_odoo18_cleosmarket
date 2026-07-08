# -*- coding: utf-8 -*-

import json

from odoo.http import request, route, Controller


class CleoStoreLocationController(Controller):
    """Devuelve la ubicación principal de Super Tienda Cleo para el mapa de confirmación."""

    @route(
        "/cleo/store/location",
        type="http",
        auth="public",
        website=True,
        sitemap=False,
        csrf=False,
    )
    def cleo_store_location(self, **kwargs):
        partner = request.env["res.partner"].sudo().browse(1).exists()
        company = request.website.company_id.sudo()

        latitude = partner.partner_latitude if partner else 0.0
        longitude = partner.partner_longitude if partner else 0.0

        data = {
            "name": partner.display_name if partner else "Super Tienda Cleo",
            "latitude": latitude or 13.6610128,
            "longitude": longitude or -89.2023200,
            "label": "Super Tienda Cleo AQUÍ",
            "logo_url": "/web/image/res.company/%s/logo" % company.id,
        }

        return request.make_response(
            json.dumps(data),
            headers=[
                ("Content-Type", "application/json; charset=utf-8"),
                ("Cache-Control", "no-store"),
            ],
        )

# -*- coding: utf-8 -*-

import json

from odoo.http import Controller, request, route


class CleoPickupDefaultController(Controller):
    """Selecciona Super Tienda Cleo como punto de recogida por defecto."""

    def _json_response(self, data, status=200):
        return request.make_response(
            json.dumps(data),
            headers=[
                ("Content-Type", "application/json; charset=utf-8"),
                ("Cache-Control", "no-store"),
            ],
            status=status,
        )

    def _get_store_partner(self):
        """Contacto principal de Super Tienda Cleo."""
        return request.env["res.partner"].sudo().browse(1).exists()

    def _prepare_pickup_location_data(self, partner):
        return {
            "id": partner.id,
            "name": partner.display_name or partner.name or "Super Tienda Cleo",
            "street": partner.street or "",
            "street2": partner.street2 or "",
            "city": partner.city or "",
            "zip_code": partner.zip or "",
            "state": partner.state_id.name or "",
            "country_code": partner.country_id.code or "",
            "latitude": partner.partner_latitude or 0.0,
            "longitude": partner.partner_longitude or 0.0,
        }

    @route(
        "/cleo/pickup/default",
        type="http",
        auth="public",
        methods=["POST"],
        website=True,
        csrf=True,
        sitemap=False,
    )
    def cleo_pickup_default(self, carrier_id=None, **post):
        order_sudo = request.website.sale_get_order()
        store_partner = self._get_store_partner()

        if not order_sudo:
            return self._json_response({
                "success": False,
                "error": "No se encontró una orden activa.",
            }, status=400)

        if not store_partner:
            return self._json_response({
                "success": False,
                "error": "No se encontró el contacto Super Tienda Cleo ID 1.",
            }, status=400)

        vals = {}

        if carrier_id:
            try:
                carrier = request.env["delivery.carrier"].sudo().browse(int(carrier_id)).exists()
                if carrier and carrier.delivery_type == "in_store":
                    vals["carrier_id"] = carrier.id
            except Exception:
                pass

        if "pickup_location_data" in order_sudo._fields:
            vals["pickup_location_data"] = self._prepare_pickup_location_data(store_partner)

        # Para retiro en tienda usamos la dirección de la tienda como dirección de entrega.
        if "partner_shipping_id" in order_sudo._fields:
            vals["partner_shipping_id"] = store_partner.id

        if vals:
            order_sudo.sudo().write(vals)

        return self._json_response({
            "success": True,
            "message": "Super Tienda Cleo seleccionada como punto de recogida.",
            "partner_id": store_partner.id,
            "name": store_partner.display_name,
        })

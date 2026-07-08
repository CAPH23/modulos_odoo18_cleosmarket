# -*- coding: utf-8 -*-

import json

from odoo.http import Controller, request, route


class CleoAddressDeleteController(Controller):
    """Permite archivar direcciones del checkout de forma segura."""

    def _json_response(self, data, status=200):
        return request.make_response(
            json.dumps(data),
            headers=[
                ("Content-Type", "application/json; charset=utf-8"),
                ("Cache-Control", "no-store"),
            ],
            status=status,
        )

    @route(
        "/cleo/address/archive",
        type="http",
        auth="public",
        methods=["POST"],
        website=True,
        csrf=True,
        sitemap=False,
    )
    def cleo_address_archive(self, partner_id=None, **post):
        order_sudo = request.website.sale_get_order()

        if not order_sudo:
            return self._json_response({
                "success": False,
                "error": "No se encontró una orden activa.",
            }, status=400)

        if not partner_id:
            return self._json_response({
                "success": False,
                "error": "No se recibió el ID de la dirección.",
            }, status=400)

        try:
            partner_id = int(partner_id)
        except Exception:
            return self._json_response({
                "success": False,
                "error": "ID de dirección inválido.",
            }, status=400)

        partner_sudo = request.env["res.partner"].sudo().browse(partner_id).exists()

        if not partner_sudo:
            return self._json_response({
                "success": True,
                "message": "La dirección ya no existe.",
            })

        order_partner_sudo = order_sudo.partner_id.sudo()
        order_commercial_partner_sudo = order_partner_sudo.commercial_partner_id.sudo()

        # Seguridad: solo permitir eliminar direcciones relacionadas al cliente de la orden.
        if partner_sudo.commercial_partner_id.id != order_commercial_partner_sudo.id:
            return self._json_response({
                "success": False,
                "error": "No puedes eliminar una dirección que no pertenece a tu cuenta.",
            }, status=403)

        # No permitir archivar el contacto principal del cliente.
        if partner_sudo.id in (order_partner_sudo.id, order_commercial_partner_sudo.id):
            return self._json_response({
                "success": False,
                "error": "No puedes eliminar el contacto principal de la cuenta.",
            }, status=403)

        # Si la dirección eliminada está seleccionada en la orden, regresar al contacto principal.
        vals = {}

        if order_sudo.partner_shipping_id.id == partner_sudo.id:
            vals["partner_shipping_id"] = order_partner_sudo.id

        if order_sudo.partner_invoice_id.id == partner_sudo.id:
            vals["partner_invoice_id"] = order_partner_sudo.id

        if vals:
            order_sudo.sudo().write(vals)

        # No hacemos unlink para no afectar historial de ventas/facturas.
        partner_sudo.sudo().write({"active": False})

        return self._json_response({
            "success": True,
            "message": "Dirección eliminada correctamente.",
        })

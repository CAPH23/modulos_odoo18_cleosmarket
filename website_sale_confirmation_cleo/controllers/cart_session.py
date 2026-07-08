# -*- coding: utf-8 -*-

import json

from odoo.http import Controller, request, route


class CleoCartSessionController(Controller):
    """Limpia el carrito real de la sesión después de confirmar un pedido."""

    def _json_response(self, data, status=200):
        response = request.make_response(
            json.dumps(data, ensure_ascii=False),
            headers=[
                ("Content-Type", "application/json; charset=utf-8"),
                ("Cache-Control", "no-store"),
            ],
        )
        response.status_code = status
        return response

    @route(
        "/cleo/cart/clear_confirmed",
        type="http",
        auth="public",
        methods=["POST"],
        website=True,
        csrf=False,
        sitemap=False,
    )
    def cleo_cart_clear_confirmed(self, **post):
        session = request.session

        sale_order_id = session.get("sale_order_id")
        sale_last_order_id = session.get("sale_last_order_id")

        order_id = sale_order_id or sale_last_order_id

        if not order_id:
            session.pop("website_sale_cart_quantity", None)
            session.modified = True

            return self._json_response({
                "success": True,
                "message": "No había carrito activo en sesión.",
                "cart_quantity": 0,
            })

        try:
            order_id = int(order_id)
        except Exception:
            return self._json_response({
                "success": False,
                "error": "ID de pedido inválido en sesión.",
            }, status=400)

        order_sudo = request.env["sale.order"].sudo().browse(order_id).exists()

        if not order_sudo:
            session.pop("sale_order_id", None)
            session.pop("website_sale_cart_quantity", None)
            session.modified = True

            return self._json_response({
                "success": True,
                "message": "El pedido de la sesión ya no existe. Carrito limpiado.",
                "cart_quantity": 0,
            })

        # Solo limpiar si el pedido ya no es carrito editable.
        if order_sudo.state not in ("draft", "sent"):
            session["sale_last_order_id"] = order_sudo.id
            session.pop("sale_order_id", None)
            session.pop("website_sale_cart_quantity", None)
            session.modified = True

            return self._json_response({
                "success": True,
                "message": "Carrito confirmado limpiado correctamente.",
                "order_id": order_sudo.id,
                "order_name": order_sudo.name,
                "order_state": order_sudo.state,
                "cart_quantity": 0,
            })

        return self._json_response({
            "success": False,
            "message": "El pedido todavía está en borrador; no se limpia.",
            "order_id": order_sudo.id,
            "order_name": order_sudo.name,
            "order_state": order_sudo.state,
            "cart_quantity": order_sudo.cart_quantity,
        }, status=409)

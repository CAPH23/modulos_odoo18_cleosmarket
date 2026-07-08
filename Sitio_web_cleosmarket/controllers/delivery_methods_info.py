# -*- coding: utf-8 -*-

import json

from odoo.http import Controller, request, route
from odoo.tools import html2plaintext


class CleoDeliveryMethodsInfoController(Controller):
    """Devuelve nombre, tipo, precio y descripción real de los métodos de entrega."""

    def _json_response(self, data, status=200):
        response = request.make_response(
            json.dumps(data),
            headers=[
                ("Content-Type", "application/json; charset=utf-8"),
                ("Cache-Control", "no-store"),
            ],
        )
        response.status_code = status
        return response

    def _format_amount(self, amount, currency):
        amount = amount or 0.0
        symbol = currency.symbol or "$"

        formatted = f"{amount:,.2f}"
        formatted = formatted.replace(",", "X").replace(".", ",").replace("X", ".")

        if currency.position == "after":
            return f"{formatted} {symbol}"

        return f"{symbol} {formatted}"

    def _get_carrier_price(self, carrier, order):
        if carrier.delivery_type == "in_store":
            return 0.0

        if order:
            try:
                result = carrier.sudo().rate_shipment(order.sudo())
                if result and result.get("success") and "price" in result:
                    return result.get("price") or 0.0
            except Exception:
                pass

        if "fixed_price" in carrier._fields:
            return carrier.fixed_price or 0.0

        return 0.0

    def _clean_description(self, value):
        """Convierte la descripción en texto seguro para mostrar en el checkout."""
        if not value:
            return ""

        value = html2plaintext(value)
        value = " ".join(value.split())

        return value.strip()

    def _get_description(self, carrier):
        """Prioridad:
        1. Description for Online Quotations / website_description
        2. Carrier Description / carrier_description
        3. vacío
        """
        website_description = ""
        carrier_description = ""

        if "website_description" in carrier._fields:
            website_description = self._clean_description(carrier.website_description)

        if "carrier_description" in carrier._fields:
            carrier_description = self._clean_description(carrier.carrier_description)

        return website_description or carrier_description or ""

    @route(
        "/cleo/delivery/methods/info",
        type="http",
        auth="public",
        website=True,
        methods=["POST"],
        csrf=True,
        sitemap=False,
    )
    def cleo_delivery_methods_info(self, carrier_ids=None, **post):
        order_sudo = request.website.sale_get_order()
        currency = order_sudo.currency_id if order_sudo else request.website.company_id.currency_id

        try:
            carrier_ids = json.loads(carrier_ids or "[]")
            carrier_ids = [int(carrier_id) for carrier_id in carrier_ids if carrier_id]
        except Exception:
            carrier_ids = []

        carriers = request.env["delivery.carrier"].sudo().browse(carrier_ids).exists()

        methods = {}

        for carrier in carriers:
            price = self._get_carrier_price(carrier, order_sudo)

            methods[str(carrier.id)] = {
                "id": carrier.id,
                "name": carrier.name or "",
                "delivery_type": carrier.delivery_type or "",
                "description": self._get_description(carrier),
                "price": price,
                "price_label": "Gratuito" if price <= 0 else self._format_amount(price, currency),
            }

        return self._json_response({
            "success": True,
            "methods": methods,
        })

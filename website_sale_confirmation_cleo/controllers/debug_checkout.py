# -*- coding: utf-8 -*-

import json

from odoo.http import Controller, request, route


class CleoDebugCheckoutController(Controller):
    """Diagnóstico temporal del checkout actual usando la sesión del navegador."""

    def _json_response(self, data, status=200):
        response = request.make_response(
            json.dumps(data, indent=2, ensure_ascii=False, default=str),
            headers=[
                ("Content-Type", "application/json; charset=utf-8"),
                ("Cache-Control", "no-store"),
            ],
        )
        response.status_code = status
        return response

    def _field_value(self, record, field_name):
        if record and field_name in record._fields:
            value = record[field_name]
            if hasattr(value, "display_name"):
                return {
                    "id": value.id,
                    "name": value.display_name,
                } if value else False
            return value
        return "FIELD_NOT_FOUND"

    def _carrier_info(self, carrier, order_sudo=None):
        if not carrier:
            return False

        data = {
            "id": carrier.id,
            "name": carrier.name,
            "delivery_type": carrier.delivery_type,
            "company": carrier.company_id.display_name if carrier.company_id else False,
            "website_published": self._field_value(carrier, "website_published"),
            "is_published": self._field_value(carrier, "is_published"),
            "fixed_price": self._field_value(carrier, "fixed_price"),
            "free_over": self._field_value(carrier, "free_over"),
            "amount": self._field_value(carrier, "amount"),
            "website_description": self._field_value(carrier, "website_description"),
            "carrier_description": self._field_value(carrier, "carrier_description"),
        }

        if order_sudo:
            try:
                rate = carrier.sudo().rate_shipment(order_sudo.sudo())
                data["rate_shipment"] = rate
            except Exception as error:
                data["rate_shipment_error"] = str(error)

        return data

    def _order_lines(self, order_sudo):
        lines = []

        if not order_sudo:
            return lines

        for line in order_sudo.order_line:
            lines.append({
                "id": line.id,
                "product": line.product_id.display_name,
                "qty": line.product_uom_qty,
                "price_unit": line.price_unit,
                "price_subtotal": line.price_subtotal,
                "is_delivery": line.is_delivery if "is_delivery" in line._fields else False,
                "display_type": line.display_type,
            })

        return lines

    @route(
        "/cleo/debug/checkout/state",
        type="http",
        auth="public",
        website=True,
        sitemap=False,
    )
    def cleo_debug_checkout_state(self, **kw):
        session = request.session

        order_sudo = request.website.sale_get_order(force_create=False)

        data = {
            "session": {
                "sale_order_id": session.get("sale_order_id"),
                "sale_last_order_id": session.get("sale_last_order_id"),
                "website_sale_cart_quantity": session.get("website_sale_cart_quantity"),
                "keys_related": {
                    key: session.get(key)
                    for key in session.keys()
                    if "sale" in key or "cart" in key or "order" in key or "delivery" in key or "carrier" in key
                },
            },
            "website_sale_get_order_exists": bool(order_sudo),
        }

        if not order_sudo:
            data["message"] = "No hay pedido activo en la sesión actual."
            return self._json_response(data)

        carrier = order_sudo.carrier_id if "carrier_id" in order_sudo._fields else False

        data["order"] = {
            "id": order_sudo.id,
            "name": order_sudo.name,
            "state": order_sudo.state,
            "cart_quantity": order_sudo.cart_quantity if "cart_quantity" in order_sudo._fields else False,
            "amount_untaxed": order_sudo.amount_untaxed,
            "amount_tax": order_sudo.amount_tax,
            "amount_total": order_sudo.amount_total,
            "amount_delivery": self._field_value(order_sudo, "amount_delivery"),
            "invoice_status": self._field_value(order_sudo, "invoice_status"),
            "delivery_status": self._field_value(order_sudo, "delivery_status"),
            "partner_id": {
                "id": order_sudo.partner_id.id,
                "name": order_sudo.partner_id.display_name,
            } if order_sudo.partner_id else False,
            "partner_shipping_id": {
                "id": order_sudo.partner_shipping_id.id,
                "name": order_sudo.partner_shipping_id.display_name,
                "street": order_sudo.partner_shipping_id.street,
                "city": order_sudo.partner_shipping_id.city,
                "state": order_sudo.partner_shipping_id.state_id.name,
                "country": order_sudo.partner_shipping_id.country_id.name,
                "latitude": order_sudo.partner_shipping_id.partner_latitude,
                "longitude": order_sudo.partner_shipping_id.partner_longitude,
            } if order_sudo.partner_shipping_id else False,
            "carrier_id": self._carrier_info(carrier, order_sudo) if carrier else False,
            "pickup_location_data": self._field_value(order_sudo, "pickup_location_data"),
            "lines": self._order_lines(order_sudo),
        }

        carriers = request.env["delivery.carrier"].sudo().search([
            "|",
            ("website_published", "=", True),
            ("website_published", "=", False),
        ], order="id asc")

        data["all_delivery_carriers"] = [
            self._carrier_info(c, order_sudo)
            for c in carriers
        ]

        return self._json_response(data)

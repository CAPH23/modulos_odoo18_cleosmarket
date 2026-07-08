# -*- coding: utf-8 -*-
"""
Personalización del flujo de checkout de Super Tienda Cleo.

Objetivo:
- Desde /shop/cart permitir ir a /shop/checkout?try_skip_step=true sin validar dirección.
- En /shop/checkout el cliente selecciona el método de entrega.
- Si el método es "Entrega en tienda" (delivery_type = in_store), permitir continuar a pago
  sin dirección personal del cliente y usar la dirección de Super Tienda Cleo para facturación.
- Si el método no es "Entrega en tienda", validar dirección normalmente y enviar a /shop/address;
  al guardar dirección, regresar directamente a /shop/payment.
"""

import json

from werkzeug.urls import url_encode

from odoo import fields
from odoo.http import request, route
from odoo.tools import str2bool

from odoo.addons.website_sale_collect.controllers.main import WebsiteSaleCollect


class CleosmarketCheckoutFlow(WebsiteSaleCollect):
    """Ajustes del flujo de compra para retiro en tienda."""

    # ID real confirmado en la base:
    # delivery.carrier "Entrega en tienda" usa delivery_type = "in_store".
    # La dirección de Super Tienda Cleo corresponde al partner de la compañía principal.
    CLEO_STORE_PARTNER_XML_FALLBACK = "base.main_company"

    def _cleo_store_partner_sudo(self):
        """Devuelve el partner de la compañía principal del sitio web.

        En tu instalación corresponde a:
        Super Tienda Cleo / res.company ID 1 / partner ID 1.
        Se evita dejar el ID quemado para que sea más seguro ante copias de base.
        """
        website = request.website.sudo()
        company = website.company_id or request.env.company.sudo()
        return company.partner_id.sudo()

    def _cleo_is_in_store_order(self, order_sudo):
        """Indica si el pedido tiene seleccionado retiro/entrega en tienda."""
        return bool(
            order_sudo
            and order_sudo.carrier_id
            and order_sudo.carrier_id.delivery_type == "in_store"
        )

    def _cleo_order_uses_store_address(self, order_sudo):
        """Detecta si el pedido trae la dirección de tienda en facturación o entrega."""
        store_partner = self._cleo_store_partner_sudo()
        return bool(
            order_sudo
            and store_partner
            and (
                order_sudo.partner_shipping_id.id == store_partner.id
                or order_sudo.partner_invoice_id.id == store_partner.id
            )
        )

    def _cleo_apply_store_address_for_pickup(self, order_sudo):
        """Usa la dirección de Super Tienda Cleo como dirección de entrega/facturación.

        Esto se aplica solo cuando el método de entrega seleccionado es in_store.
        """
        if not order_sudo:
            return

        store_partner = self._cleo_store_partner_sudo()
        if not store_partner:
            return

        vals = {}
        if order_sudo.partner_shipping_id.id != store_partner.id:
            vals["partner_shipping_id"] = store_partner.id
        if order_sudo.partner_invoice_id.id != store_partner.id:
            vals["partner_invoice_id"] = store_partner.id

        if vals:
            order_sudo.sudo().write(vals)

    def _cleo_restore_customer_address_before_delivery_validation(self, order_sudo):
        """Evita que la dirección de la tienda quede como dirección para entrega a domicilio.

        Caso cubierto:
        1. Cliente selecciona "Entrega en tienda".
        2. Se asigna la dirección de Super Tienda Cleo.
        3. Cliente regresa y cambia a entrega a domicilio.
        En ese caso, no se debe permitir pagar usando la dirección de la tienda.
        """
        if not order_sudo or self._cleo_is_in_store_order(order_sudo):
            return

        store_partner = self._cleo_store_partner_sudo()
        customer_partner = order_sudo.partner_id.sudo()

        if not store_partner or not customer_partner or customer_partner.id == store_partner.id:
            return

        vals = {}
        if order_sudo.partner_shipping_id.id == store_partner.id:
            vals["partner_shipping_id"] = customer_partner.id
        if order_sudo.partner_invoice_id.id == store_partner.id:
            vals["partner_invoice_id"] = customer_partner.id

        if vals:
            order_sudo.sudo().write(vals)

    def _cleo_redirect_to_delivery_address(self, order_sudo, partner_sudo=None):
        """Redirige al formulario de dirección y vuelve a /shop/payment al guardar."""
        params = {
            "address_type": "delivery",
            "use_delivery_as_billing": "true",
            "callback": "/shop/payment",
        }
        if partner_sudo and partner_sudo.id:
            params["partner_id"] = partner_sudo.id

        return request.redirect("/shop/address?%s" % url_encode(params))
    def _cleo_required_checkout_address_missing_fields(self, partner_sudo):
        """Campos mínimos obligatorios para continuar desde /shop/checkout.

        Se validan aquí además del JS para evitar que el cliente pueda saltar
        directamente a /shop/payment con una dirección incompleta.
        """
        missing_fields = []

        if not partner_sudo or not partner_sudo.exists():
            return [
                "country_id",
                "partner_latitude",
                "partner_longitude",
                "state_id",
                "street",
            ]

        if not partner_sudo.country_id:
            missing_fields.append("country_id")
        if not partner_sudo.partner_latitude:
            missing_fields.append("partner_latitude")
        if not partner_sudo.partner_longitude:
            missing_fields.append("partner_longitude")
        if not partner_sudo.state_id:
            missing_fields.append("state_id")
        if not partner_sudo.street:
            missing_fields.append("street")

        return missing_fields

    def _cleo_checkout_address_is_complete(self, partner_sudo):
        """Devuelve True si la dirección cumple los mínimos exigidos."""
        return not self._cleo_required_checkout_address_missing_fields(partner_sudo)


    @route(
        "/shop/checkout",
        type="http",
        methods=["GET"],
        auth="public",
        website=True,
        sitemap=False,
    )
    def shop_checkout(self, try_skip_step=None, **query_params):
        """Muestra el checkout sin validar dirección.

        Odoo estándar valida dirección antes de renderizar /shop/checkout.
        Aquí solo se valida que exista carrito válido; la dirección se valida después,
        cuando el cliente confirma según el método de entrega seleccionado.
        """
        try_skip_step = str2bool(try_skip_step or "false")
        order_sudo = request.website.sale_get_order()

        if order_sudo:
            request.session["sale_last_order_id"] = order_sudo.id

        # Mantener validaciones básicas de carrito, líneas y login obligatorio si aplica.
        # Se omite únicamente la validación de direcciones.
        if redirection := self._check_cart(order_sudo):
            return redirection

        checkout_page_values = self._prepare_checkout_page_values(order_sudo, **query_params)

        can_skip_delivery = True
        if order_sudo._has_deliverable_products():
            can_skip_delivery = False
            available_dms = order_sudo._get_delivery_methods()
            checkout_page_values["delivery_methods"] = available_dms

            if delivery_method := order_sudo._get_preferred_delivery_method(available_dms):
                rate = delivery_method.rate_shipment(order_sudo)
                if (
                    not order_sudo.carrier_id
                    or not rate.get("success")
                    or order_sudo.amount_delivery != rate["price"]
                ):
                    order_sudo._set_delivery_method(delivery_method, rate=rate)

        if try_skip_step and can_skip_delivery:
            return request.redirect("/shop/confirm_order")

        return request.render("website_sale.checkout", checkout_page_values)

    def _check_addresses(self, order_sudo):
        """Valida dirección dependiendo del método de entrega.

        - in_store: no valida dirección del cliente y usa la dirección de Super Tienda Cleo.
        - otros métodos: valida dirección y al guardar redirige a /shop/payment.
        """
        if self._cleo_is_in_store_order(order_sudo):
            self._cleo_apply_store_address_for_pickup(order_sudo)
            return None

        self._cleo_restore_customer_address_before_delivery_validation(order_sudo)

        # Si el carrito es anónimo o no tiene dirección del cliente, pedir dirección.
        if order_sudo._is_anonymous_cart():
            return self._cleo_redirect_to_delivery_address(order_sudo)

        delivery_partner_sudo = order_sudo.partner_shipping_id
        if not order_sudo.only_services:
            missing_required_address_fields = self._cleo_required_checkout_address_missing_fields(
                delivery_partner_sudo
            )
            if missing_required_address_fields:
                return self._cleo_redirect_to_delivery_address(order_sudo, delivery_partner_sudo)

        if (
            not order_sudo.only_services
            and not self._check_delivery_address(delivery_partner_sudo)
            and delivery_partner_sudo._can_be_edited_by_current_customer(order_sudo, "delivery")
        ):
            return self._cleo_redirect_to_delivery_address(order_sudo, delivery_partner_sudo)

        # Si la dirección de facturación está incompleta, permitir corregirla,
        # pero siempre regresar a /shop/payment.
        invoice_partner_sudo = order_sudo.partner_invoice_id
        if (
            not self._check_billing_address(invoice_partner_sudo)
            and invoice_partner_sudo._can_be_edited_by_current_customer(order_sudo, "billing")
        ):
            params = {
                "address_type": "billing",
                "callback": "/shop/payment",
            }
            if invoice_partner_sudo and invoice_partner_sudo.id:
                params["partner_id"] = invoice_partner_sudo.id
            return request.redirect("/shop/address?%s" % url_encode(params))

        return None

    def _cleo_parse_coordinate(self, value):
        """Convierte coordenadas escritas con punto o coma decimal."""
        if value in (None, False):
            return None

        value = str(value).strip().replace(",", ".")
        if not value:
            return None

        try:
            return float(value)
        except ValueError:
            return None

    def _cleo_prepare_geo_values(self, form_data, address_type="delivery"):
        """Valida latitud y longitud del formulario /shop/address."""
        raw_latitude = form_data.get("partner_latitude")
        raw_longitude = form_data.get("partner_longitude")

        latitude = self._cleo_parse_coordinate(raw_latitude)
        longitude = self._cleo_parse_coordinate(raw_longitude)

        latitude_empty = raw_latitude in (None, False, "")
        longitude_empty = raw_longitude in (None, False, "")

        if latitude_empty or longitude_empty:
            return {}, json.dumps({
                "invalid_fields": ["partner_latitude", "partner_longitude"],
                "messages": [
                    "Debe ingresar latitud y longitud, o seleccionar el punto exacto en el mapa."
                ],
            })

        if latitude is None or longitude is None:
            return {}, json.dumps({
                "invalid_fields": ["partner_latitude", "partner_longitude"],
                "messages": [
                    "Latitud y longitud deben ser valores numéricos. Ejemplo: 13.6929400 y -89.2181900."
                ],
            })

        if latitude < -90 or latitude > 90:
            return {}, json.dumps({
                "invalid_fields": ["partner_latitude"],
                "messages": ["La latitud debe estar entre -90 y 90."],
            })

        if longitude < -180 or longitude > 180:
            return {}, json.dumps({
                "invalid_fields": ["partner_longitude"],
                "messages": ["La longitud debe estar entre -180 y 180."],
            })

        return {
            "partner_latitude": latitude,
            "partner_longitude": longitude,
        }, None

    def _cleo_get_address_partner_after_submit(self, order_sudo, partner_id=None, address_type="delivery"):
        """Obtiene el partner correcto luego de guardar /shop/address.

        Cuando se edita desde /shop/checkout, Odoo puede abrir:
        /shop/address?address_type=billing&partner_id=194

        En ese caso debemos guardar latitud/longitud directamente en ese partner_id.
        """
        Partner = request.env["res.partner"].sudo()

        if partner_id:
            try:
                partner_sudo = Partner.browse(int(partner_id)).exists()
                if partner_sudo:
                    return partner_sudo
            except Exception:
                pass

        partner_sudo = Partner.browse()

        if order_sudo:
            if address_type == "delivery":
                partner_sudo = order_sudo.partner_shipping_id.sudo()
            elif address_type == "billing":
                partner_sudo = order_sudo.partner_invoice_id.sudo()

        return partner_sudo

    @route(
        "/shop/address/submit",
        type="http",
        methods=["POST"],
        auth="public",
        website=True,
        sitemap=False,
    )
    def shop_address_submit(
        self,
        partner_id=None,
        address_type="billing",
        use_delivery_as_billing=None,
        callback=None,
        required_fields=None,
        **form_data
    ):
        """Guarda la dirección y además persiste latitud/longitud en res.partner."""
        geo_values, geo_error_response = self._cleo_prepare_geo_values(form_data)

        if geo_error_response:
            return geo_error_response

        # No incluir partner_latitude ni partner_longitude en required_fields de Odoo.
        # Esos campos los validamos nosotros arriba.
        required_fields = "name,email,phone,street,city,country_id,state_id"

        response = super().shop_address_submit(
            partner_id=partner_id,
            address_type=address_type,
            use_delivery_as_billing=use_delivery_as_billing,
            callback=callback,
            required_fields=required_fields,
            **form_data
        )

        if not geo_values:
            return response

        try:
            response_data = json.loads(response)
        except Exception:
            response_data = {}

        if response_data.get("invalid_fields") or (
            response_data.get("messages") and not response_data.get("redirectUrl")
        ):
            return response

        order_sudo = request.website.sale_get_order()
        partner_sudo = self._cleo_get_address_partner_after_submit(
            order_sudo,
            partner_id=partner_id,
            address_type=address_type,
        )

        if partner_sudo and partner_sudo.exists():
            write_values = {}

            if "partner_latitude" in partner_sudo._fields:
                write_values["partner_latitude"] = geo_values["partner_latitude"]

            if "partner_longitude" in partner_sudo._fields:
                write_values["partner_longitude"] = geo_values["partner_longitude"]

            if "date_localization" in partner_sudo._fields:
                write_values["date_localization"] = fields.Date.context_today(partner_sudo)

            if write_values:
                partner_sudo.sudo().write(write_values)

        return response

    def _cleo_parse_coordinate(self, value):
        """Convierte coordenadas escritas con punto o coma decimal."""
        if value in (None, False):
            return None

        value = str(value).strip().replace(",", ".")
        if not value:
            return None

        try:
            return float(value)
        except ValueError:
            return None

    def _cleo_prepare_geo_values(self, form_data, address_type="delivery"):
        raw_latitude = form_data.get("partner_latitude")
        raw_longitude = form_data.get("partner_longitude")
    
        latitude = self._cleo_parse_coordinate(raw_latitude)
        longitude = self._cleo_parse_coordinate(raw_longitude)
    
        latitude_empty = raw_latitude in (None, False, "")
        longitude_empty = raw_longitude in (None, False, "")
    
        if address_type != "delivery" and latitude_empty and longitude_empty:
            return {}, None
    
        if latitude_empty or longitude_empty:
            return {}, json.dumps({
                "invalid_fields": ["partner_latitude", "partner_longitude"],
                "messages": [
                    "Debe ingresar latitud y longitud, o seleccionar el punto exacto en el mapa."
                ],
            })
    
        if latitude is None or longitude is None:
            return {}, json.dumps({
                "invalid_fields": ["partner_latitude", "partner_longitude"],
                "messages": [
                    "Latitud y longitud deben ser valores numéricos. Ejemplo: 13.6929400 y -89.2181900."
                ],
            })
    
        if latitude < -90 or latitude > 90:
            return {}, json.dumps({
                "invalid_fields": ["partner_latitude"],
                "messages": ["La latitud debe estar entre -90 y 90."],
            })
    
        if longitude < -180 or longitude > 180:
            return {}, json.dumps({
                "invalid_fields": ["partner_longitude"],
                "messages": ["La longitud debe estar entre -180 y 180."],
            })
    
        return {
            "partner_latitude": latitude,
            "partner_longitude": longitude,
        }, None

    def _cleo_get_address_partner_after_submit(self, order_sudo, partner_id=None, address_type="delivery"):
        """Obtiene el partner correcto luego de guardar /shop/address."""
        Partner = request.env["res.partner"].sudo()
        partner_sudo = Partner.browse()

        if order_sudo:
            if address_type == "delivery":
                partner_sudo = order_sudo.partner_shipping_id.sudo()
            elif address_type == "billing":
                partner_sudo = order_sudo.partner_invoice_id.sudo()

        if (not partner_sudo or not partner_sudo.exists()) and partner_id:
            try:
                partner_sudo = Partner.browse(int(partner_id)).exists()
            except Exception:
                partner_sudo = Partner.browse()

        return partner_sudo

    @route(
        "/shop/address/submit",
        type="http",
        methods=["POST"],
        auth="public",
        website=True,
        sitemap=False,
    )
    def shop_address_submit(
        self,
        partner_id=None,
        address_type="billing",
        use_delivery_as_billing=None,
        callback=None,
        required_fields=None,
        **form_data
    ):

        """Guarda la dirección y además persiste latitud/longitud en res.partner."""
        sv_country = self._cleo_get_el_salvador_country()
        if sv_country:
            form_data["country_id"] = str(sv_country.id)

        geo_values, geo_error_response = self._cleo_prepare_geo_values(
            form_data,
            address_type=address_type,
        )

        if geo_error_response:
            return geo_error_response

        response = super().shop_address_submit(
            partner_id=partner_id,
            address_type=address_type,
            use_delivery_as_billing=use_delivery_as_billing,
            callback=callback,
            required_fields=required_fields,
            **form_data
        )

        if not geo_values:
            return response

        try:
            response_text = response.get_data(as_text=True) if hasattr(response, "get_data") else response
            response_data = json.loads(response_text)
        except Exception:
            response_data = {}

        if response_data.get("invalid_fields") or (
            response_data.get("messages") and not response_data.get("redirectUrl")
        ):
            return response

        order_sudo = request.website.sale_get_order()
        partner_sudo = self._cleo_get_address_partner_after_submit(
            order_sudo,
            partner_id=partner_id,
            address_type=address_type,
        )

        if partner_sudo and partner_sudo.exists():
            write_values = {}

            if "partner_latitude" in partner_sudo._fields:
                write_values["partner_latitude"] = geo_values["partner_latitude"]

            if "partner_longitude" in partner_sudo._fields:
                write_values["partner_longitude"] = geo_values["partner_longitude"]

            if "date_localization" in partner_sudo._fields:
                write_values["date_localization"] = fields.Date.context_today(partner_sudo)

            if write_values:
                partner_sudo.sudo().write(write_values)

        return response

    def _cleo_get_el_salvador_country(self):
        """Obtiene El Salvador de forma segura por código ISO."""
        return request.env["res.country"].sudo().search([("code", "=", "SV")], limit=1)

    def _check_shipping_method(self, order_sudo):
        """Evita que el pago de retiro en tienda sea devuelto a checkout por dirección."""
        if self._cleo_is_in_store_order(order_sudo):
            self._cleo_apply_store_address_for_pickup(order_sudo)
            return None
        return super()._check_shipping_method(order_sudo)

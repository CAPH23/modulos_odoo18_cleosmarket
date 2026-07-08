# -*- coding: utf-8 -*-
import logging
import math
import re

from odoo import http
from odoo.http import request

from odoo.addons.website_sale.controllers.main import WebsiteSale

_logger = logging.getLogger(__name__)
_logger.info("PY sync: controlador website_sale de delivery_pedidosya CARGADO")


class WebsiteSalePedidosYa(WebsiteSale):

    @http.route(
        ['/shop/checkout', '/shop/checkout/'],
        type='http',
        methods=['GET'],
        auth='public',
        website=True,
        sitemap=False,
    )
    def shop_checkout(self, try_skip_step=None, **query_params):
        """Antes de que Odoo calcule tarifas, sincroniza la dirección real
        del pedido con una dirección de entrega válida del cliente.

        El problema corregido:
        - Al entrar por primera vez a /shop/checkout, el pedido podía conservar
          como partner_shipping_id una dirección de recogida/punto de tienda
          usada anteriormente, por ejemplo "Charlie Brown, Super Tienda Cleo".
        - El checkout mostraba las direcciones del cliente, pero la tarifa de
          PedidosYa se calculaba con la dirección vieja almacenada en la orden.
        - Al hacer clic en una dirección, el JS nativo de Odoo llamaba a
          /shop/update_address y recién entonces el cálculo era correcto.
        """
        _logger.info(
            "PY sync: shop_checkout interceptado try_skip_step=%s params=%s",
            try_skip_step,
            query_params,
        )
        self._pedidosya_sync_default_shipping()
        return super().shop_checkout(
            try_skip_step=try_skip_step,
            **query_params,
        )

    # ---------------------------------------------------------------------
    # Helpers de sincronización
    # ---------------------------------------------------------------------
    @staticmethod
    def _py_norm(value):
        value = (value or '').strip().lower()
        value = re.sub(r'\s+', ' ', value)
        return value

    @staticmethod
    def _py_distance_km(lat1, lng1, lat2, lng2):
        try:
            lat1 = float(lat1)
            lng1 = float(lng1)
            lat2 = float(lat2)
            lng2 = float(lng2)
        except (TypeError, ValueError):
            return None
        radius = 6371.0
        d_lat = math.radians(lat2 - lat1)
        d_lng = math.radians(lng2 - lng1)
        a = (
            math.sin(d_lat / 2) ** 2
            + math.cos(math.radians(lat1))
            * math.cos(math.radians(lat2))
            * math.sin(d_lng / 2) ** 2
        )
        return radius * 2 * math.asin(math.sqrt(a))

    def _pedidosya_get_pickup_partners(self, order):
        """Partners que representan tienda/bodega/punto de recogida.

        Se usan para evitar que una dirección tipo "Super Tienda Cleo" quede
        como DROP_OFF del cliente y PedidosYa cotice desde la tienda hacia la
        misma tienda o hacia un punto incorrecto.
        """
        Partner = request.env['res.partner'].sudo()
        partners = Partner.browse()

        for partner in (
            order.company_id.partner_id,
            request.website.company_id.partner_id,
            order.warehouse_id.partner_id,
        ):
            if partner:
                partners |= partner.sudo()

        warehouses = request.env['stock.warehouse'].sudo().search([
            ('company_id', '=', order.company_id.id),
        ])
        partners |= warehouses.mapped('partner_id')
        return partners.exists()

    def _pedidosya_is_pickup_like_address(self, partner, pickup_partners):
        """Detecta si una dirección del cliente realmente parece punto tienda."""
        if not partner:
            return False
        partner = partner.sudo()
        pickup_partners = pickup_partners.sudo().exists()

        if partner in pickup_partners:
            return True

        pickup_names = {
            self._py_norm(p.name)
            for p in pickup_partners
            if self._py_norm(p.name)
        }
        partner_name = self._py_norm(partner.name)
        if partner_name and partner_name in pickup_names:
            return True

        # Si las coordenadas son prácticamente iguales al punto de recogida,
        # también se considera dirección de tienda. 0.08 km = aprox. 80 metros.
        if partner.partner_latitude and partner.partner_longitude:
            for pickup in pickup_partners:
                if not (pickup.partner_latitude and pickup.partner_longitude):
                    continue
                distance = self._py_distance_km(
                    partner.partner_latitude,
                    partner.partner_longitude,
                    pickup.partner_latitude,
                    pickup.partner_longitude,
                )
                if distance is not None and distance <= 0.08:
                    return True

        return False

    @staticmethod
    def _pedidosya_is_complete_delivery_address(partner):
        return bool(
            partner
            and partner.street
            and partner.city
            and partner.country_id
        )

    def _pedidosya_get_delivery_candidates(self, order):
        """Replica el criterio base de Odoo para direcciones de entrega.

        Odoo 18 prepara las tarjetas de entrega usando los contactos hijos del
        commercial partner con tipo delivery/other, más el partner principal.
        Aquí se aplica el mismo criterio y luego se limpian direcciones de tienda.
        """
        Partner = order.partner_id.with_context(show_address=1).sudo()
        commercial = order.partner_id.commercial_partner_id.sudo()
        pickup_partners = self._pedidosya_get_pickup_partners(order)

        candidates = Partner.search([
            ('id', 'child_of', commercial.ids),
            '|',
            ('type', 'in', ['delivery', 'other']),
            ('id', '=', commercial.id),
        ], order='id desc') | order.partner_id.sudo()

        if order.partner_id.sudo() != commercial:
            # Igual que Odoo: si el principal no está completo, no debe ser
            # usado como dirección visible de entrega para un contacto hijo.
            if not self._pedidosya_is_complete_delivery_address(commercial):
                candidates = candidates.filtered(lambda p: p.id != commercial.id)

        candidates = candidates.filtered(self._pedidosya_is_complete_delivery_address)
        candidates = candidates.filtered(
            lambda p: not self._pedidosya_is_pickup_like_address(p, pickup_partners)
        )
        return candidates

    def _pedidosya_select_default_shipping(self, order, candidates):
        """Selecciona una dirección real del cliente para la cotización inicial."""
        if not candidates:
            return False

        # 1) Si ya hubo una venta real con dirección válida y no fue recogida
        # en tienda, usar la última dirección de envío real del cliente.
        last_order = request.env['sale.order'].sudo().search([
            ('partner_id.commercial_partner_id', '=', order.partner_id.commercial_partner_id.id),
            ('state', 'in', ('sale', 'done')),
            ('partner_shipping_id', 'in', candidates.ids),
            '|',
            ('carrier_id', '=', False),
            ('carrier_id.delivery_type', '!=', 'in_store'),
        ], order='id desc', limit=1)
        if last_order.partner_shipping_id:
            return last_order.partner_shipping_id

        commercial = order.partner_id.commercial_partner_id.sudo()
        if commercial in candidates:
            return commercial

        # 2) Si no hay historial, usar la primera en el mismo orden en que Odoo
        # las prepara para el checkout: id descendente.
        return candidates[:1]

    def _pedidosya_sync_default_shipping(self):
        order = request.website.sale_get_order()
        if not order or order.state != 'draft':
            _logger.info("PY sync: sin orden en borrador; no se hace nada")
            return
        if not order._has_deliverable_products():
            _logger.info("PY sync: orden sin productos entregables; no se hace nada")
            return

        candidates = self._pedidosya_get_delivery_candidates(order)
        current = order.partner_shipping_id.sudo()
        pickup_partners = self._pedidosya_get_pickup_partners(order)
        current_is_pickup_like = self._pedidosya_is_pickup_like_address(
            current,
            pickup_partners,
        )

        _logger.info(
            "PY sync: orden=%s ship_actual=%s|%s|tipo=%s pickup_like=%s candidatas=%s",
            order.name,
            current.id,
            current.display_name,
            current.type,
            current_is_pickup_like,
            [(c.id, c.display_name, c.type) for c in candidates],
        )

        if not candidates:
            _logger.info("PY sync: sin candidatas reales; no se cambia")
            return

        if current in candidates and not current_is_pickup_like:
            _logger.info("PY sync: la dirección actual ES candidata real; no se cambia")
            return

        target = self._pedidosya_select_default_shipping(order, candidates)
        if not target:
            _logger.info("PY sync: no se pudo determinar target; no se cambia")
            return

        _logger.info(
            "PY sync: reasignando dirección de entrega a %s|%s",
            target.id,
            target.display_name,
        )

        # Usar el helper estándar de Odoo para que se recomputen correctamente
        # los campos dependientes de direcciones en el pedido.
        order_sudo = order.sudo()
        order_sudo._update_address(target.id, ['partner_shipping_id'])

        # Si venía de un flujo de recogida/pickup, limpiar ese dato para que
        # el pago/checkout no mezcle recogida con entrega a domicilio.
        if 'pickup_location_data' in order_sudo._fields and order_sudo.pickup_location_data:
            order_sudo.pickup_location_data = False

        order.invalidate_recordset(['partner_shipping_id'])

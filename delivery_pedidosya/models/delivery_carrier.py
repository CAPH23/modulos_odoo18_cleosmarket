# -*- coding: utf-8 -*-
import re
import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from .pedidosya_client import PedidosYaClient, PedidosYaMockClient

_logger = logging.getLogger(__name__)

# Límites físicos publicados en el OpenAPI v3
MAX_ITEM_VOLUME_CM3 = 80840.0     # 47*43*40 cm
MAX_ITEM_WEIGHT_KG = 20.0
MAX_ITEMS = 100


class DeliveryCarrier(models.Model):
    _inherit = 'delivery.carrier'

    delivery_type = fields.Selection(
        selection_add=[('pedidosya', 'PedidosYa')],
        ondelete={'pedidosya': lambda recs: recs.write(
            {'delivery_type': 'fixed', 'fixed_price': 0})},
    )

    # --- modo de operación ---------------------------------------------------
    pedidosya_mode = fields.Selection(
        selection=[
            ('mock', 'Simulado (sin conexión a la API)'),
            ('test', 'Pruebas (API real con isTest=True)'),
            ('prod', 'Producción'),
        ],
        string='Modo PedidosYa', default='mock', required=False,
        help="Simulado: no se hace ninguna llamada externa; ideal para desarrollar.\n"
             "Pruebas: usa la API real con envíos de simulación (isTest=true).\n"
             "Producción: crea envíos reales con riders reales.")

    # --- credenciales (las entrega PedidosYa) ---------------------------------
    pedidosya_auth_url = fields.Char(
        string='URL de autenticación',
        help="Endpoint para generar el token (lo informa PedidosYa junto con las "
             "credenciales; no figura en el OpenAPI). El token dura 45 minutos y "
             "se cachea automáticamente.")
    pedidosya_client_id = fields.Char(string='Client ID', groups='base.group_system')
    pedidosya_client_secret = fields.Char(string='Client Secret', groups='base.group_system')
    pedidosya_user = fields.Char(string='Usuario API', groups='base.group_system')
    pedidosya_password = fields.Char(string='Contraseña API', groups='base.group_system')

    # --- caché de token --------------------------------------------------------
    pedidosya_token = fields.Char(string='Token (caché)', copy=False,
                                  groups='base.group_system')
    pedidosya_token_expiration = fields.Datetime(
        string='Token expira', copy=False, groups='base.group_system')

    # --- opciones --------------------------------------------------------------
    pedidosya_default_item_type = fields.Selection(
        selection=[('STANDARD', 'Estándar'), ('FRAGILE', 'Frágil'), ('COLD', 'Frío')],
        string='Tipo de ítem por defecto', default='STANDARD')
    pedidosya_notification_mail = fields.Boolean(
        string='Notificar al cliente por email', default=True,
        help="Envía el email del cliente en notificationMail para que PedidosYa "
             "le notifique confirmación y cancelación del envío.")

    # --- parámetros del simulador -----------------------------------------------
    pedidosya_sim_base_price = fields.Float(
        string='Simulación: tarifa base (USD)', default=3.0)
    pedidosya_sim_km_price = fields.Float(
        string='Simulación: precio por km (USD)', default=0.5)

    # --- webhooks (Fase 2) --------------------------------------------------------
    pedidosya_webhook_key = fields.Char(
        string='Clave del webhook (authorizationKey)', copy=False,
        groups='base.group_system',
        help="PedidosYa enviará esta clave en el header Authorization de cada "
             "notificación. Se valida en /pedidosya/webhook.")
    pedidosya_webhook_url = fields.Char(
        string='URL del webhook', compute='_compute_pedidosya_webhook_url',
        help="URL pública que se registra en PedidosYa. Incluye ?db= porque "
             "el dbfilter del servidor matchea más de una base de datos.")
    pedidosya_webhook_registered = fields.Boolean(
        string='Webhook registrado', copy=False, readonly=True)

    def _compute_pedidosya_webhook_url(self):
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        dbname = self.env.cr.dbname
        for carrier in self:
            carrier.pedidosya_webhook_url = (
                '%s/pedidosya/webhook?db=%s' % (base_url, dbname))

    def action_pedidosya_generate_webhook_key(self):
        import secrets
        for carrier in self:
            carrier.pedidosya_webhook_key = secrets.token_urlsafe(36)
            carrier.pedidosya_webhook_registered = False
        return True

    def action_pedidosya_register_webhook(self):
        """Registra la URL + clave en PedidosYa (PUT /v3/webhooks-configuration).

        En modo simulado no llama a ninguna API: solo valida la configuración
        y marca el registro, para poder probar el flujo con curl.
        """
        self.ensure_one()
        if not self.pedidosya_webhook_key:
            self.action_pedidosya_generate_webhook_key()
        config = {
            'isTest': self.pedidosya_mode != 'prod',
            'notificationType': 'WEBHOOK',
            'topic': 'SHIPPING_STATUS',
            'urls': [{
                'url': self.pedidosya_webhook_url,
                'authorizationKey': self.pedidosya_webhook_key,
            }],
        }
        client = self._pedidosya_get_client()
        client.set_webhooks_configuration(config)
        self.pedidosya_webhook_registered = True
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('PedidosYa'),
                'message': _('Webhook registrado: %s',
                             self.pedidosya_webhook_url),
                'type': 'success',
                'sticky': False,
            },
        }


    # =========================================================================
    # Helpers
    # =========================================================================
    def _pedidosya_get_client(self):
        self.ensure_one()
        if self.pedidosya_mode in (False, 'mock'):
            return PedidosYaMockClient(self)
        return PedidosYaClient(self)

    @api.model
    def _pedidosya_format_phone(self, phone):
        """Formato exigido: prefijo '+' opcional y solo dígitos (máx. 14)."""
        if not phone:
            return False
        cleaned = re.sub(r'[^\d+]', '', phone)
        if cleaned.startswith('+'):
            cleaned = '+' + re.sub(r'\D', '', cleaned[1:])
        else:
            cleaned = re.sub(r'\D', '', cleaned)
        return cleaned[:14] or False

    def _pedidosya_ensure_geolocation(self, partner):
        """Geolocaliza el contacto si aún no tiene coordenadas.

        base_geolocalize guarda lat/lng en el contacto, así que la llamada
        externa ocurre UNA sola vez por dirección; las siguientes cotizaciones
        leen las coordenadas ya almacenadas. Se usa sudo porque en el checkout
        la cotización corre como usuario público, sin permiso de escritura
        sobre contactos.
        """
        if partner.partner_latitude and partner.partner_longitude:
            return True
        if not (partner.street and partner.city):
            return False
        try:
            return partner.sudo().geo_localize()
        except Exception:
            _logger.warning(
                "PedidosYa: no se pudo geolocalizar el contacto %s",
                partner.display_name)
            return False

    def _pedidosya_partner_missing_fields(self, partner):
        """Campos que exige el esquema WayPointModel."""
        missing = []
        if not partner.street:
            missing.append(_('calle (street)'))
        if not partner.city:
            missing.append(_('ciudad'))
        if not (partner.phone or partner.mobile):
            missing.append(_('teléfono'))
        if not partner.name:
            missing.append(_('nombre de contacto'))
        return missing

    def _pedidosya_prepare_waypoint(self, partner, wp_type, instructions=None,
                                    fallback_phone=None):
        self.ensure_one()
        self._pedidosya_ensure_geolocation(partner)   # <-- línea nueva
        phone = self._pedidosya_format_phone(partner.phone or partner.mobile
                                             or fallback_phone)
        waypoint = {
            'type': wp_type,                                    # PICK_UP | DROP_OFF
            'addressStreet': (partner.street or '')[:255],
            'city': (partner.city or partner.state_id.name or '')[:255],
            'phone': phone or '',
            'name': (partner.name or '')[:70],
        }
        if partner.street2:
            waypoint['addressAdditional'] = partner.street2[:150]
        if instructions:
            waypoint['instructions'] = instructions[:255]
        # lat/lng opcionales: si no van, PedidosYa geocodifica addressStreet
        if partner.partner_latitude and partner.partner_longitude:
            waypoint['latitude'] = partner.partner_latitude
            waypoint['longitude'] = partner.partner_longitude
        return waypoint

    def _pedidosya_prepare_item(self, product, quantity, unit_value, description=None):
        self.ensure_one()
        weight = product.weight or 0.1                       # kg por unidad
        volume_cm3 = (product.volume or 0.0) * 1_000_000.0   # m3 → cm3
        if not volume_cm3:
            volume_cm3 = 1000.0                              # 10x10x10 cm por defecto
        return {
            'type': self.pedidosya_default_item_type or 'STANDARD',
            'value': round(max(unit_value, 0.0), 2),
            'description': (description or product.display_name or 'Producto')[:235],
            'sku': (product.default_code or '')[:50] or None,
            'quantity': max(1, int(round(quantity))),
            'volume': round(min(volume_cm3, MAX_ITEM_VOLUME_CM3), 2),
            'weight': round(min(weight, MAX_ITEM_WEIGHT_KG), 2),
        }

    def _pedidosya_pickup_partner(self, warehouse=None):
        self.ensure_one()
        partner = (warehouse and warehouse.partner_id) \
            or self.company_id.partner_id or self.env.company.partner_id
        return partner

    def _pedidosya_select_offer(self, estimate_response):
        """Elige la mejor oferta: EXPRESS más barata; si no hay, la primera."""
        offers = estimate_response.get('deliveryOffers') or []
        if not offers:
            return None
        express = [o for o in offers if o.get('deliveryMode') == 'EXPRESS']
        pool = express or offers
        return min(pool, key=lambda o: (o.get('pricing') or {}).get('total', 0.0))

    def _pedidosya_offer_price_in_currency(self, offer, target_currency, company, date):
        pricing = offer.get('pricing') or {}
        total = pricing.get('total', 0.0)
        code = pricing.get('currency') or 'USD'
        from_currency = self.env['res.currency'].with_context(active_test=False).search(
            [('name', '=', code)], limit=1)
        if from_currency and target_currency and from_currency != target_currency:
            total = from_currency._convert(total, target_currency, company, date)
        return total

    # =========================================================================
    # Corrección de dirección inicial del checkout
    # =========================================================================
    @api.model
    def _pedidosya_norm_text(self, value):
        value = (value or '').strip().lower()
        return re.sub(r'\s+', ' ', value)

    @api.model
    def _pedidosya_distance_km(self, lat1, lng1, lat2, lng2):
        """Distancia aproximada entre dos coordenadas."""
        import math
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

    def _pedidosya_checkout_pickup_partners(self, order, pickup=None):
        """Partners que representan tienda/bodega/punto de retiro.

        Se usa en rate_shipment porque /shop/checkout puede calcular tarifa antes
        de que el cliente haga clic nuevamente en una dirección guardada.
        """
        self.ensure_one()
        Partner = self.env['res.partner'].sudo()
        partners = Partner.browse()

        for partner in (
            pickup,
            order.company_id.partner_id,
            order.warehouse_id.partner_id,
            order.website_id.company_id.partner_id if order.website_id else False,
        ):
            if partner:
                partners |= partner.sudo()

        warehouses = self.env['stock.warehouse'].sudo().search([
            ('company_id', '=', order.company_id.id),
        ])
        partners |= warehouses.mapped('partner_id')
        return partners.exists()

    def _pedidosya_is_pickup_like_dropoff(self, partner, pickup_partners):
        """Detecta si el DROP_OFF parece ser realmente la tienda.

        Caso real visto en logs:
        - partner_shipping_id = "Charlie Brown, Super Tienda Cleo"
        - esa dirección tiene coordenadas de la tienda y genera una tarifa inicial
          distinta a la dirección que el cliente selecciona después.
        """
        if not partner:
            return False
        partner = partner.sudo()
        pickup_partners = pickup_partners.sudo().exists()

        if partner in pickup_partners:
            return True

        partner_name = self._pedidosya_norm_text(partner.name)
        partner_display = self._pedidosya_norm_text(partner.display_name)
        partner_street = self._pedidosya_norm_text(partner.street)
        partner_city = self._pedidosya_norm_text(partner.city)

        for pickup in pickup_partners:
            pickup_name = self._pedidosya_norm_text(pickup.name)
            pickup_display = self._pedidosya_norm_text(pickup.display_name)
            pickup_street = self._pedidosya_norm_text(pickup.street)
            pickup_city = self._pedidosya_norm_text(pickup.city)

            # Nombre igual o contenido en display_name, ejemplo:
            # "Charlie Brown, Super Tienda Cleo" contiene "Super Tienda Cleo".
            if pickup_name and (
                partner_name == pickup_name
                or pickup_name in partner_display
                or partner_name == pickup_display
            ):
                return True

            # Misma calle/ciudad que la tienda.
            if pickup_street and partner_street == pickup_street:
                if not pickup_city or not partner_city or partner_city == pickup_city:
                    return True

            # Coordenadas prácticamente iguales a la tienda.
            if (
                partner.partner_latitude and partner.partner_longitude
                and pickup.partner_latitude and pickup.partner_longitude
            ):
                distance = self._pedidosya_distance_km(
                    partner.partner_latitude,
                    partner.partner_longitude,
                    pickup.partner_latitude,
                    pickup.partner_longitude,
                )
                if distance is not None and distance <= 0.08:
                    return True

        return False

    @api.model
    def _pedidosya_is_complete_delivery_dropoff(self, partner):
        return bool(
            partner
            and partner.street
            and partner.city
            and partner.country_id
        )

    def _pedidosya_get_checkout_delivery_candidates(self, order, pickup_partners):
        """Direcciones válidas del cliente, siguiendo el criterio de Odoo 18.

        Odoo 18 arma las tarjetas de dirección de entrega con los hijos del
        commercial_partner de tipo delivery/other y el partner comercial.
        Aquí se usa el mismo criterio, pero descartando direcciones que parezcan
        tienda/punto de retiro.
        """
        Partner = order.partner_id.with_context(show_address=1).sudo()
        commercial = order.partner_id.commercial_partner_id.sudo()

        candidates = Partner.search([
            ('id', 'child_of', commercial.ids),
            '|',
            ('type', 'in', ['delivery', 'other']),
            ('id', '=', commercial.id),
        ], order='id desc') | order.partner_id.sudo()

        if order.partner_id.sudo() != commercial:
            if not self._pedidosya_is_complete_delivery_dropoff(commercial):
                candidates = candidates.filtered(lambda p: p.id != commercial.id)

        candidates = candidates.filtered(self._pedidosya_is_complete_delivery_dropoff)
        candidates = candidates.filtered(
            lambda p: not self._pedidosya_is_pickup_like_dropoff(p, pickup_partners)
        )
        return candidates.exists()

    def _pedidosya_select_checkout_dropoff(self, order, pickup):
        """Devuelve el dropoff correcto para cotizar.

        Regla principal:
        - Si el partner_shipping_id actual es una dirección real del cliente, se
          respeta. Esto evita cambiar la dirección después de que el cliente haga
          clic en Sofia Bergara u otra dirección guardada.
        - Si el partner_shipping_id actual parece tienda/pickup, se reemplaza por
          una dirección real del cliente antes de llamar a PedidosYa.
        """
        self.ensure_one()
        current = order.partner_shipping_id.sudo()
        pickup_partners = self._pedidosya_checkout_pickup_partners(order, pickup=pickup)
        current_is_pickup_like = self._pedidosya_is_pickup_like_dropoff(
            current, pickup_partners)
        candidates = self._pedidosya_get_checkout_delivery_candidates(
            order, pickup_partners)

        _logger.info(
            "PY sync/rate: orden=%s ship_actual=%s|%s|tipo=%s pickup_like=%s candidatas=%s",
            order.name,
            current.id,
            current.display_name,
            current.type,
            current_is_pickup_like,
            [(p.id, p.display_name, p.type) for p in candidates],
        )

        if current in candidates and not current_is_pickup_like:
            return current

        target = False
        commercial = order.partner_id.commercial_partner_id.sudo()

        # Preferir el partner real del pedido/comercial. En tu caso es el que
        # aparece luego como "Charlie Brown (id=194)".
        for preferred in (order.partner_id.sudo(), commercial):
            if preferred in candidates:
                target = preferred
                break

        # Si no hay preferido, usar última dirección real utilizada en una venta.
        if not target:
            last_order = self.env['sale.order'].sudo().search([
                ('partner_id.commercial_partner_id', '=', commercial.id),
                ('state', 'in', ('sale', 'done')),
                ('partner_shipping_id', 'in', candidates.ids),
                '|',
                ('carrier_id', '=', False),
                ('carrier_id.delivery_type', '!=', 'in_store'),
            ], order='id desc', limit=1)
            target = last_order.partner_shipping_id

        # Último recurso: primera candidata válida.
        if not target and candidates:
            target = candidates[:1]

        if target and target != current:
            _logger.info(
                "PY sync/rate: corrigiendo partner_shipping_id %s|%s -> %s|%s antes de cotizar",
                current.id,
                current.display_name,
                target.id,
                target.display_name,
            )
            try:
                order.sudo()._update_address(target.id, ['partner_shipping_id'])
                order.invalidate_recordset(['partner_shipping_id'])
            except Exception:
                _logger.exception(
                    "PY sync/rate: no se pudo actualizar partner_shipping_id; se usará target solo para la cotización"
                )
            return target

        return current

    # =========================================================================
    # Payloads
    # =========================================================================
    def _pedidosya_prepare_estimate_from_order(self, order):
        """Payload EstimationShippingRequest desde una sale.order (checkout)."""
        self.ensure_one()
        errors, warnings = [], []

        pickup = self._pedidosya_pickup_partner(order.warehouse_id)
        dropoff = self._pedidosya_select_checkout_dropoff(order, pickup)
        _logger.info(
            "PY rate: dropoff=%s (id=%s) lat=%s lng=%s",
            dropoff.display_name, dropoff.id,
            dropoff.partner_latitude, dropoff.partner_longitude)

        missing_pickup = self._pedidosya_partner_missing_fields(pickup)
        if missing_pickup:
            errors.append(_("Punto de recogida '%(name)s' incompleto: %(fields)s",
                            name=pickup.display_name,
                            fields=', '.join(missing_pickup)))

        # En cotización somos tolerantes: si al cliente le falta el teléfono
        # usamos el de la empresa y avisamos; al CREAR el envío sí es bloqueante.
        fallback_phone = pickup.phone or pickup.mobile
        missing_dropoff = self._pedidosya_partner_missing_fields(dropoff)
        blocking_dropoff = [m for m in missing_dropoff if 'tel' not in m]
        if blocking_dropoff:
            errors.append(_("Dirección de entrega incompleta: %s")
                          % ', '.join(blocking_dropoff))
        elif missing_dropoff:
            warnings.append(_("El cliente no tiene teléfono; se usará el de la "
                              "tienda para cotizar."))

        items = []
        for line in order.order_line:
            if (line.display_type or line.is_delivery
                    or line.product_id.type == 'service'
                    or line.product_uom_qty <= 0):
                continue
            unit_value = (line.price_total / line.product_uom_qty
                          if line.product_uom_qty else line.price_unit)
            items.append(self._pedidosya_prepare_item(
                line.product_id, line.product_uom_qty, unit_value, line.name))
        if not items:
            errors.append(_("No hay productos físicos que enviar."))
        items = items[:MAX_ITEMS]

        payload = {
            'referenceId': (order.name or 'SO')[:255],
            'isTest': self.pedidosya_mode != 'prod',
            'items': items,
            'waypoints': [
                self._pedidosya_prepare_waypoint(pickup, 'PICK_UP'),
                self._pedidosya_prepare_waypoint(
                    dropoff, 'DROP_OFF', fallback_phone=fallback_phone),
            ],
        }
        if self.pedidosya_notification_mail and dropoff.email:
            payload['notificationMail'] = dropoff.email[:255]
        return payload, errors, warnings

    def _pedidosya_prepare_estimate_from_picking(self, picking):
        """Payload EstimationShippingRequest desde un stock.picking (envío real)."""
        self.ensure_one()
        errors = []

        order = picking.sale_id
        warehouse = picking.picking_type_id.warehouse_id
        pickup = self._pedidosya_pickup_partner(warehouse)
        dropoff = picking.partner_id

        for partner, label in ((pickup, _('recogida')), (dropoff, _('entrega'))):
            missing = self._pedidosya_partner_missing_fields(partner)
            if missing:
                errors.append(_("Datos faltantes en el punto de %(label)s "
                                "(%(name)s): %(fields)s",
                                label=label, name=partner.display_name,
                                fields=', '.join(missing)))

        items = []
        for move in picking.move_ids:
            if move.state == 'cancel' or move.product_id.type == 'service':
                continue
            qty = move.quantity or move.product_uom_qty
            if qty <= 0:
                continue
            sale_line = move.sale_line_id
            if sale_line and sale_line.product_uom_qty:
                unit_value = sale_line.price_total / sale_line.product_uom_qty
            else:
                unit_value = move.product_id.lst_price
            items.append(self._pedidosya_prepare_item(
                move.product_id, qty, unit_value))
        if not items:
            errors.append(_("La transferencia no tiene productos físicos que enviar."))
        items = items[:MAX_ITEMS]

        payload = {
            'referenceId': (picking.name or order.name or 'PICK')[:255],
            'isTest': self.pedidosya_mode != 'prod',
            'items': items,
            'waypoints': [
                self._pedidosya_prepare_waypoint(pickup, 'PICK_UP'),
                self._pedidosya_prepare_waypoint(dropoff, 'DROP_OFF',
                                                 instructions=picking.note and
                                                 str(picking.note) or None),
            ],
        }
        email = dropoff.email or (order and order.partner_id.email)
        if self.pedidosya_notification_mail and email:
            payload['notificationMail'] = email[:255]
        return payload, errors

    # =========================================================================
    # API estándar de delivery.carrier
    # =========================================================================
    def pedidosya_rate_shipment(self, order):
        self.ensure_one()
        payload, errors, warnings = self._pedidosya_prepare_estimate_from_order(order)
        if errors:
            return {'success': False, 'price': 0.0,
                    'error_message': '\n'.join(errors), 'warning_message': False}
        try:
            client = self._pedidosya_get_client()
            response = client.estimate(payload)
        except UserError as exc:
            return {'success': False, 'price': 0.0,
                    'error_message': str(exc), 'warning_message': False}

        offer = self._pedidosya_select_offer(response)
        if not offer:
            return {'success': False, 'price': 0.0,
                    'error_message': _("PedidosYa no devolvió ofertas de envío "
                                       "para esta dirección."),
                    'warning_message': False}

        price = self._pedidosya_offer_price_in_currency(
            offer, order.currency_id, order.company_id,
            order.date_order or fields.Date.context_today(self))
        return {
            'success': True,
            'price': price,
            'error_message': False,
            'warning_message': '\n'.join(warnings) or False,
        }

    def pedidosya_send_shipping(self, pickings):
        self.ensure_one()
        client = self._pedidosya_get_client()
        result = []
        for picking in pickings:
            payload, errors = self._pedidosya_prepare_estimate_from_picking(picking)
            if errors:
                raise UserError(_("PedidosYa — no se puede crear el envío:\n%s")
                                % '\n'.join(errors))

            estimate = client.estimate(payload)
            offer = self._pedidosya_select_offer(estimate)
            if not offer:
                raise UserError(_("PedidosYa no devolvió ofertas para %s.")
                                % picking.name)
            confirmed = client.confirm_estimate(
                estimate.get('estimateId'), offer.get('deliveryOfferId'))

            shipping_id = confirmed.get('shippingId') or ''
            picking.write({
                'pedidosya_shipping_id': shipping_id,
                'pedidosya_status': confirmed.get('status') or 'CONFIRMED',
                'pedidosya_confirmation_code': confirmed.get('confirmationCode'),
                'pedidosya_tracking_url': confirmed.get('shareLocationUrl'),
            })
            price = self._pedidosya_offer_price_in_currency(
                offer,
                picking.sale_id.currency_id or picking.company_id.currency_id,
                picking.company_id, fields.Date.context_today(self))
            picking.message_post(body=_(
                "Envío PedidosYa creado.<br/>ID: <b>%(sid)s</b><br/>"
                "Código de confirmación: <b>%(code)s</b><br/>Costo: %(price).2f",
                sid=shipping_id,
                code=confirmed.get('confirmationCode') or '-',
                price=price))
            result.append({'exact_price': price, 'tracking_number': shipping_id})
        return result

    def pedidosya_get_tracking_link(self, picking):
        return picking.pedidosya_tracking_url or False

    def pedidosya_cancel_shipment(self, pickings):
        for picking in pickings:
            if not picking.pedidosya_shipping_id:
                continue
            client = picking.carrier_id._pedidosya_get_client()
            client.cancel_shipping(
                picking.pedidosya_shipping_id,
                _("Cancelado desde Odoo (%s)") % picking.name)
            picking.write({
                'pedidosya_status': 'CANCELLED',
                'carrier_tracking_ref': False,
            })
            picking.message_post(body=_("Envío PedidosYa cancelado."))

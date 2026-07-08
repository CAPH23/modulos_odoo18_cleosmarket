# -*- coding: utf-8 -*-
import base64
import json
import logging
import pprint
from datetime import timedelta

import requests
from werkzeug import urls

from odoo import _, api, fields, models, tools
from odoo.exceptions import ValidationError

from odoo.addons.payment_wompi_sv import const

_logger = logging.getLogger(__name__)


class PaymentProvider(models.Model):
    _inherit = 'payment.provider'

    code = fields.Selection(
        selection_add=[(const.PROVIDER_CODE, const.PROVIDER_NAME)],
        ondelete={const.PROVIDER_CODE: 'set default'},
    )

    # -------------------------------------------------------------------------
    # Credentials / API endpoints
    # -------------------------------------------------------------------------
    wompi_sv_client_id = fields.Char(
        string='Wompi Client ID / App ID',
        required_if_provider=const.PROVIDER_CODE,
        groups='base.group_system',
    )
    wompi_sv_client_secret = fields.Char(
        string='Wompi Client Secret',
        required_if_provider=const.PROVIDER_CODE,
        groups='base.group_system',
    )
    wompi_sv_api_secret = fields.Char(
        string='Wompi API Secret para Hash',
        required_if_provider=const.PROVIDER_CODE,
        groups='base.group_system',
        help='Se usa para validar el HMAC de Webhook y Redirect URL. En algunos comercios puede coincidir con el Client Secret.',
    )
    wompi_sv_oauth_url = fields.Char(
        string='URL OAuth Wompi',
        default=const.OAUTH_URL,
        required_if_provider=const.PROVIDER_CODE,
        groups='base.group_system',
    )
    wompi_sv_api_base_url = fields.Char(
        string='URL API Wompi',
        default=const.API_BASE_URL,
        required_if_provider=const.PROVIDER_CODE,
        groups='base.group_system',
    )
    wompi_sv_access_token = fields.Char(
        string='Wompi Access Token temporal',
        groups='base.group_system',
        copy=False,
    )
    wompi_sv_access_token_expiration = fields.Datetime(
        string='Expiración Access Token Wompi',
        groups='base.group_system',
        copy=False,
    )

    # -------------------------------------------------------------------------
    # Checkout / payment link configuration
    # -------------------------------------------------------------------------
    wompi_sv_payment_title = fields.Char(
        string='Título del pago en Wompi',
        default='Pedido {reference} - Super Tienda Cleo',
        help='Puedes usar {reference}, {amount}, {currency}, {order_name}.',
    )
    wompi_sv_notification_emails = fields.Char(
        string='Correos de notificación Wompi',
        help='Correos separados por coma. Se envían a Wompi como emailsNotificacion.',
    )
    wompi_sv_notify_customer = fields.Boolean(
        string='Notificar transacción al cliente desde Wompi',
        default=False,
    )
    wompi_sv_allow_amount_edit = fields.Boolean(
        string='Permitir editar monto en Wompi',
        default=False,
    )
    wompi_sv_allow_quantity_edit = fields.Boolean(
        string='Permitir editar cantidad en Wompi',
        default=False,
    )
    wompi_sv_default_quantity = fields.Integer(
        string='Cantidad por defecto',
        default=1,
    )
    wompi_sv_payment_link_duration_minutes = fields.Integer(
        string='Minutos disponibles en interfaz de pago',
        default=30,
    )
    wompi_sv_max_successful_payments = fields.Integer(
        string='Límite de pagos exitosos',
        default=1,
        help='1 significa que el enlace solo se puede pagar una vez.',
    )
    wompi_sv_max_failed_attempts = fields.Integer(
        string='Límite de intentos fallidos',
        default=3,
    )
    wompi_sv_card_group_id = fields.Char(
        string='ID grupo de tarjetas Wompi',
        help='Opcional. Restricción de tarjetas si Wompi la tiene configurada.',
    )

    # -------------------------------------------------------------------------
    # Payment methods
    # -------------------------------------------------------------------------
    wompi_sv_allow_card = fields.Boolean(
        string='Permitir tarjeta crédito/débito',
        default=True,
    )
    wompi_sv_allow_points = fields.Boolean(
        string='Permitir puntos Banco Agrícola',
        default=False,
    )
    wompi_sv_allow_installments = fields.Boolean(
        string='Permitir cuotas Banco Agrícola',
        default=False,
    )
    wompi_sv_max_installments = fields.Integer(
        string='Cantidad máxima de cuotas',
        default=0,
        help='Se envía solo si “Permitir cuotas” está activo y el valor es mayor que 0.',
    )
    wompi_sv_allow_bitcoin = fields.Boolean(
        string='Permitir Bitcoin',
        default=False,
    )
    wompi_sv_allow_quickpay = fields.Boolean(
        string='Permitir QuickPay',
        default=False,
    )

    # -------------------------------------------------------------------------
    # Product information sent to Wompi
    # -------------------------------------------------------------------------
    wompi_sv_send_product_info = fields.Boolean(
        string='Enviar información del pedido a Wompi',
        default=True,
    )
    wompi_sv_product_image_url = fields.Char(
        string='URL imagen principal para Wompi',
        help='Debe ser una URL pública HTTPS. Si se deja vacío, se usa el banner incluido en el módulo.',
    )
    wompi_sv_include_order_lines = fields.Boolean(
        string='Incluir resumen de productos',
        default=True,
    )
    wompi_sv_max_order_lines = fields.Integer(
        string='Máximo de líneas de producto en descripción',
        default=5,
    )
    wompi_sv_description_footer = fields.Text(
        string='Texto final de descripción',
        default='Pago seguro procesado por Wompi El Salvador\nRecibirá la confirmación de su pedido en cleosmarket.com',
    )

    # -------------------------------------------------------------------------
    # Capabilities, webhook and debugging
    # -------------------------------------------------------------------------
    wompi_sv_allow_webhook_api_fallback = fields.Boolean(
        string='Permitir validación por API si webhook llega sin wompi_hash',
        default=True,
        help='Si Nginx o un proxy elimina el header wompi_hash, Odoo consultará TransaccionCompra para validar referencia, monto y estado.',
    )
    wompi_sv_debug_logging = fields.Boolean(
        string='Activar logs de depuración Wompi',
        default=False,
    )
    wompi_sv_capabilities_last_sync = fields.Datetime(
        string='Última consulta /Aplicativo',
        readonly=True,
        copy=False,
    )
    wompi_sv_supports_points = fields.Boolean(
        string='Cuenta Wompi permite puntos',
        readonly=True,
        copy=False,
    )
    wompi_sv_available_installments = fields.Char(
        string='Cuotas disponibles detectadas',
        readonly=True,
        copy=False,
    )
    wompi_sv_raw_capabilities = fields.Text(
        string='Respuesta /Aplicativo',
        readonly=True,
        copy=False,
    )

    # -------------------------------------------------------------------------
    # Odoo payment provider hooks
    # -------------------------------------------------------------------------
    def _get_supported_currencies(self):
        supported_currencies = super()._get_supported_currencies()
        if self.code == const.PROVIDER_CODE:
            supported_currencies = supported_currencies.filtered(lambda c: c.name in const.SUPPORTED_CURRENCIES)
        return supported_currencies

    def _get_default_payment_method_codes(self):
        default_codes = super()._get_default_payment_method_codes()
        if self.code != const.PROVIDER_CODE:
            return default_codes
        return const.DEFAULT_PAYMENT_METHOD_CODES

    def _get_redirect_form_view(self, is_validation=False):
        self.ensure_one()
        if self.code == const.PROVIDER_CODE:
            return self.env.ref('payment_wompi_sv.redirect_form')
        return super()._get_redirect_form_view(is_validation=is_validation)

    # -------------------------------------------------------------------------
    # Default setup
    # -------------------------------------------------------------------------
    @api.model
    def _wompi_sv_apply_default_v2_settings(self):
        providers = self.sudo().search([('code', '=', const.PROVIDER_CODE)])
        for provider in providers:
            vals = {}
            defaults = {
                'wompi_sv_oauth_url': const.OAUTH_URL,
                'wompi_sv_api_base_url': const.API_BASE_URL,
                'wompi_sv_payment_title': 'Pedido {reference} - Super Tienda Cleo',
                'wompi_sv_default_quantity': 1,
                'wompi_sv_payment_link_duration_minutes': 30,
                'wompi_sv_max_successful_payments': 1,
                'wompi_sv_max_failed_attempts': 3,
                'wompi_sv_max_order_lines': 5,
                'wompi_sv_description_footer': 'Pago seguro procesado por Wompi El Salvador\nRecibirá la confirmación de su pedido en cleosmarket.com',
            }
            for field_name, value in defaults.items():
                if not provider[field_name]:
                    vals[field_name] = value
            if provider.wompi_sv_allow_card is False and not provider.wompi_sv_allow_points and not provider.wompi_sv_allow_installments and not provider.wompi_sv_allow_bitcoin:
                vals['wompi_sv_allow_card'] = True
            if vals:
                provider.write(vals)
        return True

    @api.model
    def _wompi_sv_create_and_attach_payment_method(self):
        """Create and attach a Wompi-only payment method.

        Important:
        The core payment method with code ``card`` is shared by other providers.
        Previous versions of this module wrote the Wompi card-logo image into that
        shared record, so other payment methods could unexpectedly display the
        Wompi/Visa/Mastercard strip in ``/shop/payment``.
        """
        provider = self.sudo().search([('code', '=', const.PROVIDER_CODE)], limit=1)
        PaymentMethod = self.env['payment.method'].sudo()
        wompi_card_method = PaymentMethod.search([('code', '=', 'wompi_sv_card')], limit=1)
        shared_card_method = PaymentMethod.search([('code', '=', 'card')], limit=1)

        if not wompi_card_method:
            method_vals = {'name': 'Tarjeta de crédito o débito', 'code': 'wompi_sv_card'}
            if 'active' in PaymentMethod._fields:
                method_vals['active'] = True
            if 'sequence' in PaymentMethod._fields:
                method_vals['sequence'] = 10
            wompi_card_method = PaymentMethod.create(method_vals)

        if not provider:
            return True

        country_sv = self.env['res.country'].sudo().search([('code', '=', 'SV')], limit=1)
        currency_usd = self.env.ref('base.USD', raise_if_not_found=False) or self.env['res.currency'].sudo().search([('name', '=', 'USD')], limit=1)

        provider_vals = {}
        payment_method_commands = [(4, wompi_card_method.id)]
        # Remove only the relation between Wompi and Odoo's shared card method.
        # Do not delete or modify the shared record because other providers may use it.
        if shared_card_method:
            payment_method_commands.append((3, shared_card_method.id))
        provider_vals['payment_method_ids'] = payment_method_commands
        if country_sv and 'available_country_ids' in provider._fields:
            provider_vals['available_country_ids'] = [(6, 0, [country_sv.id])]
        if currency_usd and 'available_currency_ids' in provider._fields:
            provider_vals['available_currency_ids'] = [(6, 0, [currency_usd.id])]
        if provider_vals:
            provider.write(provider_vals)

        self._wompi_sv_load_and_write_image_if_possible(provider, 'payment_wompi_sv/static/src/img/wompi_logo.png', 'proveedor de pago Wompi')
        self._wompi_sv_load_and_write_image_if_possible(wompi_card_method, 'payment_wompi_sv/static/src/img/tarjeta_de_credito.png', 'método de pago Wompi Tarjeta')
        self._wompi_sv_cleanup_shared_card_image_if_possible(shared_card_method)
        return True

    @api.model
    def _wompi_sv_cleanup_shared_card_image_if_possible(self, card_method):
        """Undo the image written by old module versions on the shared ``card`` method.

        The cleanup is intentionally conservative: it clears the image only when
        the current binary value exactly matches the bundled Wompi card-logo file.
        This avoids deleting a legitimate custom logo configured by another
        payment provider.
        """
        if not card_method:
            return False
        try:
            with tools.file_open('payment_wompi_sv/static/src/img/tarjeta_de_credito.png', 'rb') as image_file:
                wompi_card_image_b64 = base64.b64encode(image_file.read())
        except Exception as exc:
            _logger.warning('No se pudo cargar la imagen Wompi para limpiar el método global card: %s', exc)
            return False

        def _as_bytes(value):
            if isinstance(value, bytes):
                return value
            if isinstance(value, str):
                return value.encode('ascii', errors='ignore')
            return b''

        cleaned = False
        for field_name in ['image_1920', 'image_1024', 'image_512', 'image_256', 'image_128', 'image']:
            if field_name not in card_method._fields:
                continue
            current = _as_bytes(card_method[field_name])
            if current and current == wompi_card_image_b64:
                try:
                    card_method.sudo().write({field_name: False})
                    cleaned = True
                    _logger.info('Wompi: se limpió la imagen del método de pago global card.%s porque correspondía a la imagen Wompi anterior.', field_name)
                except Exception as exc:
                    _logger.warning('No se pudo limpiar la imagen del método global card.%s: %s', field_name, exc)
        return cleaned

    @api.model
    def _wompi_sv_load_and_write_image_if_possible(self, record, image_path, description):
        if not record or not image_path:
            return False
        try:
            with tools.file_open(image_path, 'rb') as image_file:
                image_b64 = base64.b64encode(image_file.read())
        except Exception as exc:
            _logger.warning('No se pudo cargar la imagen para %s desde %s: %s', description, image_path, exc)
            return False
        return self._wompi_sv_write_image_if_possible(record, image_b64)

    @api.model
    def _wompi_sv_write_image_if_possible(self, record, image_b64):
        if not record or not image_b64:
            return False
        for field_name in ['image_1920', 'image_1024', 'image_512', 'image_256', 'image_128', 'image']:
            if field_name in record._fields:
                try:
                    record.sudo().write({field_name: image_b64})
                    return True
                except Exception as exc:
                    _logger.warning('No se pudo escribir imagen en %s.%s: %s', record._name, field_name, exc)
        return False

    # -------------------------------------------------------------------------
    # Logging helpers
    # -------------------------------------------------------------------------
    def _wompi_sv_log(self, level, message, *args):
        self.ensure_one()
        if level in ('debug', 'info') and not self.wompi_sv_debug_logging:
            return
        logger = getattr(_logger, level, _logger.info)
        logger(message, *args)

    # -------------------------------------------------------------------------
    # Wompi API helpers
    # -------------------------------------------------------------------------
    def _wompi_sv_get_hmac_secret(self):
        self.ensure_one()
        return self.wompi_sv_api_secret or self.wompi_sv_client_secret

    def _wompi_sv_get_access_token(self, force_refresh=False):
        self.ensure_one()
        now = fields.Datetime.now()
        if not force_refresh and self.wompi_sv_access_token and self.wompi_sv_access_token_expiration and self.wompi_sv_access_token_expiration > now:
            return self.wompi_sv_access_token

        if not self.wompi_sv_client_id or not self.wompi_sv_client_secret:
            raise ValidationError(_('Wompi: configure Client ID and Client Secret before enabling payments.'))

        oauth_url = self.wompi_sv_oauth_url or const.OAUTH_URL
        data = {
            'grant_type': 'client_credentials',
            'client_id': self.wompi_sv_client_id,
            'client_secret': self.wompi_sv_client_secret,
            'audience': 'wompi_api',
        }
        headers = {'content-type': 'application/x-www-form-urlencoded'}

        try:
            response = requests.post(oauth_url, data=data, headers=headers, timeout=20)
            response.raise_for_status()
            content = response.json()
        except requests.exceptions.HTTPError as error:
            _logger.exception('Wompi OAuth HTTP error at %s', oauth_url)
            raise ValidationError(_('Wompi: OAuth authentication failed. Verify the Client ID and Client Secret.')) from error
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as error:
            _logger.exception('Wompi OAuth connection error at %s', oauth_url)
            raise ValidationError(_('Wompi: could not connect to the OAuth server.')) from error
        except ValueError as error:
            _logger.exception('Wompi OAuth invalid JSON response at %s', oauth_url)
            raise ValidationError(_('Wompi: OAuth server returned an invalid response.')) from error

        access_token = content.get('access_token')
        expires_in = int(content.get('expires_in') or 3600)
        if not access_token:
            raise ValidationError(_('Wompi: OAuth response did not include an access token.'))

        expiration = fields.Datetime.to_string(fields.Datetime.now() + timedelta(seconds=max(expires_in - 120, 60)))
        self.sudo().write({
            'wompi_sv_access_token': access_token,
            'wompi_sv_access_token_expiration': expiration,
        })
        return access_token

    def _wompi_sv_make_request(self, endpoint, payload=None, method='POST', reference=None, timeout=25):
        self.ensure_one()
        access_token = self._wompi_sv_get_access_token()
        api_base_url = self.wompi_sv_api_base_url or const.API_BASE_URL
        url = urls.url_join(api_base_url, endpoint)
        headers = {
            'authorization': f'Bearer {access_token}',
            'content-type': 'application/json',
        }

        self._wompi_sv_log('info', 'Sending Wompi request %s %s for reference %s:\n%s', method, url, reference, pprint.pformat(payload))
        try:
            if method.upper() == 'GET':
                response = requests.get(url, params=payload, headers=headers, timeout=timeout)
            else:
                response = requests.post(url, json=payload, headers=headers, timeout=timeout)
            response.raise_for_status()
            if not response.content:
                return {}
            return response.json()
        except requests.exceptions.HTTPError as error:
            try:
                error_content = response.json()
            except Exception:
                error_content = response.text
            _logger.exception('Wompi API error at %s with response:\n%s', url, pprint.pformat(error_content))
            raise ValidationError(_('Wompi: the API request failed. Review the Odoo logs for details.')) from error
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as error:
            _logger.exception('Wompi API connection error at %s', url)
            raise ValidationError(_('Wompi: could not connect to the API.')) from error
        except ValueError as error:
            _logger.exception('Wompi API invalid JSON response at %s', url)
            raise ValidationError(_('Wompi: API returned an invalid response.')) from error

    def _wompi_sv_get_application_capabilities(self):
        self.ensure_one()
        return self._wompi_sv_make_request(const.API_APPLICATION_ENDPOINT, method='GET', reference='Aplicativo', timeout=20)

    def _wompi_sv_sync_capabilities(self):
        self.ensure_one()
        data = self._wompi_sv_get_application_capabilities() or {}
        cuotas = data.get('cuotasDisponibles') or data.get('CuotasDisponibles') or []
        cuotas_labels = []
        for item in cuotas:
            if isinstance(item, dict):
                qty = item.get('cantidadCuotas') or item.get('CantidadCuotas')
                tasa = item.get('tasa') or item.get('Tasa')
                if qty:
                    cuotas_labels.append('%s cuotas%s' % (qty, (' (%s%%)' % tasa) if tasa is not None else ''))
            else:
                cuotas_labels.append(str(item))

        points = data.get('aplicaPagoConPuntos')
        if points is None:
            points = data.get('AplicaPagoConPuntos')

        vals = {
            'wompi_sv_capabilities_last_sync': fields.Datetime.now(),
            'wompi_sv_supports_points': bool(points),
            'wompi_sv_available_installments': ', '.join(cuotas_labels),
            'wompi_sv_raw_capabilities': json.dumps(data, ensure_ascii=False, indent=2),
        }
        self.write(vals)
        return data

    def action_wompi_sv_test_connection(self):
        for provider in self:
            provider.ensure_one()
            provider._wompi_sv_get_access_token(force_refresh=True)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Wompi'),
                'message': _('Conexión OAuth correcta. Token obtenido correctamente.'),
                'type': 'success',
                'sticky': False,
            },
        }

    def action_wompi_sv_sync_capabilities(self):
        for provider in self:
            provider._wompi_sv_sync_capabilities()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Wompi'),
                'message': _('Capacidades del aplicativo actualizadas desde Wompi.'),
                'type': 'success',
                'sticky': False,
            },
        }

    def action_wompi_sv_clear_token(self):
        self.write({
            'wompi_sv_access_token': False,
            'wompi_sv_access_token_expiration': False,
        })
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Wompi'),
                'message': _('Token temporal limpiado.'),
                'type': 'info',
                'sticky': False,
            },
        }

    # -------------------------------------------------------------------------
    # Payload helpers
    # -------------------------------------------------------------------------
    def _wompi_sv_get_base_url(self):
        self.ensure_one()
        base_url = ''
        try:
            base_url = self.get_base_url()
        except Exception:
            base_url = ''
        if not base_url:
            base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url') or ''
        return base_url.rstrip('/')

    def _wompi_sv_get_public_banner_url(self):
        self.ensure_one()
        base_url = self._wompi_sv_get_base_url()
        return self.wompi_sv_product_image_url or '%s/payment_wompi_sv/static/src/img/wompi_payment_banner.png' % base_url

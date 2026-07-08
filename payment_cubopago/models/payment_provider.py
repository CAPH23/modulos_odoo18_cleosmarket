# -*- coding: utf-8 -*-
# Part of the CuboPago payment module.
# Copyright 2026 Carlos Palacios
# License OPL-1 (Odoo Proprietary License v1.0). See LICENSE file for full details.
import base64
import logging
import pprint

import requests
from werkzeug import urls

from odoo import _, api, fields, models, tools
from odoo.exceptions import ValidationError

from odoo.addons.payment_cubopago import const

_logger = logging.getLogger(__name__)


class PaymentProvider(models.Model):
    _inherit = 'payment.provider'

    code = fields.Selection(
        selection_add=[(const.PROVIDER_CODE, const.PROVIDER_NAME)],
        ondelete={const.PROVIDER_CODE: 'set default'},
    )

    # -------------------------------------------------------------------------
    # Credentials per environment (SANDBOX / PRODUCTION)
    # -------------------------------------------------------------------------
    cubopago_api_key_test = fields.Char(
        string='CuboPago API Key (Sandbox)',
        groups='base.group_system',
        help='API Key generada en Cubo Admin para el entorno SANDBOX. '
             'Se usa cuando el proveedor está en modo de prueba.',
    )
    cubopago_api_key_prod = fields.Char(
        string='CuboPago API Key (Producción)',
        groups='base.group_system',
        help='API Key generada en Cubo Admin para el entorno de PRODUCCIÓN. '
             'Se usa cuando el proveedor está habilitado.',
    )
    cubopago_api_url_test = fields.Char(
        string='URL API CuboPago (Sandbox)',
        default=const.DEFAULT_API_URL_TEST,
        groups='base.group_system',
        help='URL base de la API CuboPago para SANDBOX. Confirma el valor exacto '
             'con CuboPago, ya que puede variar.',
    )
    cubopago_api_url_prod = fields.Char(
        string='URL API CuboPago (Producción)',
        default=const.DEFAULT_API_URL_PROD,
        groups='base.group_system',
        help='URL base de la API CuboPago para PRODUCCIÓN. Confirma el valor exacto '
             'con CuboPago, ya que puede variar.',
    )

    # -------------------------------------------------------------------------
    # Payment link configuration
    # -------------------------------------------------------------------------
    cubopago_payment_description = fields.Char(
        string='Descripción del pago',
        default='Pedido {reference}',
        help='Puedes usar {reference}, {amount}, {currency}, {order_name}.',
    )
    cubopago_send_items = fields.Boolean(
        string='Enviar detalle de productos',
        default=True,
        help='Incluye el array items (nombre, precio, cantidad) en el link de pago.',
    )
    cubopago_max_items = fields.Integer(
        string='Máximo de productos a enviar',
        default=20,
    )
    cubopago_send_client_info = fields.Boolean(
        string='Enviar datos del cliente',
        default=True,
        help='Precarga nombre, correo y teléfono del cliente en el link de pago.',
    )
    cubopago_monthly_installment_id = fields.Integer(
        string='ID plan meses sin intereses',
        default=0,
        help='Opcional. ID del plan de meses sin intereses a aplicar. '
             'Se envía solo si es mayor que 0. Respeta el monto mínimo del plan.',
    )

    # -------------------------------------------------------------------------
    # Behaviour / debugging
    # -------------------------------------------------------------------------
    cubopago_debug_logging = fields.Boolean(
        string='Activar logs de depuración CuboPago',
        default=False,
    )

    # Display-only webhook URL computed from the instance base URL, so the
    # merchant can copy it into the Developers section of Cubo Admin.
    cubopago_webhook_url = fields.Char(
        string='URL Webhook (configurar en Cubo Admin)',
        compute='_compute_cubopago_webhook_url',
    )

    @api.depends('code')
    def _compute_cubopago_webhook_url(self):
        for provider in self:
            base_url = ''
            if provider.code == const.PROVIDER_CODE:
                base_url = provider._cubopago_get_base_url()
            provider.cubopago_webhook_url = ('%s/payment/cubopago/webhook' % base_url) if base_url else ''

    # -------------------------------------------------------------------------
    # Odoo payment provider hooks
    # -------------------------------------------------------------------------
    def _get_supported_currencies(self):
        supported_currencies = super()._get_supported_currencies()
        if self.code == const.PROVIDER_CODE:
            supported_currencies = supported_currencies.filtered(
                lambda c: c.name in const.SUPPORTED_CURRENCIES
            )
        return supported_currencies

    def _get_default_payment_method_codes(self):
        default_codes = super()._get_default_payment_method_codes()
        if self.code != const.PROVIDER_CODE:
            return default_codes
        return const.DEFAULT_PAYMENT_METHOD_CODES

    def _get_redirect_form_view(self, is_validation=False):
        self.ensure_one()
        if self.code == const.PROVIDER_CODE:
            return self.env.ref('payment_cubopago.redirect_form')
        return super()._get_redirect_form_view(is_validation=is_validation)

    # -------------------------------------------------------------------------
    # Environment helpers
    # -------------------------------------------------------------------------
    def _cubopago_is_production(self):
        """CuboPago uses production credentials when the provider is enabled,
        and sandbox credentials when the provider is in test mode."""
        self.ensure_one()
        return self.state == 'enabled'

    def _cubopago_get_api_key(self):
        self.ensure_one()
        if self._cubopago_is_production():
            return self.cubopago_api_key_prod
        return self.cubopago_api_key_test

    def _cubopago_get_api_url(self):
        self.ensure_one()
        if self._cubopago_is_production():
            return (self.cubopago_api_url_prod or const.DEFAULT_API_URL_PROD).rstrip('/')
        return (self.cubopago_api_url_test or const.DEFAULT_API_URL_TEST).rstrip('/')

    def _cubopago_get_base_url(self):
        self.ensure_one()
        base_url = ''
        try:
            base_url = self.get_base_url()
        except Exception:
            base_url = ''
        if not base_url:
            base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url') or ''
        return base_url.rstrip('/')

    # -------------------------------------------------------------------------
    # Logging helper
    # -------------------------------------------------------------------------
    def _cubopago_log(self, level, message, *args):
        self.ensure_one()
        if level in ('debug', 'info') and not self.cubopago_debug_logging:
            return
        logger = getattr(_logger, level, _logger.info)
        logger(message, *args)

    # -------------------------------------------------------------------------
    # API request helper
    # -------------------------------------------------------------------------
    def _cubopago_make_request(self, endpoint, payload=None, method='POST', reference=None, timeout=25):
        self.ensure_one()
        api_key = self._cubopago_get_api_key()
        if not api_key:
            raise ValidationError(_('CuboPago: configure la API Key antes de procesar pagos.'))

        url = urls.url_join(self._cubopago_get_api_url() + '/', endpoint.lstrip('/'))
        headers = {
            'X-API-KEY': api_key,
            'Content-Type': 'application/json',
        }

        self._cubopago_log(
            'info', 'CuboPago request %s %s (ref %s):\n%s',
            method, url, reference, pprint.pformat(payload),
        )
        try:
            if method.upper() == 'GET':
                response = requests.get(url, headers=headers, timeout=timeout)
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
            _logger.exception('CuboPago API error at %s:\n%s', url, pprint.pformat(error_content))
            raise ValidationError(_('CuboPago: la solicitud a la API falló. Revise los logs de Odoo.')) from error
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as error:
            _logger.exception('CuboPago API connection error at %s', url)
            raise ValidationError(_('CuboPago: no se pudo conectar con la API.')) from error
        except ValueError as error:
            _logger.exception('CuboPago API invalid JSON response at %s', url)
            raise ValidationError(_('CuboPago: la API devolvió una respuesta inválida.')) from error

    def _cubopago_fetch_transaction(self, payment_intent_token, reference=None):
        """Server-to-server verification of a transaction by its token."""
        self.ensure_one()
        if not payment_intent_token:
            return {}
        return self._cubopago_make_request(
            const.ENDPOINT_TRANSACTION % payment_intent_token,
            method='GET',
            reference=reference,
        )

    # -------------------------------------------------------------------------
    # Connection test
    # -------------------------------------------------------------------------
    def action_cubopago_test_connection(self):
        for provider in self:
            provider.ensure_one()
            api_key = provider._cubopago_get_api_key()
            if not api_key:
                raise ValidationError(_('CuboPago: configure la API Key del entorno actual primero.'))
            # Reaching the transactions endpoint with a dummy token lets us tell
            # apart an authentication problem (401/403) from a reachable API
            # (404 = token not found, which means the key was accepted).
            url = urls.url_join(
                provider._cubopago_get_api_url() + '/',
                (const.ENDPOINT_TRANSACTION % '__ping__').lstrip('/'),
            )
            headers = {'X-API-KEY': api_key}
            try:
                response = requests.get(url, headers=headers, timeout=20)
            except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as error:
                raise ValidationError(_('CuboPago: no se pudo conectar con %s.', url)) from error
            if response.status_code in (401, 403):
                raise ValidationError(_('CuboPago: la API Key fue rechazada (HTTP %s).', response.status_code))
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('CuboPago'),
                'message': _('Conexión correcta: la API respondió y la API Key fue aceptada.'),
                'type': 'success',
                'sticky': False,
            },
        }

    # -------------------------------------------------------------------------
    # Payment method setup
    # -------------------------------------------------------------------------
    @api.model
    def _cubopago_create_and_attach_payment_method(self):
        """Create and attach a CuboPago-only payment method.

        We never modify Odoo's shared 'card' method, which may be used by other
        providers; instead we create a dedicated 'cubopago' method.
        """
        provider = self.sudo().search([('code', '=', const.PROVIDER_CODE)], limit=1)
        PaymentMethod = self.env['payment.method'].sudo()
        method = PaymentMethod.search([('code', '=', 'cubopago')], limit=1)

        if not method:
            method_vals = {'name': 'CuboPago', 'code': 'cubopago'}
            if 'active' in PaymentMethod._fields:
                method_vals['active'] = True
            if 'sequence' in PaymentMethod._fields:
                method_vals['sequence'] = 10
            method = PaymentMethod.create(method_vals)

        if not provider:
            return True

        country_sv = self.env['res.country'].sudo().search([('code', '=', 'SV')], limit=1)
        currency_usd = self.env.ref('base.USD', raise_if_not_found=False) \
            or self.env['res.currency'].sudo().search([('name', '=', 'USD')], limit=1)

        provider_vals = {'payment_method_ids': [(4, method.id)]}
        if country_sv and 'available_country_ids' in provider._fields:
            provider_vals['available_country_ids'] = [(6, 0, [country_sv.id])]
        if currency_usd and 'available_currency_ids' in provider._fields:
            provider_vals['available_currency_ids'] = [(6, 0, [currency_usd.id])]
        provider.write(provider_vals)

        self._cubopago_load_logo(provider, 'payment_cubopago/static/description/icon.png')
        self._cubopago_load_logo(method, 'payment_cubopago/static/description/icon.png')
        return True

    @api.model
    def _cubopago_load_logo(self, record, image_path):
        if not record or not image_path:
            return False
        try:
            with tools.file_open(image_path, 'rb') as image_file:
                image_b64 = base64.b64encode(image_file.read())
        except Exception as exc:
            _logger.warning('CuboPago: no se pudo cargar el logo desde %s: %s', image_path, exc)
            return False
        for field_name in ['image_1920', 'image_1024', 'image_512', 'image_256', 'image_128', 'image']:
            if field_name in record._fields:
                try:
                    record.sudo().write({field_name: image_b64})
                    return True
                except Exception as exc:
                    _logger.warning('CuboPago: no se pudo escribir el logo en %s.%s: %s', record._name, field_name, exc)
        return False

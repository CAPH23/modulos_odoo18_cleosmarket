# -*- coding: utf-8 -*-
import hmac
import json
import logging
import pprint
from hashlib import sha256

from odoo import http
from odoo.http import request

from odoo.addons.payment_wompi_sv import const

_logger = logging.getLogger(__name__)


class WompiSVController(http.Controller):
    _return_url = '/payment/wompi_sv/return'
    _webhook_url = '/payment/wompi_sv/webhook'

    @http.route(
        '/payment_wompi_sv/payment_method_logo_info',
        type='http',
        auth='public',
        methods=['GET'],
        csrf=False,
        website=True,
        sitemap=False,
    )
    def wompi_sv_payment_method_logo_info(self, **_kwargs):
        """Return the Wompi-only payment method ID and the original HD logo path.

        The checkout template can render payment.method thumbnails through resized
        image fields. The frontend script uses this endpoint to target only the
        custom Wompi method and replace its thumbnail with the bundled original
        image, without touching Odoo global payment methods or other providers.
        """
        method = request.env['payment.method'].sudo().search([('code', '=', 'wompi_sv_card')], limit=1)
        payload = {
            'payment_method_id': method.id if method else False,
            'logo_url': '/payment_wompi_sv/static/src/img/tarjeta_de_credito.png',
        }
        return request.make_response(
            json.dumps(payload),
            headers=[
                ('Content-Type', 'application/json; charset=utf-8'),
                ('Cache-Control', 'no-store'),
            ],
        )

    @http.route(
        _return_url,
        type='http',
        methods=['GET', 'POST'],
        auth='public',
        csrf=False,
        website=True,
    )
    def wompi_sv_return_from_checkout(self, **data):
        _logger.info('Wompi return received:\n%s', pprint.pformat(data))
        try:
            if data.get('hash') and self._validate_redirect_hash(data):
                data['_wompi_sv_source'] = 'return'
                request.env['payment.transaction'].sudo()._handle_notification_data(const.PROVIDER_CODE, data)
            else:
                _logger.warning('Wompi return received without valid redirect hash:\n%s', pprint.pformat(data))
        except Exception:
            _logger.exception('Error procesando retorno Wompi. Se redirige a /payment/status.')
        return request.redirect('/payment/status')

    @http.route(
        _webhook_url,
        type='http',
        auth='public',
        methods=['POST'],
        csrf=False,
    )
    def wompi_sv_webhook(self, **_kwargs):
        raw_body = request.httprequest.get_data(cache=True) or b''
        wompi_hash = self._get_wompi_hash_from_request()
        _logger.info('Wompi webhook received. Body length: %s | Hash present: %s', len(raw_body), bool(wompi_hash))

        try:
            data = json.loads(raw_body.decode('utf-8')) if raw_body else {}
        except Exception:
            _logger.exception('Wompi webhook rejected: invalid JSON body.')
            return request.make_response('invalid json', status=400)

        if not data:
            _logger.warning('Wompi webhook rejected: empty JSON body.')
            return request.make_response('empty payload', status=400)

        provider = self._get_provider_matching_hash(raw_body, wompi_hash)
        if provider:
            data['_wompi_sv_source'] = 'webhook'
            data['_wompi_sv_webhook_hash'] = wompi_hash
            provider._wompi_sv_log('info', 'Validated Wompi webhook data:\n%s', pprint.pformat(data))
            return self._process_webhook_data(data)

        # Safe fallback inspired by the official WooCommerce plugin behavior:
        # when a proxy strips wompi_hash, verify the transaction through Wompi API
        # before letting Odoo process it.
        fallback_tx = self._find_transaction_from_data(data)
        if fallback_tx and fallback_tx.provider_id.wompi_sv_allow_webhook_api_fallback:
            if self._validate_webhook_by_api(fallback_tx, data):
                data['_wompi_sv_source'] = 'webhook_api_fallback'
                data['_wompi_sv_webhook_hash'] = wompi_hash or ''
                _logger.warning(
                    'Wompi webhook accepted by API fallback for transaction %s because wompi_hash was missing or invalid.',
                    fallback_tx.reference,
                )
                return self._process_webhook_data(data)

        _logger.warning('Wompi webhook rejected: invalid or missing wompi_hash header.')
        return request.make_response('invalid hash', status=403)

    def _process_webhook_data(self, data):
        try:
            request.env['payment.transaction'].sudo()._handle_notification_data(const.PROVIDER_CODE, data)
        except Exception:
            _logger.exception('Error procesando webhook Wompi. Se responde OK para evitar reintentos infinitos.')
        return request.make_response('ok', status=200)

    def _get_wompi_hash_from_request(self):
        headers = request.httprequest.headers
        environ = request.httprequest.environ
        candidates = [
            headers.get('wompi_hash'),
            headers.get('Wompi-Hash'),
            headers.get('WompiHash'),
            headers.get('Wompi_hash'),
            headers.get('Wompi_Hash'),
            environ.get('HTTP_WOMPI_HASH'),
            environ.get('HTTP_WOMPIHASH'),
        ]
        for value in candidates:
            if value:
                return str(value).strip()
        return ''

    def _get_provider_matching_hash(self, raw_body, wompi_hash):
        if not wompi_hash:
            return None
        received_hash = str(wompi_hash).strip().lower()
        providers = request.env['payment.provider'].sudo().search([
            ('code', '=', const.PROVIDER_CODE),
            ('state', '!=', 'disabled'),
        ])
        for provider in providers:
            secret = provider._wompi_sv_get_hmac_secret()
            if not secret:
                continue
            expected_hash = hmac.new(str(secret).encode('utf-8'), raw_body, sha256).hexdigest().lower()
            if hmac.compare_digest(expected_hash, received_hash):
                return provider
        return None

    def _find_transaction_from_data(self, data):
        reference = self._extract_reference(data)
        if not reference:
            return request.env['payment.transaction'].sudo()
        return request.env['payment.transaction'].sudo().search([
            ('reference', '=', reference),
            ('provider_code', '=', const.PROVIDER_CODE),
        ], limit=1)

    def _validate_webhook_by_api(self, tx, data):
        id_transaccion = self._extract_transaction_id(data)
        if not id_transaccion:
            _logger.warning('Wompi webhook fallback rejected: no IdTransaccion for %s.', tx.reference)
            return False

        try:
            api_data = tx.provider_id._wompi_sv_make_request(
                const.API_TRANSACTION_ENDPOINT % id_transaccion,
                method='GET',
                reference=tx.reference,
            )
        except Exception:
            _logger.exception('Wompi webhook fallback rejected: API validation failed for %s.', tx.reference)
            return False

        amount = self._extract_amount(api_data) or self._extract_amount(data)
        try:
            amount = float(amount)
        except (TypeError, ValueError):
            amount = None
        if amount is None or tx.currency_id.compare_amounts(amount, tx.amount) != 0:
            _logger.warning('Wompi webhook fallback rejected: amount mismatch for %s. API/data: %s, Odoo: %s', tx.reference, amount, tx.amount)
            return False

        reference = self._extract_reference(api_data) or self._extract_reference(data)
        if reference and str(reference) != str(tx.reference):
            _logger.warning('Wompi webhook fallback rejected: reference mismatch. API/data: %s, Odoo: %s', reference, tx.reference)
            return False

        approved = self._extract_approved_flag(api_data)
        result = self._extract_result(api_data)
        if approved is True or str(result or '').strip().lower() in ('exitosaaprobada', 'aprobada', 'approved', 'paid', 'success', 'successful'):
            data['_wompi_sv_api_data'] = api_data
            return True

        _logger.warning('Wompi webhook fallback rejected: transaction not approved for %s. API: %s', tx.reference, pprint.pformat(api_data))
        return False

    def _validate_redirect_hash(self, data):
        received_hash = data.get('hash')
        if not received_hash:
            return False

        reference = data.get('identificadorEnlaceComercio') or data.get('IdentificadorEnlaceComercio')
        tx = request.env['payment.transaction'].sudo().search([
            ('reference', '=', reference),
            ('provider_code', '=', const.PROVIDER_CODE),
        ], limit=1)
        if not tx:
            _logger.warning('Wompi redirect hash validation failed: no transaction for reference %s', reference)
            return False

        secret = tx.provider_id._wompi_sv_get_hmac_secret()
        concatenated = ''.join([
            str(data.get('identificadorEnlaceComercio') or data.get('IdentificadorEnlaceComercio') or ''),
            str(data.get('idTransaccion') or data.get('IdTransaccion') or ''),
            str(data.get('idEnlace') or data.get('IdEnlace') or ''),
            str(data.get('monto') or data.get('Monto') or ''),
        ])
        expected_hash = hmac.new(str(secret).encode('utf-8'), concatenated.encode('utf-8'), sha256).hexdigest().lower()
        return hmac.compare_digest(expected_hash, str(received_hash).strip().lower())

    def _extract_reference(self, data):
        enlace = self._get_value(data, 'EnlacePago', 'enlacePago') or {}
        return (
            self._get_value(data, 'identificadorEnlaceComercio', 'IdentificadorEnlaceComercio')
            or self._get_value(enlace, 'identificadorEnlaceComercio', 'IdentificadorEnlaceComercio')
            or self._get_value(data, 'idExterno', 'IdExterno')
        )

    def _extract_transaction_id(self, data):
        return self._get_value(data, 'idTransaccion', 'IdTransaccion', 'idTransaccionCompra', 'IdTransaccionCompra')

    def _extract_amount(self, data):
        return self._get_value(data, 'monto', 'Monto', 'montoOriginal', 'MontoOriginal')

    def _extract_result(self, data):
        return self._get_value(data, 'resultadoTransaccion', 'ResultadoTransaccion', 'estado', 'Estado', 'mensaje', 'Mensaje')

    def _extract_approved_flag(self, data):
        value = self._get_value(data, 'esAprobada', 'EsAprobada', 'aprobada', 'Aprobada')
        if isinstance(value, bool):
            return value
        if value is None:
            return None
        value = str(value).lower().strip()
        if value in ('true', '1', 'si', 'sí', 'yes'):
            return True
        if value in ('false', '0', 'no'):
            return False
        return None

    def _get_value(self, data, *keys):
        if not isinstance(data, dict):
            return None
        for key in keys:
            if key in data:
                return data[key]
        lower_map = {str(k).lower(): v for k, v in data.items()}
        for key in keys:
            value = lower_map.get(str(key).lower())
            if value is not None:
                return value
        return None

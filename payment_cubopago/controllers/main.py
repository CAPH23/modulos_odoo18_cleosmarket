# -*- coding: utf-8 -*-
# Part of the CuboPago payment module.
# Copyright 2026 Carlos Palacios
# License OPL-1 (Odoo Proprietary License v1.0). See LICENSE file for full details.
import json
import logging
import pprint

from odoo import http
from odoo.http import request

from odoo.addons.payment_cubopago import const

_logger = logging.getLogger(__name__)


class CuboPagoController(http.Controller):
    _return_url = '/payment/cubopago/return'
    _webhook_url = '/payment/cubopago/webhook'

    @http.route(
        _return_url,
        type='http',
        methods=['GET', 'POST'],
        auth='public',
        csrf=False,
        website=True,
    )
    def cubopago_return_from_checkout(self, **data):
        """CuboPago redirects the customer here after the payment attempt.

        The redirect is NOT signed, so we do not change the transaction state
        from here. Odoo tracks the active transaction in the session; the
        authoritative confirmation comes from the (API-verified) webhook.
        """
        _logger.info('CuboPago return received:\n%s', pprint.pformat(data))
        return request.redirect('/payment/status')

    @http.route(
        _webhook_url,
        type='http',
        auth='public',
        methods=['POST'],
        csrf=False,
    )
    def cubopago_webhook(self, **_kwargs):
        raw_body = request.httprequest.get_data(cache=True) or b''
        try:
            data = json.loads(raw_body.decode('utf-8')) if raw_body else {}
        except Exception:
            _logger.exception('CuboPago webhook rejected: invalid JSON body.')
            return request.make_response('invalid json', status=400)

        if not data:
            _logger.warning('CuboPago webhook rejected: empty JSON body.')
            return request.make_response('empty payload', status=400)

        data['_cubopago_source'] = 'webhook'
        _logger.info('CuboPago webhook received:\n%s', pprint.pformat(data))
        try:
            # _process_notification_data performs the mandatory server-to-server
            # verification against CuboPago before changing any state.
            request.env['payment.transaction'].sudo()._handle_notification_data(const.PROVIDER_CODE, data)
        except Exception:
            _logger.exception('CuboPago: error procesando webhook. Se responde OK para evitar reintentos infinitos.')
        return request.make_response('ok', status=200)

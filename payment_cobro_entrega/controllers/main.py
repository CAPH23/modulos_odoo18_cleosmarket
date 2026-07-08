# -*- coding: utf-8 -*-
import logging
import pprint

from odoo.http import Controller, request, route

from odoo.addons.payment_cobro_entrega import const

_logger = logging.getLogger(__name__)


class CobroEntregaController(Controller):
    _process_url = '/payment/cobro_entrega/process'

    @route(_process_url, type='http', auth='public', methods=['POST'], csrf=False)
    def cobro_entrega_process_transaction(self, **post):
        _logger.info("Handling Cobro contra entrega processing with data:\n%s", pprint.pformat(post))
        request.env['payment.transaction'].sudo()._handle_notification_data(const.PROVIDER_CODE, post)
        return request.redirect('/payment/status')

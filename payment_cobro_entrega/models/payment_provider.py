# -*- coding: utf-8 -*-
from odoo import fields, models

from odoo.addons.payment_cobro_entrega import const


class PaymentProvider(models.Model):
    _inherit = 'payment.provider'

    code = fields.Selection(
        selection_add=[(const.PROVIDER_CODE, 'Cobro contra entrega')],
        ondelete={const.PROVIDER_CODE: 'set default'},
    )

    def _get_default_payment_method_codes(self):
        """Return the default payment method codes for this provider."""
        default_codes = super()._get_default_payment_method_codes()
        if self.code != const.PROVIDER_CODE:
            return default_codes
        return const.DEFAULT_PAYMENT_METHOD_CODES

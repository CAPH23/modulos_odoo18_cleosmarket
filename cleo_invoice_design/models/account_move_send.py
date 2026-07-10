# -*- coding: utf-8 -*-
from odoo import models


class AccountMoveSend(models.AbstractModel):
    _inherit = 'account.move.send'

    def _get_default_pdf_report_id(self, move):
        if move.move_type in ('out_invoice', 'out_receipt') and move.state == 'posted':
            ticket_report = self.env.ref('cleo_invoice_design.action_report_cleo_invoice_ticket', raise_if_not_found=False)
            if ticket_report:
                return ticket_report
        return super()._get_default_pdf_report_id(move)

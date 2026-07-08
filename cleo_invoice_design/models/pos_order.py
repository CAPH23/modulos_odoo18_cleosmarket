# -*- coding: utf-8 -*-
from odoo import models


class PosOrder(models.Model):
    _inherit = 'pos.order'

    def action_print_cleo_pos_ticket(self):
        """Print the Super Tienda Cleo POS 80mm ticket."""
        return self.env.ref('cleo_invoice_design.action_report_cleo_pos_ticket').report_action(self)

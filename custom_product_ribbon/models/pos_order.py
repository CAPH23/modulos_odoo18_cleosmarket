from odoo import models

class PosOrder(models.Model):
    _inherit = 'pos.order'

    def _create_picking(self):
        res = super()._create_picking()
        self.env['product.template']._update_ribbon_status()
        return res

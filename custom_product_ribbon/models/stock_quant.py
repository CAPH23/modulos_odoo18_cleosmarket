from odoo import models

class StockQuant(models.Model):
    _inherit = 'stock.quant'

    def write(self, vals):
        res = super().write(vals)
        self._update_product_ribbons()
        return res

    def _update_product_ribbons(self):
        ribbon = self.env['product.ribbon'].search([('name', '=', 'Fuera de stock')], limit=1)
        if not ribbon:
            return
        product_ids = self.mapped('product_id.product_tmpl_id')
        for template in product_ids:
            if template.qty_available <= 0:
                template.website_ribbon_id = ribbon.id
            else:
                if template.website_ribbon_id == ribbon:
                    template.website_ribbon_id = False

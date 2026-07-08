from odoo import api, fields, models

class ProductTemplate(models.Model):
    _inherit = 'product.template'

    website_ribbon_id = fields.Many2one(
        comodel_name='product.ribbon',
        string="Ribbon",
    )

    @api.model
    def _update_ribbon_status(self):
        ribbon = self.env['product.ribbon'].search([('name', '=', 'Fuera de stock')], limit=1)
        if not ribbon:
            return
        products = self.search([])
        for product in products:
            if product.qty_available <= 0:
                product.website_ribbon_id = ribbon.id
            else:
                if product.website_ribbon_id == ribbon:
                    product.website_ribbon_id = False

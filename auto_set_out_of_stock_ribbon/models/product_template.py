from odoo import api, fields, models

class ProductTemplate(models.Model):
    _inherit = 'product.template'

    @api.depends('qty_available')
    def _compute_website_ribbon_auto(self):
        ribbon = self.env['product.ribbon'].search([('name', '=', 'Fuera de stock')], limit=1)
        for product in self:
            if product.qty_available <= 0 and ribbon:
                product.website_ribbon_id = ribbon.id

    website_ribbon_id = fields.Many2one(
        comodel_name='product.ribbon',
        string="Ribbon",
        compute='_compute_website_ribbon_auto',
        store=True,
    )

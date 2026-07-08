from odoo import models, fields, api

class ProductTemplate(models.Model):
    _inherit = 'product.template'

    ribbon_text = fields.Char(
        string='Ribbon Text',
        compute='_compute_ribbon_text',
        store=True
    )

    ribbon_color = fields.Selection([
        ('primary', 'Primary'),
        ('secondary', 'Secondary'),
        ('success', 'Success'),
        ('danger', 'Danger'),
        ('warning', 'Warning'),
        ('info', 'Info'),
        ('light', 'Light'),
        ('dark', 'Dark')
    ], string="Ribbon Color", default='danger')

    @api.depends('qty_available')
    def _compute_ribbon_text(self):
        for record in self:
            if record.qty_available <= 0:
                record.ribbon_text = 'Fuera de stock'
            else:
                record.ribbon_text = False

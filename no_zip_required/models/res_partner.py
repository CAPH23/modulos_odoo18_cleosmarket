from odoo import models, fields

class ResPartner(models.Model):
    _inherit = 'res.partner'

    zip = fields.Char(string='Zip', required=False)

    country_id = fields.Many2one(
        'res.country',
        string='Country',
        default=lambda self: self.env.ref('base.sv').id  # ISO code for El Salvador
    )

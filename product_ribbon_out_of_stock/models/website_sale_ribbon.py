from odoo import models, fields

class WebsiteSaleRibbon(models.Model):
    _name = 'website.sale.ribbon'
    _description = 'Ribbon for Website Sale'

    name = fields.Char(string='Name', required=True)
    text = fields.Char(string='Text')
    color = fields.Selection([
        ('primary', 'Primary'),
        ('success', 'Success'),
        ('danger', 'Danger'),
        ('warning', 'Warning'),
        ('info', 'Info'),
    ], default='primary')
    position = fields.Selection([
        ('top-left', 'Top Left'),
        ('top-right', 'Top Right'),
        ('bottom-left', 'Bottom Left'),
        ('bottom-right', 'Bottom Right'),
    ], default='top-left')
    condition_python = fields.Text(string='Condition Python')
    auto_display_condition = fields.Boolean(string='Auto Display Condition')

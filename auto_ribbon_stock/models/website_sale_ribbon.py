from odoo import models, fields

class WebsiteSaleRibbon(models.Model):
    _name = 'website.sale.ribbon'
    _description = 'Website Sale Ribbon'

    name = fields.Char(required=True)
    text = fields.Char(string='Texto del Ribbon')
    color = fields.Selection([
        ('primary', 'Azul'),
        ('secondary', 'Gris'),
        ('success', 'Verde'),
        ('danger', 'Rojo'),
        ('warning', 'Amarillo'),
        ('info', 'Celeste'),
        ('light', 'Blanco'),
        ('dark', 'Negro'),
    ], string='Color', default='danger')
    position = fields.Selection([
        ('top-left', 'Arriba a la izquierda'),
        ('top-right', 'Arriba a la derecha'),
        ('bottom-left', 'Abajo a la izquierda'),
        ('bottom-right', 'Abajo a la derecha'),
    ], string='Posición', default='top-left')
    condition_python = fields.Text(string='Condición Python')
    auto_display_condition = fields.Boolean(string='Mostrar automáticamente', default=False)

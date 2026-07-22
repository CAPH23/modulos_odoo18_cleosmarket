# -*- coding: utf-8 -*-
from odoo import api, fields, models


class ProductTemplate(models.Model):
    _inherit = "product.template"

    goboxful_width_cm = fields.Float(string="Ancho Boxful (cm)", default=0.0)
    goboxful_length_cm = fields.Float(string="Largo Boxful (cm)", default=0.0)
    goboxful_height_cm = fields.Float(
        string="Alto Boxful (cm)", default=0.0,
        help="Opcional. Si queda vacío, el módulo lo estima con el volumen total.",
    )
    goboxful_is_fragile = fields.Boolean(string="Producto frágil")
    goboxful_shipping_blocked = fields.Boolean(
        string="Boxful bloqueado",
        compute="_compute_goboxful_shipping_blocked",
        search="_search_goboxful_shipping_blocked",
    )

    @api.depends("categ_id.goboxful_effectively_blocked")
    def _compute_goboxful_shipping_blocked(self):
        for product in self:
            product.goboxful_shipping_blocked = product.categ_id.goboxful_effectively_blocked

    def _search_goboxful_shipping_blocked(self, operator, value):
        categories = self.env["product.category"].search([
            ("goboxful_effectively_blocked", operator, value),
        ])
        return [("categ_id", "in", categories.ids)]

# -*- coding: utf-8 -*-
from odoo import api, fields, models


class ProductCategory(models.Model):
    _inherit = "product.category"

    goboxful_block_shipping = fields.Boolean(
        string="No permitir envío por Boxful",
        help="Bloquea Boxful para los productos de esta categoría y de todas sus subcategorías.",
    )
    goboxful_effectively_blocked = fields.Boolean(
        compute="_compute_goboxful_effectively_blocked",
        search="_search_goboxful_effectively_blocked",
    )

    @api.depends("goboxful_block_shipping", "parent_id.goboxful_block_shipping")
    def _compute_goboxful_effectively_blocked(self):
        for category in self:
            current = category
            blocked = False
            while current:
                if current.goboxful_block_shipping:
                    blocked = True
                    break
                current = current.parent_id
            category.goboxful_effectively_blocked = blocked

    def _search_goboxful_effectively_blocked(self, operator, value):
        blocked_roots = self.search([("goboxful_block_shipping", "=", True)])
        descendants = self.search([("id", "child_of", blocked_roots.ids)]) if blocked_roots else self.browse()
        positive = bool(value) if operator in ("=", "==") else not bool(value)
        return [("id", "in" if positive else "not in", descendants.ids)]

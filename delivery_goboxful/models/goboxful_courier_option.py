# -*- coding: utf-8 -*-
from odoo import api, fields, models


class GoBoxfulCourierOption(models.Model):
    _name = "goboxful.courier.option"
    _description = "Boxful Courier Quote Option"
    _order = "total_price, base_price, id"
    _check_company_auto = True

    picking_id = fields.Many2one("stock.picking", required=True, ondelete="cascade", index=True)
    sale_order_id = fields.Many2one(related="picking_id.sale_id", store=True, index=True)
    company_id = fields.Many2one(related="picking_id.company_id", store=True, index=True)
    currency_id = fields.Many2one(related="sale_order_id.currency_id", store=True)
    courier_external_id = fields.Char(required=True, index=True)
    courier_name = fields.Char(required=True)
    delivery_type = fields.Char()
    base_price = fields.Monetary(currency_field="currency_id")
    cod_commission = fields.Monetary(currency_field="currency_id")
    total_price = fields.Monetary(compute="_compute_total_price", store=True, currency_field="currency_id")
    estimated_delivery = fields.Char()
    raw_payload = fields.Text(groups="base.group_system")
    selected = fields.Boolean(compute="_compute_selected")

    _sql_constraints = [
        ("picking_courier_unique", "unique(picking_id, courier_external_id)",
         "El courier ya existe entre las opciones de esta transferencia."),
    ]

    @api.depends("base_price", "cod_commission")
    def _compute_total_price(self):
        for option in self:
            option.total_price = option.base_price + option.cod_commission

    @api.depends("picking_id.goboxful_selected_option_id")
    def _compute_selected(self):
        for option in self:
            option.selected = option.picking_id.goboxful_selected_option_id == option

    def action_select(self):
        self.ensure_one()
        self.picking_id.goboxful_selected_option_id = self
        self.picking_id._goboxful_apply_selected_option()
        return {"type": "ir.actions.client", "tag": "reload"}

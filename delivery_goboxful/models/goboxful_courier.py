# -*- coding: utf-8 -*-
from odoo import fields, models


class GoBoxfulCourier(models.Model):
    _name = "goboxful.courier"
    _description = "Boxful Courier Classification"
    _order = "delivery_type, name"

    carrier_id = fields.Many2one(
        "delivery.carrier", required=True, ondelete="cascade", index=True,
    )
    company_id = fields.Many2one(related="carrier_id.company_id", store=True, index=True)
    external_id = fields.Char(required=True, index=True)
    name = fields.Char(required=True)
    delivery_type = fields.Selection(
        [("same_day", "Mismo día"), ("scheduled", "Entrega programada")],
        string="Tipo de entrega", required=True, default="same_day",
    )
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ("carrier_external_unique", "unique(carrier_id, external_id)",
         "Este courier ya está registrado para este método de envío."),
    ]

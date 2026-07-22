# -*- coding: utf-8 -*-
from odoo import fields, models


class GoBoxfulApiLog(models.Model):
    _name = "goboxful.api.log"
    _description = "Boxful API Log"
    _order = "create_date desc, id desc"

    company_id = fields.Many2one(
        "res.company", required=True, index=True, ondelete="cascade",
        default=lambda self: self.env.company,
    )
    account_id = fields.Many2one("goboxful.account", ondelete="set null", index=True)
    method = fields.Char(required=True, index=True)
    endpoint = fields.Char(required=True, index=True)
    http_status = fields.Integer(index=True)
    duration_ms = fields.Integer()
    success = fields.Boolean(default=False, index=True)
    request_body = fields.Text()
    response_body = fields.Text()
    error_message = fields.Text()
    res_model = fields.Char(index=True)
    res_id = fields.Integer(index=True)

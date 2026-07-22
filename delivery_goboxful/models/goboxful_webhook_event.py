# -*- coding: utf-8 -*-
import hashlib
import json

from odoo import api, fields, models


class GoBoxfulWebhookEvent(models.Model):
    _name = "goboxful.webhook.event"
    _description = "Boxful Webhook Event"
    _order = "create_date desc, id desc"

    event_hash = fields.Char(required=True, index=True)
    company_id = fields.Many2one("res.company", required=True, index=True, ondelete="cascade")
    account_id = fields.Many2one("goboxful.account", required=True, index=True, ondelete="cascade")
    picking_id = fields.Many2one("stock.picking", index=True, ondelete="set null")
    shipment_id = fields.Char(index=True)
    shipment_number = fields.Char(index=True)
    status_code = fields.Integer(index=True)
    event_date = fields.Datetime(index=True)
    payload = fields.Text(required=True)
    processed = fields.Boolean(default=False, index=True)
    processing_message = fields.Char()

    _sql_constraints = [
        ("event_hash_unique", "unique(event_hash)", "El evento webhook Boxful ya fue procesado."),
    ]

    @api.model
    def hash_payload(self, account_id, payload):
        canonical = json.dumps(payload or {}, sort_keys=True, separators=(",", ":"), default=str)
        return hashlib.sha256(("%s|%s" % (account_id, canonical)).encode()).hexdigest()

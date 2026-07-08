# -*- coding: utf-8 -*-

from odoo import fields, models


class SaleOrder(models.Model):
    _inherit = "sale.order"

    cleo_terms_accepted = fields.Boolean(
        string="Términos aceptados",
        copy=False,
        readonly=True,
    )

    cleo_terms_accepted_datetime = fields.Datetime(
        string="Fecha de aceptación",
        copy=False,
        readonly=True,
    )

    cleo_terms_accepted_ip = fields.Char(
        string="IP de aceptación",
        copy=False,
        readonly=True,
    )

    cleo_terms_accepted_user_agent = fields.Char(
        string="Navegador / dispositivo",
        copy=False,
        readonly=True,
    )

    cleo_terms_accepted_url = fields.Char(
        string="URL de términos aceptada",
        copy=False,
        readonly=True,
    )

    cleo_terms_accepted_version = fields.Char(
        string="Versión legal aceptada",
        copy=False,
        readonly=True,
        default="2026-06",
    )

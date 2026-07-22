# -*- coding: utf-8 -*-
import re
import unicodedata

from odoo import api, fields, models


def normalize_location_name(value):
    value = unicodedata.normalize("NFKD", value or "")
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = re.sub(r"[^a-zA-Z0-9]+", " ", value).strip().lower()
    return re.sub(r"\s+", " ", value)


class GoBoxfulState(models.Model):
    _name = "goboxful.state"
    _description = "Boxful State"
    _order = "country_code, name"

    name = fields.Char(required=True, index=True)
    normalized_name = fields.Char(compute="_compute_normalized_name", store=True, index=True)
    external_id = fields.Char(required=True, index=True)
    country_code = fields.Selection(
        selection="_selection_country_code", string="Código de país",
        required=True, index=True,
    )
    country_id = fields.Many2one(
        "res.country", string="País", compute="_compute_country_id",
        inverse="_inverse_country_id", store=True,
    )
    active = fields.Boolean(default=True)
    city_ids = fields.One2many("goboxful.city", "state_id", string="Ciudades")
    last_sync_at = fields.Datetime(readonly=True)

    _sql_constraints = [
        ("external_country_unique", "unique(external_id, country_code)",
         "El identificador Boxful del departamento/estado debe ser único por país."),
    ]

    @api.model
    def _selection_country_code(self):
        countries = self.env["res.country"].sudo().search([("code", "!=", False)])
        return sorted(
            {(country.code, "%s - %s" % (country.code, country.name)) for country in countries},
            key=lambda item: item[1],
        )

    @api.depends("country_code")
    def _compute_country_id(self):
        Country = self.env["res.country"].sudo()
        for record in self:
            record.country_id = Country.search([("code", "=", record.country_code)], limit=1)

    def _inverse_country_id(self):
        for record in self:
            if record.country_id:
                record.country_code = record.country_id.code

    @api.depends("name")
    def _compute_normalized_name(self):
        for record in self:
            record.normalized_name = normalize_location_name(record.name)


class GoBoxfulCity(models.Model):
    _name = "goboxful.city"
    _description = "Boxful City"
    _order = "state_id, name"

    name = fields.Char(required=True, index=True)
    normalized_name = fields.Char(compute="_compute_normalized_name", store=True, index=True)
    external_id = fields.Char(required=True, index=True)
    state_id = fields.Many2one(
        "goboxful.state", required=True, ondelete="cascade", index=True,
    )
    country_code = fields.Selection(related="state_id.country_code", store=True, index=True)
    active = fields.Boolean(default=True)
    # En la instalación de Cleos Market, res.partner.state_id representa el
    # Municipio y res.partner.city contiene el Distrito como texto. Boxful usa
    # la ciudad como municipio; por eso el mapeo se realiza contra state_id y
    # no se instala base_address_city ni se modifica el formulario existente.
    # Es un mapeo de varios-a-uno: Boxful puede tener una sola ciudad (p. ej.
    # "San Salvador") que corresponde a varios Municipios de Odoo (p. ej. SAN
    # SALVADOR CENTRO/NORTE/OESTE/ESTE/SUR de l10n_sv), por lo que no alcanza
    # con un Many2one.
    odoo_state_ids = fields.Many2many(
        "res.country.state", string="Municipios equivalentes en Odoo",
    )
    latitude = fields.Float(digits=(16, 7))
    longitude = fields.Float(digits=(16, 7))
    last_sync_at = fields.Datetime(readonly=True)

    _sql_constraints = [
        ("external_state_unique", "unique(external_id, state_id)",
         "El identificador Boxful de la ciudad debe ser único dentro del estado."),
    ]

    @api.depends("name")
    def _compute_normalized_name(self):
        for record in self:
            record.normalized_name = normalize_location_name(record.name)

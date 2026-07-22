# -*- coding: utf-8 -*-
from odoo import api, fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    goboxful_department_id = fields.Many2one(
        "goboxful.state", string="Departamento Boxful",
        related="state_id.goboxful_department_id", store=True, readonly=True,
        help="Se deriva del Municipio (Estado): configure el Departamento de cada "
             "Municipio en Contactos > Configuración > Provincias.",
    )
    goboxful_city_id = fields.Many2one(
        "goboxful.city", string="Ciudad Boxful/Distrito",
        help="Se mantiene sincronizado con el Distrito: cada vez que el Distrito cambia, "
             "este campo se recalcula automáticamente (incluido dejarlo vacío si el nuevo "
             "Distrito no calza con ninguna ciudad Boxful sincronizada).",
    )
    goboxful_reference_point = fields.Char(
        string="Punto de referencia Boxful",
        help="Si está vacío se utiliza la segunda línea de dirección o el nombre del distrito.",
    )
    goboxful_delivery_instructions = fields.Text(string="Instrucciones de entrega Boxful")

    def _goboxful_match_city_from_district(self):
        self.ensure_one()
        if not self.city:
            return self.env["goboxful.city"]
        from .goboxful_location import normalize_location_name
        return self.env["goboxful.city"].sudo().search([
            ("country_code", "=", self.country_id.code or "SV"),
            ("normalized_name", "=", normalize_location_name(self.city)),
            ("active", "=", True),
        ], limit=1)

    def _goboxful_autofill_city(self, force=False):
        for partner in self:
            if not force and partner.goboxful_city_id:
                continue
            match = partner._goboxful_match_city_from_district()
            if partner.goboxful_city_id != match:
                partner.goboxful_city_id = match

    @api.onchange("city", "country_id")
    def _onchange_goboxful_city_from_district(self):
        match = self._goboxful_match_city_from_district()
        if self.goboxful_city_id != match:
            self.goboxful_city_id = match

    @api.model_create_multi
    def create(self, vals_list):
        partners = super().create(vals_list)
        partners._goboxful_autofill_city()
        return partners

    def write(self, vals):
        res = super().write(vals)
        if "city" in vals or "country_id" in vals:
            # El Distrito cambió: se resincroniza siempre (incluso limpiando el
            # valor si el nuevo Distrito ya no calza con ninguna ciudad Boxful),
            # para no dejar un mapeo viejo apuntando a una ciudad equivocada.
            self._goboxful_autofill_city(force=True)
        return res

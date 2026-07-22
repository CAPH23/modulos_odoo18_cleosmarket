# -*- coding: utf-8 -*-
from odoo import fields, models


class ResCountryState(models.Model):
    _inherit = "res.country.state"

    # En este proyecto res.country.state representa el Municipio (ver
    # l10n_sv_city). Boxful agrupa los municipios bajo un Departamento
    # (modelo goboxful.state, ya usado como "Departamento Boxful" en
    # goboxful.account); este campo registra a qué Departamento pertenece
    # cada Municipio para poder derivarlo también en el contacto.
    goboxful_department_id = fields.Many2one(
        "goboxful.state", string="Departamento", ondelete="set null", index=True,
    )

# -*- coding: utf-8 -*-
"""Hace que /my/account valide municipio (state_id) y latitud/longitud igual
que /shop/address?address_type=billing.

La parte visual (municipio limitado a El Salvador, distrito como select
filtrado, mapa, país fijo) vive en views/portal_account_geo_templates.xml;
este controlador solo ajusta la validación de esos campos nuevos en el
formulario de portal.CustomerPortal.account(), que sigue escribiendo
directamente sobre request.env.user.partner_id.
"""

from odoo import _
from odoo.addons.portal.controllers.portal import CustomerPortal


class CleoPortalAccount(CustomerPortal):

    def _get_mandatory_fields(self):
        return super()._get_mandatory_fields() + ["state_id"]

    def _get_optional_fields(self):
        fields = [f for f in super()._get_optional_fields() if f != "state_id"]
        return fields + ["partner_latitude", "partner_longitude"]

    def _cleo_parse_coordinate(self, value):
        """Convierte coordenadas escritas con punto o coma decimal."""
        if not value:
            return None

        value = str(value).strip().replace(",", ".")
        if not value:
            return None

        try:
            return float(value)
        except ValueError:
            return None

    def details_form_validate(self, data, partner_creation=False):
        error, error_message = super().details_form_validate(data, partner_creation=partner_creation)

        raw_latitude = data.get("partner_latitude")
        raw_longitude = data.get("partner_longitude")
        latitude_empty = not raw_latitude
        longitude_empty = not raw_longitude

        # Igual que en /shop/address/submit: latitud/longitud son opcionales,
        # pero si se manda una, se debe mandar la otra y ambas deben ser válidas.
        if latitude_empty != longitude_empty:
            error["partner_latitude"] = "missing"
            error["partner_longitude"] = "missing"
            error_message.append(_("Debe ingresar latitud y longitud, o dejar ambas vacías."))
        elif not latitude_empty:
            latitude = self._cleo_parse_coordinate(raw_latitude)
            longitude = self._cleo_parse_coordinate(raw_longitude)

            if latitude is None or longitude is None:
                error["partner_latitude"] = "error"
                error["partner_longitude"] = "error"
                error_message.append(
                    _("Latitud y longitud deben ser valores numéricos. Ejemplo: 13.6929400 y -89.2181900.")
                )
            elif latitude < -90 or latitude > 90:
                error["partner_latitude"] = "error"
                error_message.append(_("La latitud debe estar entre -90 y 90."))
            elif longitude < -180 or longitude > 180:
                error["partner_longitude"] = "error"
                error_message.append(_("La longitud debe estar entre -180 y 180."))

        return error, error_message

    def on_account_update(self, values, partner):
        super().on_account_update(values, partner)
        for fname in ("partner_latitude", "partner_longitude"):
            if fname in values:
                parsed = self._cleo_parse_coordinate(values[fname])
                values[fname] = parsed if parsed is not None else False

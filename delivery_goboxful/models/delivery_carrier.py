# -*- coding: utf-8 -*-
import hashlib
import json
import logging
import math
from datetime import datetime, time as dt_time, timedelta, timezone

import pytz
from babel.dates import format_datetime

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools.misc import get_lang

_logger = logging.getLogger(__name__)

LB_TO_KG = 0.45359237
FT3_TO_M3 = 0.028316846592


class DeliveryCarrier(models.Model):
    _inherit = "delivery.carrier"

    delivery_type = fields.Selection(
        selection_add=[("goboxful", "Boxful")],
        ondelete={"goboxful": lambda records: records.write({
            "delivery_type": "fixed", "fixed_price": 0,
        })},
    )
    goboxful_account_id = fields.Many2one(
        "goboxful.account", string="Cuenta Boxful", ondelete="restrict",
        domain="[('company_id', '=', company_id), ('active', '=', True)]",
        check_company=True,
    )
    goboxful_same_day_only = fields.Boolean(
        string="Solo couriers del mismo día",
        default=False,
        help="Si está activo, la tarjeta de envío solo lista couriers clasificados como "
             "'Mismo día' en la tabla de abajo. Si está inactivo, se listan también los "
             "couriers de 'Entrega programada'.",
    )
    goboxful_quote_cache_minutes = fields.Integer(
        string="Vigencia de cotización (minutos)", default=8,
    )
    goboxful_selection_criteria = fields.Selection(
        [("cheapest", "Más barato"), ("fastest", "Más rápido")],
        string="Criterio de preselección de courier", default="cheapest", required=True,
        help="Determina qué courier aparece preseleccionado en la tarjeta de envío. "
             "El cliente puede elegir cualquier otro courier de la lista.",
    )
    goboxful_courier_ids = fields.One2many(
        "goboxful.courier", "carrier_id", string="Couriers Boxful",
        help="Cada courier que Boxful devuelve se registra aquí automáticamente la primera "
             "vez que se cotiza (como 'Mismo día'). Reclasifíquelo aquí como 'Entrega "
             "programada' si corresponde a couriers de día siguiente o posterior.",
    )
    goboxful_last_error = fields.Char(readonly=True, copy=False)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("delivery_type") == "goboxful":
                vals["integration_level"] = "rate"
        return super().create(vals_list)

    def write(self, vals):
        if vals.get("delivery_type") == "goboxful" or (
            "integration_level" in vals and any(r.delivery_type == "goboxful" for r in self)
        ):
            vals["integration_level"] = "rate"
        return super().write(vals)

    @api.onchange("delivery_type")
    def _onchange_goboxful_delivery_type(self):
        if self.delivery_type == "goboxful":
            self.integration_level = "rate"
            if self.company_id:
                self.goboxful_account_id = self.env["goboxful.account"].search([
                    ("company_id", "=", self.company_id.id), ("active", "=", True),
                ], limit=1)

    def _match(self, partner, order):
        matched = super()._match(partner, order)
        if not matched or self.delivery_type != "goboxful":
            return matched
        return not order._goboxful_has_blocked_products()

    def _goboxful_get_account(self, company=None):
        self.ensure_one()
        company = company or self.company_id or self.env.company
        account = self.sudo().goboxful_account_id.sudo()
        if not account or account.company_id != company:
            account = self.env["goboxful.account"].sudo().search([
                ("company_id", "=", company.id), ("active", "=", True),
            ], limit=1)
        if not account:
            raise UserError(_("No existe una cuenta Boxful configurada para %s.") % company.display_name)
        return account

    # ------------------------------------------------------------------
    # Direcciones, peso, volumen y paquete único
    # ------------------------------------------------------------------
    @api.model
    def _goboxful_weight_for_api(self, value, account):
        """Normaliza el peso de Odoo a la unidad configurada para Boxful."""
        odoo_in_lbs = self.env["ir.config_parameter"].sudo().get_param(
            "product.weight_in_lbs", "0"
        ) in ("1", "True", "true")
        value = float(value or 0.0)
        if account.api_weight_unit == "lb":
            return value if odoo_in_lbs else value / LB_TO_KG
        return value * LB_TO_KG if odoo_in_lbs else value

    @api.model
    def _goboxful_volume_to_m3(self, value):
        in_ft3 = self.env["ir.config_parameter"].sudo().get_param(
            "product.volume_in_cubic_feet", "0"
        ) in ("1", "True", "true")
        return float(value or 0.0) * (FT3_TO_M3 if in_ft3 else 1.0)

    @api.model
    def _goboxful_phone(self, partner):
        raw = partner.mobile or partner.phone or ""
        digits = "".join(char for char in raw if char.isdigit())
        if digits.startswith("503") and len(digits) > 8:
            digits = digits[3:]
        return digits[:15]

    @api.model
    def _goboxful_area_code(self, partner, fallback="+503"):
        phone_code = partner.country_id.phone_code if partner.country_id else False
        if phone_code:
            return "+%s" % str(phone_code).lstrip("+")
        return fallback or "+503"

    def _goboxful_find_city(self, partner, account):
        self.ensure_one()
        if partner.goboxful_city_id and partner.goboxful_city_id.country_code == (partner.country_id.code or "SV"):
            return partner.goboxful_city_id
        City = self.env["goboxful.city"].sudo()
        country_code = partner.country_id.code or account.pickup_country_code or "SV"
        city = City.search([
            ("country_code", "=", country_code),
            ("odoo_state_ids", "in", partner.state_id.ids),
            ("active", "=", True),
        ], limit=1)
        if not city and partner.state_id:
            from .goboxful_location import normalize_location_name
            city = City.search([
                ("country_code", "=", country_code),
                ("normalized_name", "=", normalize_location_name(partner.state_id.name)),
                ("active", "=", True),
            ], limit=1)
        return city

    def _goboxful_validate_destination(self, partner, account):
        missing = []
        if not partner.name:
            missing.append(_("nombre"))
        if not partner.street:
            missing.append(_("calle"))
        if not partner.state_id:
            missing.append(_("municipio"))
        if not partner.country_id:
            missing.append(_("país"))
        if not self._goboxful_phone(partner):
            missing.append(_("teléfono"))
        if not partner.email:
            missing.append(_("correo electrónico"))
        if not partner.partner_latitude:
            missing.append(_("latitud"))
        if not partner.partner_longitude:
            missing.append(_("longitud"))
        city = self._goboxful_find_city(partner, account)
        if not city:
            missing.append(_("mapeo de municipio/ciudad Boxful"))
        if missing:
            raise UserError(_("La dirección de entrega no está completa para Boxful: %s") % ", ".join(missing))
        return city

    def _goboxful_package_from_lines(self, lines, account, total_price):
        self.ensure_one()
        total_weight = 0.0
        total_volume_m3 = 0.0
        max_width = 0.0
        max_length = 0.0
        max_height = 0.0
        fragile = False
        content_names = []

        for line in lines:
            product = line.product_id
            if not product or product.type == "service" or getattr(line, "is_delivery", False):
                continue
            qty = line.product_uom._compute_quantity(line.product_uom_qty, product.uom_id)
            tmpl = product.product_tmpl_id
            total_weight += self._goboxful_weight_for_api(product.weight, account) * qty
            total_volume_m3 += self._goboxful_volume_to_m3(product.volume) * qty
            max_width = max(max_width, tmpl.goboxful_width_cm or 0.0)
            max_length = max(max_length, tmpl.goboxful_length_cm or 0.0)
            max_height = max(max_height, tmpl.goboxful_height_cm or 0.0)
            fragile = fragile or tmpl.goboxful_is_fragile
            if len(content_names) < 4:
                content_names.append(product.display_name)

        weight = max(total_weight, account.default_weight)
        width = max(max_width, account.default_width_cm)
        length = max(max_length, account.default_length_cm)
        volume_cm3 = total_volume_m3 * 1_000_000.0
        calculated_height = volume_cm3 / (width * length) if volume_cm3 and width and length else 0.0
        height = max(max_height, calculated_height, account.default_height_cm)

        return {
            "content": (", ".join(content_names) or _("Productos varios en caja"))[:180],
            "width": round(width, 2),
            "height": round(height, 2),
            "length": round(length, 2),
            "weight": round(weight, 3),
            "price": round(max(float(total_price or 0.0), 0.01), 2),
            "isFragile": bool(fragile),
        }

    def _goboxful_pickup_datetime(self, account):
        tz = pytz.timezone(account.pickup_timezone or "America/El_Salvador")
        now_local = datetime.now(tz)
        lead = timedelta(minutes=max(account.pickup_lead_minutes or 0, 0))
        candidate = now_local + lead
        start_hour = int(math.floor(account.pickup_start_hour or 8.0))
        start_min = int(round(((account.pickup_start_hour or 8.0) % 1) * 60))
        end_hour = int(math.floor(account.pickup_end_hour or 17.0))
        end_min = int(round(((account.pickup_end_hour or 17.0) % 1) * 60))
        opening = tz.localize(datetime.combine(candidate.date(), dt_time(start_hour, start_min)))
        closing = tz.localize(datetime.combine(candidate.date(), dt_time(end_hour, end_min)))
        if candidate < opening:
            candidate = opening
        elif candidate > closing:
            next_day = candidate.date() + timedelta(days=1)
            candidate = tz.localize(datetime.combine(next_day, dt_time(start_hour, start_min)))
        return candidate.astimezone(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")

    @api.model
    def _goboxful_parse_iso(self, value):
        """Convierte un ISO 8601 (el que nosotros enviamos, p. ej. recolectionDateTime) a datetime naive UTC."""
        if not value:
            return False
        try:
            dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            if dt.tzinfo:
                dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
            return dt
        except (TypeError, ValueError):
            return False

    @api.model
    def _goboxful_parse_estimated_delivery(self, value):
        """Convierte el estimatedDelivery de Boxful ('YYYY-MM-DD HH:MM') a datetime."""
        try:
            return datetime.strptime(str(value).strip(), "%Y-%m-%d %H:%M")
        except (TypeError, ValueError):
            return False

    def _goboxful_format_utc_dt(self, dt, account):
        """Formatea un datetime naive UTC (p. ej. el resultado de _goboxful_parse_iso)
        en la zona horaria de recolección de la cuenta, como día/mes/año sin hora."""
        if not dt:
            return ""
        tz = pytz.timezone((account and account.pickup_timezone) or "America/El_Salvador")
        local_dt = pytz.utc.localize(dt).astimezone(tz)
        lang = get_lang(self.env).code or "es_ES"
        return format_datetime(local_dt, format="dd/MM/y", locale=lang)

    def _goboxful_format_naive_dt(self, dt):
        """Formatea un datetime que Boxful ya devuelve en hora local (estimatedDelivery),
        sin aplicar ninguna conversión de zona horaria, como día/mes/año sin hora."""
        if not dt:
            return ""
        lang = get_lang(self.env).code or "es_ES"
        return format_datetime(dt, format="dd/MM/y", locale=lang, tzinfo=None)

    def _goboxful_cod_data(self, order):
        self.ensure_one()
        transactions = order.sudo().transaction_ids.sorted("id", reverse=True)
        cod = bool(transactions.filtered(lambda tx: tx.provider_code == "cleo_cod")[:1])
        return cod, round(order.amount_total, 2) if cod else None

    def _goboxful_prepare_available_payload(self, order, account, city, package):
        cod, cod_amount = self._goboxful_cod_data(order)
        payload = {
            "clientId": account.boxful_client_id or "",
            "recolectionDateTime": self._goboxful_pickup_datetime(account),
            "packages": [package],
            "cod": cod,
            "codAmount": cod_amount,
            "customerAddress": {
                "latitude": order.partner_shipping_id.partner_latitude,
                "longitude": order.partner_shipping_id.partner_longitude,
                "stateId": city.state_id.external_id,
                "cityId": city.external_id,
            },
        }
        if account.boxful_pickup_address_id:
            payload["recolectionAddressId"] = account.boxful_pickup_address_id
        else:
            account._goboxful_validate_pickup()
            payload["recolectionAddress"] = {
                "latitude": account.pickup_latitude,
                "longitude": account.pickup_longitude,
                "stateId": account.pickup_state_id.external_id,
                "cityId": account.pickup_city_id.external_id,
            }
        return payload

    @api.model
    def _goboxful_extract_list(self, response, keys=("couriers", "data", "results")):
        if isinstance(response, list):
            return response
        if isinstance(response, dict):
            for key in keys:
                value = response.get(key)
                if isinstance(value, list):
                    return value
                if isinstance(value, dict):
                    nested = self._goboxful_extract_list(value, keys)
                    if nested:
                        return nested
        return []

    def _goboxful_classify_courier(self, courier_external_id, courier_name, api_delivery_type=None):
        """Devuelve 'same_day' o 'scheduled' para un courier, según la clasificación manual
        configurada en goboxful_courier_ids. El campo /courier/available de Boxful no siempre
        incluye deliveryType, así que esta clasificación (editable en la pestaña Boxful del
        transportista) es la fuente confiable; un courier nuevo se autorregistra como 'Mismo
        día' (o 'Entrega programada' si la API sugiere un tipo de día siguiente) para que el
        responsable lo pueda reclasificar después."""
        self.ensure_one()
        Courier = self.env["goboxful.courier"].sudo()
        courier = Courier.search([
            ("carrier_id", "=", self.id),
            ("external_id", "=", courier_external_id),
        ], limit=1)
        if courier:
            if courier_name and courier.name != courier_name:
                courier.name = courier_name
            return courier.delivery_type
        default_type = "same_day"
        api_delivery_type = str(api_delivery_type or "").lower()
        if api_delivery_type and "same" not in api_delivery_type:
            default_type = "scheduled"
        Courier.create({
            "carrier_id": self.id,
            "external_id": courier_external_id,
            "name": courier_name or courier_external_id,
            "delivery_type": default_type,
        })
        return default_type

    def _goboxful_effective_delivery_type(self, classified_type, pickup_dt, estimated_delivery, account):
        """La clasificación manual ('goboxful.courier') dice si un courier suele ser de mismo
        día, pero para una cotización puntual Boxful puede devolver fechas de recolección y
        entrega en días distintos (p. ej. recolección 23 de julio, entrega 24 de julio o
        después). En ese caso la fecha manda: solo se considera 'same_day' cuando, además de
        estar clasificado así, la fecha de recolección y la fecha estimada de entrega caen en
        el mismo día calendario (ignorando la hora)."""
        self.ensure_one()
        if classified_type != "same_day":
            return classified_type
        if not self._goboxful_same_calendar_day(pickup_dt, estimated_delivery, account):
            return "scheduled"
        return "same_day"

    def _goboxful_same_calendar_day(self, pickup_dt, estimated_delivery, account):
        self.ensure_one()
        estimated_dt = self._goboxful_parse_estimated_delivery(estimated_delivery)
        if not pickup_dt or not estimated_dt:
            return False
        tz = pytz.timezone((account and account.pickup_timezone) or "America/El_Salvador")
        pickup_local_date = pytz.utc.localize(pickup_dt).astimezone(tz).date()
        return pickup_local_date == estimated_dt.date()

    @api.model
    def _goboxful_option_vals(self, item, cod_amount=0.0):
        courier_id = item.get("id") or item.get("courierId") or item.get("courier_id")
        name = item.get("name") or item.get("courierName") or item.get("courier_name")
        base_price = float(item.get("price") or item.get("clientPrice") or 0.0)
        percentage = float(
            item.get("codCommissionPercentage")
            or item.get("clientCodComission")
            or item.get("codCommission")
            or 0.0
        )
        if percentage > 1:
            percentage /= 100.0
        cod_commission = round(float(cod_amount or 0.0) * percentage, 2)
        return {
            "courier_external_id": str(courier_id or ""),
            "courier_name": name or str(courier_id or _("Courier Boxful")),
            "delivery_type": item.get("deliveryType") or item.get("delivery_type"),
            "base_price": base_price,
            "cod_commission": cod_commission,
            "estimated_delivery": str(item.get("estimatedDelivery") or ""),
            "courier_logo": item.get("logo") or "",
            "max_weight": float(item.get("maxWeight") or 0.0),
            "raw": item,
        }

    def _goboxful_build_quote_hash(self, order, package, payload):
        self.ensure_one()
        values = {
            "partner": order.partner_shipping_id.id,
            "address_write_date": str(order.partner_shipping_id.write_date),
            "lines": [
                (line.product_id.id, line.product_uom_qty, line.price_total)
                for line in order.order_line if not line.is_delivery
            ],
            "package": package,
            "cod": payload.get("cod"),
            "codAmount": payload.get("codAmount"),
            "pickup_city": (self.sudo().goboxful_account_id.pickup_city_id.external_id
                if self.sudo().goboxful_account_id and self.sudo().goboxful_account_id.pickup_city_id else False),
            # Sin esto, cambiar "Solo couriers del mismo día" o reclasificar un courier
            # (pestaña Boxful del transportista) no invalida una cotización ya cacheada:
            # goboxful_quote_at se renueva en cada rate_shipment (incluso en cache hit),
            # así que sin estas claves en el hash el filtro nunca se vuelve a aplicar
            # mientras la dirección/carrito no cambien.
            "same_day_only": self.goboxful_same_day_only,
            "courier_classification": sorted(
                (courier.external_id, courier.delivery_type)
                for courier in self.sudo().goboxful_courier_ids
            ),
        }
        return hashlib.sha256(json.dumps(values, sort_keys=True, default=str).encode()).hexdigest()

    def _goboxful_option_sort_key(self, opt):
        self.ensure_one()
        total_price = opt["base_price"] + opt["cod_commission"]
        if self.goboxful_selection_criteria == "fastest":
            estimated = self._goboxful_parse_estimated_delivery(opt["estimated_delivery"])
            return (estimated or datetime.max, total_price, opt["courier_name"])
        return (total_price, opt["courier_name"])

    def _goboxful_get_options_for_order(self, order, force=False):
        self.ensure_one()
        account = self._goboxful_get_account(order.company_id)
        if order._goboxful_has_blocked_products():
            raise UserError(_("Boxful no está disponible porque el pedido contiene productos refrigerados o bloqueados."))
        account._goboxful_validate_pickup()
        if account.mode != "mock" and not account.boxful_client_id:
            me = account._goboxful_get_client().get_me()
            identity = me.get("jwtPayload") or me.get("user") or me
            client_id = identity.get("clientId") or (me.get("gatewayHeaders") or {}).get("x-client-id")
            if client_id:
                account.sudo().boxful_client_id = client_id
        city = self._goboxful_validate_destination(order.partner_shipping_id, account)
        package = self._goboxful_package_from_lines(
            order.order_line, account, order._compute_amount_total_without_delivery()
        )
        available_payload = self._goboxful_prepare_available_payload(order, account, city, package)
        quote_hash = self._goboxful_build_quote_hash(order, package, available_payload)
        if not force and order.goboxful_quote_hash == quote_hash and order.goboxful_quote_at:
            age = fields.Datetime.now() - fields.Datetime.to_datetime(order.goboxful_quote_at)
            if age <= timedelta(minutes=max(self.goboxful_quote_cache_minutes or 0, 0)):
                try:
                    cached = json.loads(order.goboxful_quote_options_json or "[]")
                    if cached:
                        return cached, package, available_payload
                except (TypeError, ValueError):
                    pass
        response = account._goboxful_get_client().available_couriers(
            available_payload, res_model="sale.order", res_id=order.id,
        )
        cod_amount = available_payload.get("codAmount") or 0.0
        pickup_dt = self._goboxful_parse_iso(available_payload.get("recolectionDateTime"))
        options = []
        for item in self._goboxful_extract_list(response):
            vals = self._goboxful_option_vals(item, cod_amount)
            if not vals["courier_external_id"]:
                continue
            classified_type = self._goboxful_classify_courier(
                vals["courier_external_id"], vals["courier_name"], vals["delivery_type"],
            )
            vals["delivery_type"] = self._goboxful_effective_delivery_type(
                classified_type, pickup_dt, vals["estimated_delivery"], account,
            )
            if self.goboxful_same_day_only and vals["delivery_type"] != "same_day":
                continue
            options.append(vals)
        options.sort(key=lambda opt: self._goboxful_option_sort_key(opt))
        if not options:
            raise UserError(_("Boxful no encontró couriers disponibles para esta dirección."))
        return options, package, available_payload

    # ------------------------------------------------------------------
    # API de delivery.carrier
    # ------------------------------------------------------------------
    def _goboxful_pick_selected_option(self, options, order):
        self.ensure_one()
        selected_id = order.goboxful_selected_courier_id
        if selected_id:
            match = next(
                (opt for opt in options if opt["courier_external_id"] == selected_id), None,
            )
            if match:
                return match
        return options[0]

    def _goboxful_build_display_options(self, options, account, pickup_at, selected_id, order):
        self.ensure_one()
        pickup_label = self._goboxful_format_utc_dt(pickup_at, account)
        Monetary = self.env["ir.qweb.field.monetary"]
        display = []
        for opt in options:
            estimated_dt = self._goboxful_parse_estimated_delivery(opt["estimated_delivery"])
            price = round(opt["base_price"] + opt["cod_commission"], 2)
            display.append({
                "courier_external_id": opt["courier_external_id"],
                "courier_name": opt["courier_name"],
                "courier_logo": opt["courier_logo"],
                "delivery_type": opt["delivery_type"],
                "delivery_type_label": (
                    _("Mismo día") if opt["delivery_type"] == "same_day" else _("Entrega programada")
                ),
                "max_weight": opt["max_weight"],
                "max_weight_unit": account.api_weight_unit if account else "lb",
                "pickup_at": pickup_label,
                "estimated_delivery": self._goboxful_format_naive_dt(estimated_dt) or opt["estimated_delivery"],
                "price": price,
                "price_label": Monetary.value_to_html(price, {"display_currency": order.currency_id}),
                "selected": opt["courier_external_id"] == selected_id,
            })
        return display

    def goboxful_rate_shipment(self, order):
        self.ensure_one()
        try:
            options, package, payload = self._goboxful_get_options_for_order(order)
            selected = self._goboxful_pick_selected_option(options, order)
            hash_value = self._goboxful_build_quote_hash(order, package, payload)
            account = self._goboxful_get_account(order.company_id)
            pickup_at = self._goboxful_parse_iso(payload.get("recolectionDateTime"))
            estimated_dt = self._goboxful_parse_estimated_delivery(selected["estimated_delivery"])
            order.sudo().write({
                "goboxful_quoted_courier_id": selected["courier_external_id"],
                "goboxful_quoted_courier_name": selected["courier_name"],
                "goboxful_quote_price": selected["base_price"],
                "goboxful_quote_cod_commission": selected["cod_commission"],
                "goboxful_quote_estimated_delivery": selected["estimated_delivery"],
                "goboxful_quote_hash": hash_value,
                "goboxful_quote_at": fields.Datetime.now(),
                "goboxful_quote_options_json": json.dumps(options, default=str),
                "goboxful_quoted_courier_logo": selected["courier_logo"],
                "goboxful_quoted_max_weight": selected["max_weight"],
                "goboxful_quoted_delivery_type": selected["delivery_type"],
                "goboxful_quoted_pickup_at": pickup_at,
                "goboxful_selected_courier_id": selected["courier_external_id"],
            })
            self.sudo().goboxful_last_error = False
            return {
                "success": True,
                "price": selected["base_price"] + selected["cod_commission"],
                "error_message": False,
                "warning_message": False,
                "courier_name": selected["courier_name"],
                "courier_logo": selected["courier_logo"],
                "delivery_type": selected["delivery_type"],
                "max_weight": selected["max_weight"],
                "max_weight_unit": account.api_weight_unit if account else "lb",
                "estimated_delivery": self._goboxful_format_naive_dt(estimated_dt) or selected["estimated_delivery"],
                "pickup_at": self._goboxful_format_utc_dt(pickup_at, account),
                "options": self._goboxful_build_display_options(
                    options, account, pickup_at, selected["courier_external_id"], order,
                ),
            }
        except Exception as exc:
            _logger.info("Boxful: cotización no disponible para %s: %s", order.name, exc)
            self.sudo().goboxful_last_error = str(exc)[:250]
            return {
                "success": False,
                "price": 0.0,
                "error_message": str(exc),
                "warning_message": False,
            }

    def goboxful_send_shipping(self, pickings):
        self.ensure_one()
        return [picking._goboxful_create_shipment_from_carrier() for picking in pickings]

    def goboxful_get_tracking_link(self, picking):
        self.ensure_one()
        return picking.goboxful_tracking_url or False

    def goboxful_cancel_shipment(self, picking):
        raise UserError(_(
            "La documentación pública de Boxful no incluye un endpoint para cancelar guías. "
            "Cancele la guía en Boxful y actualice el estado desde Odoo."
        ))

    def action_goboxful_create_account_carrier(self):
        """Compatibilidad para botones que invoquen la acción desde el transportista."""
        return True

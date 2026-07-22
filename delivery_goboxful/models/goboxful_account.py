# -*- coding: utf-8 -*-
import secrets
from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

from .goboxful_client import GoBoxfulClient, GoBoxfulMockClient
from .goboxful_location import normalize_location_name


class GoBoxfulAccount(models.Model):
    _name = "goboxful.account"
    _description = "Boxful Account Configuration"
    _rec_name = "company_id"
    _check_company_auto = True

    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        "res.company", required=True, index=True, ondelete="cascade",
        default=lambda self: self.env.company,
    )
    mode = fields.Selection(
        [
            ("mock", "Simulado (sin llamadas externas)"),
            ("test", "Pruebas con API configurada"),
            ("prod", "Producción"),
        ],
        required=True,
        default="mock",
    )
    api_url = fields.Char(required=True, default="https://api.goboxful.com")
    api_email = fields.Char(copy=False, groups="base.group_system")
    api_password = fields.Char(copy=False, groups="base.group_system")
    access_token = fields.Char(copy=False, groups="base.group_system")
    access_token_expires_at = fields.Datetime(copy=False, groups="base.group_system")
    refresh_token = fields.Char(copy=False, groups="base.group_system")
    refresh_token_expires_at = fields.Datetime(copy=False, groups="base.group_system")
    boxful_client_id = fields.Char(readonly=True, copy=False, groups="base.group_system")
    request_timeout = fields.Integer(default=25)
    test_allow_real_shipments = fields.Boolean(
        string="Permitir POST /shipment en modo pruebas",
        groups="base.group_system",
        help="Actívelo solamente cuando Boxful confirme que la cuenta o URL es segura para pruebas.",
    )

    # Dirección única de recolección por compañía.
    pickup_name = fields.Char(string="Nombre de la dirección")
    pickup_state_id = fields.Many2one(
        "goboxful.state", string="Departamento Boxful", ondelete="restrict",
        domain="[('country_code', '=', pickup_country_code)]",
    )
    pickup_city_id = fields.Many2one(
        "goboxful.city", string="Ciudad Boxful/Distrito", ondelete="restrict",
        domain="[('state_id', '=', pickup_state_id)]",
    )
    pickup_country_code = fields.Char(
        compute="_compute_pickup_country_code", store=True, size=2,
    )
    pickup_street = fields.Char(string="Calle y número")
    pickup_reference_point = fields.Char(string="Punto de referencia")
    pickup_phone = fields.Char(string="Teléfono")
    pickup_phone_area_code = fields.Char(string="Código de país", default="+503")
    pickup_latitude = fields.Float(digits=(16, 7))
    pickup_longitude = fields.Float(digits=(16, 7))
    pickup_start_hour = fields.Float(string="Inicio de recolección", default=8.0)
    pickup_end_hour = fields.Float(string="Fin de recolección", default=17.0)
    pickup_lead_minutes = fields.Integer(string="Anticipación mínima (minutos)", default=60)
    pickup_timezone = fields.Selection(
        selection=lambda self: self._tz_get(),
        default="America/El_Salvador",
        required=True,
    )
    boxful_pickup_address_id = fields.Char(string="ID de dirección Boxful", copy=False)

    responsible_user_id = fields.Many2one(
        "res.users", string="Responsable de incidencias", required=True,
        default=lambda self: self.env.user,
        domain="[('share', '=', False)]",
    )

    # Valores de respaldo para un único paquete por pedido.
    default_width_cm = fields.Float(string="Ancho predeterminado (cm)", default=30.0)
    default_length_cm = fields.Float(string="Largo predeterminado (cm)", default=40.0)
    default_height_cm = fields.Float(string="Alto predeterminado (cm)", default=20.0)
    api_weight_unit = fields.Selection(
        [("lb", "Libras"), ("kg", "Kilogramos")],
        string="Unidad de peso esperada por Boxful",
        default="lb",
        required=True,
        help=(
            "La documentación pública no declara de forma inequívoca la unidad de peso "
            "de /courier/available y /shipment. Confírmela con Boxful antes de producción."
        ),
    )
    default_weight = fields.Float(
        string="Peso mínimo/predeterminado", default=0.25,
        help="Se expresa en la unidad seleccionada para la API Boxful.",
    )
    allowed_label_hosts = fields.Text(
        string="Hosts permitidos para etiquetas",
        default="goboxful.com\napi.goboxful.com\napp.goboxful.com\nboxful.sfo3.digitaloceanspaces.com",
        groups="base.group_system",
    )
    log_payloads = fields.Boolean(
        string="Guardar cuerpos JSON en logs",
        default=False,
        groups="base.group_system",
        help=(
            "Puede incluir direcciones y datos de clientes. Manténgalo desactivado salvo "
            "durante diagnósticos controlados. Las credenciales siempre se censuran."
        ),
    )

    webhook_secret = fields.Char(copy=False, groups="base.group_system")
    webhook_url = fields.Char(compute="_compute_webhook_url")
    webhook_registered = fields.Boolean(readonly=True, copy=False)
    last_connection_at = fields.Datetime(readonly=True, copy=False)
    last_connection_message = fields.Char(readonly=True, copy=False)

    _sql_constraints = [
        ("company_unique", "unique(company_id)",
         "Solo puede existir una cuenta Boxful por compañía."),
        ("positive_timeout", "check(request_timeout >= 5)",
         "El tiempo de espera debe ser de al menos 5 segundos."),
        ("positive_dimensions",
         "check(default_width_cm > 0 and default_length_cm > 0 and default_height_cm > 0 and default_weight > 0)",
         "Las dimensiones y el peso predeterminados deben ser mayores que cero."),
    ]

    @api.model
    def _tz_get(self):
        return [(tz, tz) for tz in __import__("pytz").all_timezones]

    @api.depends("company_id")
    def _compute_pickup_country_code(self):
        for account in self:
            account.pickup_country_code = (
                account.company_id.country_id.code
                or account.company_id.partner_id.country_id.code
                or "SV"
            )

    def _compute_webhook_url(self):
        base_url = self.env["ir.config_parameter"].sudo().get_param("web.base.url")
        dbname = self.env.cr.dbname
        for account in self:
            account.webhook_url = (
                f"{base_url}/goboxful/webhook/{account.company_id.id}?db={dbname}"
                if base_url and account.company_id
                else False
            )

    def write(self, vals):
        credential_fields = {"api_url", "api_email", "api_password", "mode"}
        if credential_fields.intersection(vals):
            vals = dict(vals, access_token=False, access_token_expires_at=False,
                        refresh_token=False, refresh_token_expires_at=False,
                        boxful_client_id=False, webhook_registered=False)
        return super().write(vals)

    @api.constrains("pickup_start_hour", "pickup_end_hour")
    def _check_pickup_hours(self):
        for account in self:
            if not (0.0 <= account.pickup_start_hour < account.pickup_end_hour <= 24.0):
                raise ValidationError(_("El horario de recolección debe ser válido y la hora final debe ser posterior a la inicial."))

    @api.constrains("pickup_latitude", "pickup_longitude")
    def _check_coordinates(self):
        for account in self:
            if account.pickup_latitude and not -90 <= account.pickup_latitude <= 90:
                raise ValidationError(_("La latitud de recolección debe estar entre -90 y 90."))
            if account.pickup_longitude and not -180 <= account.pickup_longitude <= 180:
                raise ValidationError(_("La longitud de recolección debe estar entre -180 y 180."))

    def _goboxful_get_client(self):
        self.ensure_one()
        account = self.sudo()
        if account.mode == "mock":
            return GoBoxfulMockClient(account)
        return GoBoxfulClient(account)

    def _goboxful_validate_credentials(self):
        self.ensure_one()
        if self.mode != "mock" and not (self.api_email and self.api_password):
            raise UserError(_("Configure el correo y la contraseña de la cuenta Boxful."))

    def _goboxful_validate_pickup(self):
        self.ensure_one()
        missing = []
        values = {
            _("nombre"): self.pickup_name,
            _("departamento Boxful"): self.pickup_state_id,
            _("ciudad Boxful/distrito"): self.pickup_city_id,
            _("calle"): self.pickup_street,
            _("punto de referencia"): self.pickup_reference_point,
            _("teléfono"): self.pickup_phone,
            _("latitud"): self.pickup_latitude,
            _("longitud"): self.pickup_longitude,
        }
        for label, value in values.items():
            if not value:
                missing.append(label)
        if missing:
            raise UserError(_("Complete la dirección de recolección Boxful: %s") % ", ".join(missing))

    def action_create_delivery_carrier(self):
        self.ensure_one()
        existing = self.env["delivery.carrier"].sudo().search([
            ("delivery_type", "=", "goboxful"),
            ("company_id", "=", self.company_id.id),
        ], limit=1)
        if existing:
            return {
                "type": "ir.actions.act_window",
                "res_model": "delivery.carrier",
                "res_id": existing.id,
                "view_mode": "form",
            }
        product = self.env["product.product"].sudo().create({
            "name": _("Envío Boxful"),
            "type": "service",
            "sale_ok": True,
            "purchase_ok": False,
            "list_price": 0.0,
            "company_id": self.company_id.id,
        })
        vals = {
            "name": _("Boxful"),
            "delivery_type": "goboxful",
            "integration_level": "rate",
            "product_id": product.id,
            "goboxful_account_id": self.id,
        }
        if "website_published" in self.env["delivery.carrier"]._fields:
            vals["website_published"] = False
        carrier = self.env["delivery.carrier"].sudo().create(vals)
        return {
            "type": "ir.actions.act_window",
            "res_model": "delivery.carrier",
            "res_id": carrier.id,
            "view_mode": "form",
        }

    def action_test_connection(self):
        self.ensure_one()
        self._goboxful_validate_credentials()
        try:
            result = self._goboxful_get_client().get_me()
            payload = result.get("jwtPayload") or result.get("user") or result
            client_id = (
                payload.get("clientId") or payload.get("client_id")
                or (result.get("gatewayHeaders") or {}).get("x-client-id")
            )
            self.sudo().write({
                "boxful_client_id": client_id or self.boxful_client_id,
                "last_connection_at": fields.Datetime.now(),
                "last_connection_message": _("Conexión correcta"),
            })
        except Exception as exc:
            self.sudo().write({
                "last_connection_at": fields.Datetime.now(),
                "last_connection_message": str(exc)[:250],
            })
            raise
        return self._notification(_("Conexión correcta con Boxful."), "success")

    def action_clear_tokens(self):
        self.sudo().write({
            "access_token": False,
            "access_token_expires_at": False,
            "refresh_token": False,
            "refresh_token_expires_at": False,
            "boxful_client_id": False,
        })
        return self._notification(_("Tokens Boxful eliminados."), "success")

    def action_sync_locations(self):
        self.ensure_one()
        response = self._goboxful_get_client().get_states()
        states = response if isinstance(response, list) else (
            response.get("states") or response.get("data")
            or response.get("States") or []
        )
        if isinstance(states, dict):
            states = list(states.values())
        if not states:
            raise UserError(_("Boxful no devolvió departamentos/estados."))

        State = self.env["goboxful.state"].sudo()
        City = self.env["goboxful.city"].sudo()
        OdooState = self.env["res.country.state"].sudo()
        country_code = self.pickup_country_code or "SV"
        country = self.env["res.country"].sudo().search([("code", "=", country_code)], limit=1)
        now = fields.Datetime.now()
        state_count = city_count = 0

        for state_data in states:
            external_id = str(state_data.get("id") or state_data.get("_id") or "").strip()
            name = state_data.get("name") or state_data.get("state")
            if not external_id or not name:
                continue
            state = State.search([
                ("external_id", "=", external_id),
                ("country_code", "=", country_code),
            ], limit=1)
            vals = {
                "name": name,
                "country_code": country_code,
                "active": True,
                "last_sync_at": now,
            }
            if state:
                state.write(vals)
            else:
                vals["external_id"] = external_id
                state = State.create(vals)
            state_count += 1

            cities = (
                state_data.get("Cities") or state_data.get("cities")
                or state_data.get("municipalities") or []
            )
            for city_data in cities:
                city_external_id = str(city_data.get("id") or city_data.get("_id") or "").strip()
                city_name = city_data.get("name") or city_data.get("city")
                if not city_external_id or not city_name:
                    continue
                city_norm = normalize_location_name(city_name)
                # Cleos Market usa res.country.state como Municipio.
                mapped_state = OdooState.search([
                    ("country_id", "=", country.id),
                ]).filtered(lambda record: normalize_location_name(record.name) == city_norm)[:1]
                city = City.search([
                    ("external_id", "=", city_external_id),
                    ("state_id", "=", state.id),
                ], limit=1)
                city_vals = {
                    "name": city_name,
                    "active": True,
                    "latitude": city_data.get("latitude") or 0.0,
                    "longitude": city_data.get("longitude") or 0.0,
                    "last_sync_at": now,
                }
                if mapped_state:
                    # (4, id) agrega el municipio detectado sin borrar otros
                    # municipios que ya se hayan mapeado manualmente a esta
                    # misma ciudad Boxful (p. ej. las zonas de San Salvador).
                    city_vals["odoo_state_ids"] = [(4, mapped_state.id)]
                if city:
                    city.write(city_vals)
                else:
                    city_vals.update({
                        "external_id": city_external_id,
                        "state_id": state.id,
                    })
                    City.create(city_vals)
                city_count += 1

        return self._notification(
            _("Sincronizados %(states)s departamentos/estados y %(cities)s ciudades.",
              states=state_count, cities=city_count),
            "success",
        )

    def _prepare_pickup_address_payload(self):
        self.ensure_one()
        self._goboxful_validate_pickup()
        return {
            "address": self.pickup_street,
            "referencePoint": self.pickup_reference_point,
            "latitude": self.pickup_latitude,
            "longitude": self.pickup_longitude,
            "stateId": self.pickup_state_id.external_id,
            "cityId": self.pickup_city_id.external_id,
            "addressPhone": self._digits(self.pickup_phone),
            "addressAreaCode": self._digits(self.pickup_phone_area_code or "+503"),
        }

    def action_sync_pickup_address(self):
        self.ensure_one()
        client = self._goboxful_get_client()
        payload = self._prepare_pickup_address_payload()
        if self.boxful_pickup_address_id:
            response = client.update_address(self.boxful_pickup_address_id, payload)
        else:
            response = client.create_address(payload)
        address = response.get("address") or response.get("data") or response
        address_id = address.get("id") or address.get("_id")
        if not address_id:
            raise UserError(_("Boxful no devolvió el identificador de la dirección."))
        self.boxful_pickup_address_id = address_id
        return self._notification(_("Dirección de recolección sincronizada con Boxful."), "success")

    def action_generate_webhook_secret(self):
        self.ensure_one()
        self.sudo().write({
            "webhook_secret": secrets.token_urlsafe(40),
            "webhook_registered": False,
        })
        return self._notification(_("Se generó una nueva clave para el webhook."), "success")

    def action_register_webhook(self):
        self.ensure_one()
        if not self.webhook_secret:
            self.action_generate_webhook_secret()
        response = self._goboxful_get_client().register_webhook({
            "webhook": self.webhook_url,
            "accessToken": self.webhook_secret,
        })
        webhook = response.get("webhook") or response.get("data") or response
        self.webhook_registered = bool(webhook.get("active", True))
        return self._notification(_("Webhook Boxful registrado: %s") % self.webhook_url, "success")

    @api.model
    def _digits(self, value):
        return "".join(ch for ch in (value or "") if ch.isdigit())

    def _notification(self, message, notification_type="info"):
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Boxful"),
                "message": message,
                "type": notification_type,
                "sticky": False,
            },
        }

# -*- coding: utf-8 -*-
import base64
import json
import logging
from datetime import date, datetime, timezone

from markupsafe import Markup

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

GOBOXFUL_STATUS_SELECTION = [
    (-1, "Creado en sistema"),
    (1, "Registrado"),
    (2, "Recolectado"),
    (3, "En ruta a destino"),
    (4, "Entregado"),
    (5, "Guía cancelada"),
    (6, "Problemas en gestión"),
    (7, "Finalizada con problemas"),
    (8, "No entregado"),
    (9, "Devuelto en bodega"),
    (10, "No recolectado"),
    (11, "Ubicado en locker"),
]
FINAL_STATUS_CODES = {4, 5, 7, 8, 9, 10}
PROBLEM_STATUS_CODES = {5, 6, 7, 8, 9, 10}
STATUS_RANK = {-1: 1, 1: 2, 2: 3, 3: 4, 11: 4, 4: 5}
STATUS_BY_DESCRIPTION = {
    "creado en sistema": -1,
    "registrado": 1,
    "recolectado": 2,
    "en ruta a destino": 3,
    "entregado": 4,
    "guía cancelada": 5,
    "guia cancelada": 5,
    "problemas en gestión": 6,
    "problemas en gestion": 6,
    "finalizada con problemas": 7,
    "no entregado": 8,
    "devuelto en bodega": 9,
    "no recolectado": 10,
    "ubicado en locker": 11,
}


class StockPicking(models.Model):
    _inherit = "stock.picking"

    is_goboxful = fields.Boolean(compute="_compute_is_goboxful")
    goboxful_account_id = fields.Many2one(
        "goboxful.account", string="Cuenta Boxful", compute="_compute_goboxful_account",
        store=True, check_company=True,
    )
    goboxful_option_ids = fields.One2many(
        "goboxful.courier.option", "picking_id", string="Couriers Boxful",
    )
    goboxful_selected_option_id = fields.Many2one(
        "goboxful.courier.option", string="Courier seleccionado", ondelete="set null",
        domain="[('picking_id', '=', id)]",
    )
    goboxful_courier_id = fields.Char(string="ID courier Boxful", copy=False)
    goboxful_courier_name = fields.Char(string="Courier Boxful", copy=False)
    goboxful_currency_id = fields.Many2one(related="company_id.currency_id", store=True)
    goboxful_quote_price = fields.Monetary(
        string="Tarifa Boxful", currency_field="goboxful_currency_id", copy=False,
    )
    goboxful_cod_commission = fields.Monetary(
        string="Comisión COD", currency_field="goboxful_currency_id", copy=False,
    )
    goboxful_estimated_delivery = fields.Char(string="Entrega estimada", copy=False)
    goboxful_shipment_id = fields.Char(string="ID envío Boxful", copy=False, index=True)
    goboxful_shipment_number = fields.Char(string="Número de guía Boxful", copy=False, index=True)
    goboxful_status_code = fields.Integer(string="Código de estado Boxful", copy=False, index=True)
    goboxful_status_description = fields.Char(string="Estado Boxful", copy=False)
    goboxful_tracking_url = fields.Char(string="URL de seguimiento Boxful", copy=False)
    goboxful_label_url = fields.Char(string="URL de etiqueta Boxful", copy=False)
    goboxful_label_attachment_id = fields.Many2one(
        "ir.attachment", string="Etiqueta Boxful", copy=False, ondelete="set null",
    )
    goboxful_last_sync_at = fields.Datetime(copy=False)
    goboxful_webhook_date = fields.Datetime(copy=False)
    goboxful_request_state = fields.Selection([
        ("draft", "Sin crear"),
        ("quoted", "Cotizado"),
        ("creating", "Creando"),
        ("created", "Creado"),
        ("verification_pending", "Verificación pendiente"),
        ("error", "Error"),
        ("cancelled", "Cancelado"),
    ], default="draft", copy=False, index=True)
    goboxful_last_error = fields.Text(copy=False)

    _sql_constraints = [
        ("goboxful_shipment_id_unique", "unique(goboxful_shipment_id)",
         "El identificador de envío Boxful ya está asignado a otra transferencia."),
        ("goboxful_shipment_number_unique", "unique(goboxful_shipment_number)",
         "El número de guía Boxful ya está asignado a otra transferencia."),
    ]

    @api.depends("carrier_id.delivery_type")
    def _compute_is_goboxful(self):
        for picking in self:
            picking.is_goboxful = picking.carrier_id.delivery_type == "goboxful"

    @api.depends("carrier_id.goboxful_account_id", "company_id")
    def _compute_goboxful_account(self):
        Account = self.env["goboxful.account"]
        for picking in self:
            account = picking.carrier_id.goboxful_account_id
            if picking.is_goboxful and (not account or account.company_id != picking.company_id):
                account = Account.search([
                    ("company_id", "=", picking.company_id.id), ("active", "=", True),
                ], limit=1)
            picking.goboxful_account_id = account

    @api.onchange("goboxful_selected_option_id")
    def _onchange_goboxful_selected_option(self):
        self._goboxful_apply_selected_option()

    def _goboxful_apply_selected_option(self):
        for picking in self:
            option = picking.goboxful_selected_option_id
            if option:
                picking.update({
                    "goboxful_courier_id": option.courier_external_id,
                    "goboxful_courier_name": option.courier_name,
                    "goboxful_quote_price": option.base_price,
                    "goboxful_cod_commission": option.cod_commission,
                    "goboxful_estimated_delivery": option.estimated_delivery,
                    "goboxful_request_state": "quoted",
                })

    def _goboxful_validate_for_shipment(self):
        self.ensure_one()
        if not self.is_goboxful:
            raise UserError(_("La transferencia no utiliza el método Boxful."))
        if self.picking_type_code != "outgoing":
            raise UserError(_("Boxful solo puede crear envíos para transferencias salientes."))
        if self.state == "cancel":
            raise UserError(_("No puede crear una guía para una transferencia cancelada."))
        if self.goboxful_shipment_id or self.goboxful_shipment_number:
            raise UserError(_("Esta transferencia ya tiene una guía Boxful."))
        if self.goboxful_request_state in ("creating", "verification_pending"):
            raise UserError(_(
                "La creación anterior está pendiente de verificación. Revise Boxful antes de reintentar."
            ))
        if not self.sale_id:
            raise UserError(_("La transferencia debe estar vinculada a un pedido de venta."))
        if self.sale_id._goboxful_has_blocked_products():
            raise UserError(_("El pedido contiene productos no transportables por Boxful."))

    def action_goboxful_quote_couriers(self):
        for picking in self:
            picking._goboxful_validate_for_shipment()
            carrier = picking.carrier_id
            options, _package, _payload = carrier._goboxful_get_options_for_order(
                picking.sale_id, force=True
            )
            picking.goboxful_option_ids.unlink()
            created = self.env["goboxful.courier.option"]
            for option in options:
                created |= self.env["goboxful.courier.option"].create({
                    "picking_id": picking.id,
                    "courier_external_id": option["courier_external_id"],
                    "courier_name": option["courier_name"],
                    "delivery_type": option["delivery_type"],
                    "base_price": option["base_price"],
                    "cod_commission": option["cod_commission"],
                    "estimated_delivery": option["estimated_delivery"],
                    "raw_payload": json.dumps(option.get("raw") or {}, ensure_ascii=False, default=str),
                })
            selected = created.sorted(lambda opt: (opt.total_price, opt.id))[:1]
            picking.goboxful_selected_option_id = selected
            picking._goboxful_apply_selected_option()
            picking.message_post(body=_(
                "Boxful encontró %(count)s couriers del mismo día. Se seleccionó <b>%(name)s</b> por %(price).2f.",
                count=len(created), name=selected.courier_name,
                price=selected.total_price,
            ))
        return {"type": "ir.actions.client", "tag": "reload"}

    def _goboxful_split_name(self, name):
        parts = (name or "Cliente").strip().split()
        if len(parts) == 1:
            return parts[0], "-"
        return " ".join(parts[:-1]), parts[-1]

    def _goboxful_prepare_shipment_payload(self):
        self.ensure_one()
        account = self.goboxful_account_id
        carrier = self.carrier_id
        order = self.sale_id
        partner = order.partner_shipping_id
        city = carrier._goboxful_validate_destination(partner, account)
        package = carrier._goboxful_package_from_lines(
            order.order_line, account, order._compute_amount_total_without_delivery()
        )
        first_name, last_name = self._goboxful_split_name(partner.name)
        phone = carrier._goboxful_phone(partner)
        cod, cod_amount = carrier._goboxful_cod_data(order)
        reference = (
            partner.goboxful_reference_point or partner.street2
            or partner.city
            or _("Sin punto de referencia adicional")
        )
        instructions = partner.goboxful_delivery_instructions or _("Entregar al destinatario indicado.")
        payload = {
            "recolectionDate": carrier._goboxful_pickup_datetime(account),
            "courierId": self.goboxful_courier_id,
            "parcels": [package],
            "cod": cod,
            "codAmount": cod_amount or 0,
            "customerPhone": phone,
            "customerPhoneAreaCode": carrier._goboxful_area_code(partner, account.pickup_phone_area_code),
            "customerName": first_name,
            "customerLastname": last_name,
            "customerEmail": partner.email,
            "customerAddress": ", ".join(filter(None, [partner.street, partner.street2, partner.city])),
            "customerState": city.state_id.external_id,
            "customerCity": city.external_id,
            "customerAddressReferencePoint": reference,
            "instructions": instructions,
            "customerAddressLatitude": partner.partner_latitude,
            "customerAddressLongitude": partner.partner_longitude,
            "lockerId": None,
        }
        if account.boxful_pickup_address_id:
            payload["recolectionAddressId"] = account.boxful_pickup_address_id
        else:
            account._goboxful_validate_pickup()
            payload["recolectionAddress"] = {
                "address": account.pickup_street,
                "referencePoint": account.pickup_reference_point,
                "latitude": account.pickup_latitude,
                "longitude": account.pickup_longitude,
                "stateId": account.pickup_state_id.external_id,
                "cityId": account.pickup_city_id.external_id,
                "areaCode": account.pickup_phone_area_code or "+503",
                "phone": account._digits(account.pickup_phone),
            }
        return payload

    @api.model
    def _goboxful_extract_shipment(self, response):
        if not isinstance(response, dict):
            return {}
        for key in ("shipmentData", "shipment", "data"):
            value = response.get(key)
            if isinstance(value, dict):
                nested = self._goboxful_extract_shipment(value)
                return nested or value
        return response

    def _goboxful_create_label_attachment(self, label_url):
        self.ensure_one()
        if not label_url:
            return False
        content, mime = self.goboxful_account_id._goboxful_get_client().download_label(
            label_url, res_model="stock.picking", res_id=self.id,
        )
        filename = "Boxful_%s.pdf" % (self.goboxful_shipment_number or self.name).replace("/", "-")
        attachment = self.env["ir.attachment"].sudo().create({
            "name": filename,
            "type": "binary",
            "datas": base64.b64encode(content),
            "mimetype": mime.split(";")[0] if mime else "application/pdf",
            "res_model": "stock.picking",
            "res_id": self.id,
        })
        self.goboxful_label_attachment_id = attachment
        self.message_post(
            body=_("Etiqueta Boxful generada: %s") % filename,
            attachment_ids=[attachment.id],
        )
        return attachment

    def _goboxful_create_shipment_from_carrier(self):
        self.ensure_one()
        self._goboxful_validate_for_shipment()
        if not self.goboxful_selected_option_id:
            self.action_goboxful_quote_couriers()
        self._goboxful_apply_selected_option()
        if not self.goboxful_courier_id:
            raise UserError(_("Seleccione un courier Boxful antes de crear la guía."))

        self.write({"goboxful_request_state": "creating", "goboxful_last_error": False})
        payload = self._goboxful_prepare_shipment_payload()
        try:
            response = self.goboxful_account_id._goboxful_get_client().create_shipment(
                payload, res_model="stock.picking", res_id=self.id,
            )
            shipment = self._goboxful_extract_shipment(response)
            shipment_id = shipment.get("id") or shipment.get("_id")
            shipment_number = shipment.get("shipmentNumber") or shipment.get("trackingNumber")
            if not (shipment_id and shipment_number):
                raise UserError(_("Boxful no devolvió el ID y número de guía del envío."))
            status_code = self._goboxful_status_code_from_data(shipment)
            vals = {
                "goboxful_shipment_id": str(shipment_id),
                "goboxful_shipment_number": str(shipment_number),
                "goboxful_status_code": status_code,
                "goboxful_status_description": shipment.get("statusDescription") or "Creado en sistema",
                "goboxful_tracking_url": shipment.get("trackingUrl"),
                "goboxful_label_url": shipment.get("labelUrl"),
                "goboxful_courier_name": shipment.get("courierName") or self.goboxful_courier_name,
                "goboxful_request_state": "created",
                "goboxful_last_sync_at": fields.Datetime.now(),
            }
            self.write(vals)
            self._goboxful_sync_sale_status()
            self.message_post(body=Markup(
                _("Guía Boxful <b>{number}</b> creada con <b>{courier}</b>.")
            ).format(number=shipment_number, courier=self.goboxful_courier_name))
            attachment = False
            if self.goboxful_label_url:
                try:
                    attachment = self._goboxful_create_label_attachment(self.goboxful_label_url)
                except Exception as exc:
                    self.message_post(body=_("La guía fue creada, pero no se pudo descargar la etiqueta: %s") % exc)
            return {
                "exact_price": self.goboxful_quote_price + self.goboxful_cod_commission,
                "tracking_number": str(shipment_number),
                "attachment": attachment,
            }
        except Exception as exc:
            # La API pública no ofrece una clave de idempotencia. Ante cualquier
            # error después de iniciar POST /shipment, se exige verificación
            # manual antes de permitir otro intento, para evitar guías duplicadas.
            self.write({
                "goboxful_request_state": "verification_pending",
                "goboxful_last_error": str(exc),
            })
            self._goboxful_schedule_issue(_("Error creando el envío Boxful: %s") % exc)
            raise

    def action_goboxful_reset_verification(self):
        for picking in self:
            if picking.goboxful_shipment_id or picking.goboxful_shipment_number:
                raise UserError(_("La transferencia ya tiene una guía Boxful."))
            picking.write({
                "goboxful_request_state": "draft",
                "goboxful_last_error": False,
            })
        return {"type": "ir.actions.client", "tag": "reload"}

    def action_goboxful_create_shipment(self):
        self.ensure_one()
        result = self._goboxful_create_shipment_from_carrier()
        # Replica los campos estándar que Odoo usa para tracking/costo.
        self.write({
            "carrier_tracking_ref": result.get("tracking_number"),
            "carrier_price": result.get("exact_price", 0.0),
        })
        attachment = result.get("attachment") or self.goboxful_label_attachment_id
        if attachment:
            return {
                "type": "ir.actions.act_url",
                "url": "/web/content/%s?download=0" % attachment.id,
                "target": "new",
            }
        return {"type": "ir.actions.client", "tag": "reload"}

    @api.model
    def _goboxful_status_code_from_data(self, data):
        raw = data.get("status") if isinstance(data, dict) else False
        try:
            return int(raw)
        except (TypeError, ValueError):
            description = str((data or {}).get("statusDescription") or "").strip().lower()
            return STATUS_BY_DESCRIPTION.get(description, False)

    def _goboxful_update_status(self, code, description=None, event_date=None, source="API"):
        self.ensure_one()
        if code is False or code is None:
            return False
        code = int(code)
        current = self.goboxful_status_code
        # Los estados de incidencia se aplican siempre. Los logísticos normales
        # no retroceden por webhooks fuera de orden.
        if current in PROBLEM_STATUS_CODES and code not in PROBLEM_STATUS_CODES and code != 4:
            return False
        if code not in PROBLEM_STATUS_CODES and current not in PROBLEM_STATUS_CODES:
            if STATUS_RANK.get(code, 0) < STATUS_RANK.get(current, 0):
                return False
        changed = code != current or (description and description != self.goboxful_status_description)
        vals = {
            "goboxful_status_code": code,
            "goboxful_status_description": description or dict(GOBOXFUL_STATUS_SELECTION).get(code),
            "goboxful_last_sync_at": fields.Datetime.now(),
        }
        if event_date:
            vals["goboxful_webhook_date"] = event_date
        if code == 5:
            vals["goboxful_request_state"] = "cancelled"
        self.write(vals)
        self._goboxful_sync_sale_status()
        if changed:
            message = Markup(
                _("Boxful ({source}): el envío pasó a <b>{status}</b>.")
            ).format(source=source, status=vals["goboxful_status_description"])
            self.message_post(body=message)
            if self.sale_id:
                self.sale_id.message_post(body=message)
            if code in PROBLEM_STATUS_CODES:
                self._goboxful_schedule_issue(_(
                    "Boxful reportó: %s") % vals["goboxful_status_description"])
        return changed

    def _goboxful_sync_sale_status(self):
        for picking in self.filtered("sale_id"):
            picking.sale_id.sudo().write({
                "goboxful_delivery_status_code": picking.goboxful_status_code,
                "goboxful_delivery_status_description": picking.goboxful_status_description,
                "goboxful_delivery_tracking_url": picking.goboxful_tracking_url,
            })

    def _goboxful_schedule_issue(self, note):
        self.ensure_one()
        account = self.goboxful_account_id
        user = account.responsible_user_id or self.user_id or self.env.user
        existing = self.activity_ids.filtered(
            lambda activity: activity.user_id == user
            and activity.activity_type_id == self.env.ref("mail.mail_activity_data_warning")
        )
        if not existing:
            self.activity_schedule(
                "mail.mail_activity_data_warning",
                date_deadline=date.today(),
                summary=_("Incidencia Boxful"),
                note=note,
                user_id=user.id,
            )

    def action_goboxful_refresh_status(self):
        for picking in self:
            if not (picking.is_goboxful and picking.goboxful_shipment_id):
                continue
            if picking.goboxful_account_id.mode == "mock":
                current = picking.goboxful_status_code
                next_code = {-1: 1, 1: 2, 2: 3, 3: 4}.get(current, 1)
                picking._goboxful_update_status(
                    next_code, dict(GOBOXFUL_STATUS_SELECTION).get(next_code), source="Simulador"
                )
                continue
            response = picking.goboxful_account_id._goboxful_get_client().get_shipment(
                picking.goboxful_shipment_id,
                res_model="stock.picking", res_id=picking.id,
            )
            shipment = picking._goboxful_extract_shipment(response)
            code = picking._goboxful_status_code_from_data(shipment)
            picking._goboxful_update_status(
                code, shipment.get("statusDescription"), source="Consulta API"
            )
            updates = {}
            if shipment.get("trackingUrl"):
                updates["goboxful_tracking_url"] = shipment["trackingUrl"]
            if shipment.get("labelUrl"):
                updates["goboxful_label_url"] = shipment["labelUrl"]
            if updates:
                picking.write(updates)
        return {"type": "ir.actions.client", "tag": "reload"}

    def action_goboxful_open_tracking(self):
        self.ensure_one()
        if not self.goboxful_tracking_url:
            raise UserError(_("Boxful todavía no ha proporcionado un enlace de seguimiento."))
        return {"type": "ir.actions.act_url", "url": self.goboxful_tracking_url, "target": "new"}

    def action_goboxful_open_label(self):
        self.ensure_one()
        if self.goboxful_label_attachment_id:
            return {
                "type": "ir.actions.act_url",
                "url": "/web/content/%s?download=0" % self.goboxful_label_attachment_id.id,
                "target": "new",
            }
        if self.goboxful_label_url:
            return {"type": "ir.actions.act_url", "url": self.goboxful_label_url, "target": "new"}
        raise UserError(_("La transferencia no tiene etiqueta Boxful."))

    @api.model
    def _goboxful_process_webhook(self, account, payload):
        shipment_id = str(payload.get("shipmentId") or "")
        shipment_number = str(payload.get("shipmentNumber") or "")
        domain = [("company_id", "=", account.company_id.id)]
        if shipment_id and shipment_number:
            domain += ["|", ("goboxful_shipment_id", "=", shipment_id),
                       ("goboxful_shipment_number", "=", shipment_number)]
        elif shipment_id:
            domain.append(("goboxful_shipment_id", "=", shipment_id))
        elif shipment_number:
            domain.append(("goboxful_shipment_number", "=", shipment_number))
        else:
            return {"ok": False, "message": "missing_shipment_identifier"}
        picking = self.sudo().search(domain, limit=1)
        safe_payload = dict(payload)
        safe_payload.pop("accessToken", None)
        event_hash = self.env["goboxful.webhook.event"].hash_payload(account.id, safe_payload)
        existing = self.env["goboxful.webhook.event"].sudo().search([
            ("event_hash", "=", event_hash),
        ], limit=1)
        if existing:
            return {"ok": True, "duplicate": True}
        event_date = False
        if payload.get("date"):
            try:
                parsed = datetime.fromisoformat(str(payload["date"]).replace("Z", "+00:00"))
                if parsed.tzinfo:
                    parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
                event_date = parsed
            except Exception:
                event_date = False
        code = self._goboxful_status_code_from_data(payload)
        event = self.env["goboxful.webhook.event"].sudo().create({
            "event_hash": event_hash,
            "company_id": account.company_id.id,
            "account_id": account.id,
            "picking_id": picking.id if picking else False,
            "shipment_id": shipment_id,
            "shipment_number": shipment_number,
            "status_code": code or 0,
            "event_date": event_date,
            "payload": json.dumps(safe_payload, ensure_ascii=False, default=str),
        })
        if not picking:
            event.write({"processed": True, "processing_message": "shipment_not_found"})
            return {"ok": True, "message": "shipment_not_found"}
        picking._goboxful_update_status(
            code, payload.get("statusDescription"), event_date=event_date, source="Webhook"
        )
        event.write({"processed": True, "processing_message": "updated"})
        return {"ok": True, "picking_id": picking.id}

    @api.model
    def _cron_goboxful_sync_status(self):
        pickings = self.sudo().search([
            ("carrier_id.delivery_type", "=", "goboxful"),
            ("goboxful_shipment_id", "!=", False),
            ("goboxful_status_code", "not in", list(FINAL_STATUS_CODES)),
            ("state", "!=", "cancel"),
        ], limit=100)
        for picking in pickings:
            try:
                picking.action_goboxful_refresh_status()
            except Exception:
                _logger.warning("Boxful: no se pudo actualizar %s", picking.name, exc_info=True)
        return True

    @api.model
    def _cron_goboxful_cleanup_logs(self):
        cutoff = fields.Datetime.subtract(fields.Datetime.now(), days=45)
        self.env["goboxful.api.log"].sudo().search([
            ("create_date", "<", cutoff),
        ]).unlink()
        return True

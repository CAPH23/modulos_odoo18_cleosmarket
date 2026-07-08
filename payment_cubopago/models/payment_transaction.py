# -*- coding: utf-8 -*-
# Part of the CuboPago payment module.
# Copyright 2026 Carlos Palacios
# License OPL-1 (Odoo Proprietary License v1.0). See LICENSE file for full details.
import json
import logging
import pprint

from odoo import _, fields, models
from odoo.exceptions import ValidationError

from odoo.addons.payment_cubopago import const

_logger = logging.getLogger(__name__)


class PaymentTransaction(models.Model):
    _inherit = 'payment.transaction'

    cubopago_payment_intent_token = fields.Char(
        string='CuboPago Payment Intent Token', readonly=True, copy=False,
    )
    cubopago_identifier = fields.Char(
        string='CuboPago Identifier', readonly=True, copy=False,
    )
    cubopago_status = fields.Char(
        string='CuboPago Estado', readonly=True, copy=False,
    )
    cubopago_validation_source = fields.Char(
        string='Fuente de validación CuboPago', readonly=True, copy=False,
    )
    cubopago_last_payload = fields.Text(
        string='Último payload enviado a CuboPago', readonly=True, copy=False,
        groups='base.group_system',
    )
    cubopago_last_notification = fields.Text(
        string='Última notificación CuboPago', readonly=True, copy=False,
        groups='base.group_system',
    )

    # -------------------------------------------------------------------------
    # Rendering: create the payment link and redirect the customer
    # -------------------------------------------------------------------------
    def _get_specific_rendering_values(self, processing_values):
        res = super()._get_specific_rendering_values(processing_values)
        if self.provider_code != const.PROVIDER_CODE:
            return res

        self.ensure_one()
        if not self.reference:
            raise ValidationError(_('CuboPago: la transacción no tiene referencia.'))
        if not self.amount or self.amount <= 0:
            raise ValidationError(_('CuboPago: el monto debe ser mayor que cero.'))

        payload = self._cubopago_build_link_payload()
        self.provider_id._cubopago_log('info', 'CuboPago payload para %s:\n%s', self.reference, pprint.pformat(payload))

        response = self.provider_id._cubopago_make_request(
            const.ENDPOINT_CREATE_LINK,
            payload=payload,
            method='POST',
            reference=self.reference,
        )

        redirect_uri = response.get('cuboRedirectUri')
        token = response.get('paymentIntentToken')
        if not redirect_uri:
            _logger.error('CuboPago no devolvió cuboRedirectUri. Respuesta: %s', response)
            raise ValidationError(_('CuboPago: no se recibió la URL de pago.'))

        self.write({
            'provider_reference': str(token or ''),
            'cubopago_payment_intent_token': str(token or ''),
            'cubopago_last_payload': json.dumps(payload, ensure_ascii=False, indent=2),
        })
        return {'api_url': redirect_uri}

    def _cubopago_build_link_payload(self):
        self.ensure_one()
        provider = self.provider_id
        order = self.sale_order_ids[:1] if 'sale_order_ids' in self._fields else self.env['sale.order']

        payload = {
            'description': self._cubopago_format_description(order),
            # CuboPago requires the amount as an integer number of cents.
            'amount': self._cubopago_amount_to_cents(self.amount),
            'redirectUri': '%s/payment/cubopago/return' % provider._cubopago_get_base_url(),
            'metadata': {
                'orderId': self.reference,
                'reference': self.reference,
            },
        }

        if provider.cubopago_monthly_installment_id and provider.cubopago_monthly_installment_id > 0:
            payload['monthlyInstallmentId'] = int(provider.cubopago_monthly_installment_id)

        if provider.cubopago_send_client_info:
            client = self._cubopago_build_client_info()
            payload.update(client)

        if provider.cubopago_send_items and order:
            items = self._cubopago_build_items(order, provider.cubopago_max_items)
            if items:
                payload['items'] = items

        return payload

    @staticmethod
    def _cubopago_amount_to_cents(amount):
        return int(round(float(amount) * 100))

    def _cubopago_format_description(self, order):
        provider = self.provider_id
        template = provider.cubopago_payment_description or 'Pedido {reference}'
        order_name = order.name if order else self.reference
        try:
            text = template.format(
                reference=self.reference,
                order_name=order_name,
                amount='%.2f' % self.amount,
                currency=self.currency_id.name,
            )
        except Exception:
            text = 'Pedido %s' % self.reference
        return text[:255]

    def _cubopago_build_client_info(self):
        partner = self.partner_id
        info = {}
        if not partner:
            return info
        if partner.name:
            info['clientName'] = partner.name[:120]
        if partner.email:
            info['clientEmail'] = partner.email[:120]
        phone = partner.phone or partner.mobile
        if phone:
            info['clientPhone'] = phone.strip()[:20]
        return info

    def _cubopago_build_items(self, order, max_items):
        max_items = max(int(max_items or 0), 0)
        if not max_items:
            return []
        items = []
        valid_lines = order.order_line.filtered(lambda line: not line.display_type)
        for line in valid_lines[:max_items]:
            name = str(line.name or line.product_id.display_name or 'Producto').replace('\n', ' ').strip()
            qty = line.product_uom_qty or 1
            unit_price = line.price_unit or 0.0
            items.append({
                'name': name[:120],
                'price': '%.2f' % unit_price,
                'quantity': int(qty) if float(qty).is_integer() else qty,
            })
        return items

    # -------------------------------------------------------------------------
    # Notification handling
    # -------------------------------------------------------------------------
    def _get_tx_from_notification_data(self, provider_code, notification_data):
        if provider_code != const.PROVIDER_CODE:
            return super()._get_tx_from_notification_data(provider_code, notification_data)

        reference = self._cubopago_extract_reference(notification_data)
        token = self._cubopago_extract_token(notification_data)

        tx = self.env['payment.transaction']
        if reference:
            tx = self.search([('reference', '=', reference), ('provider_code', '=', const.PROVIDER_CODE)], limit=1)
        if not tx and token:
            tx = self.search([
                ('cubopago_payment_intent_token', '=', token),
                ('provider_code', '=', const.PROVIDER_CODE),
            ], limit=1)
        if not tx:
            raise ValidationError(_('CuboPago: no se encontró la transacción (ref=%s, token=%s).', reference, token))
        return tx

    def _process_notification_data(self, notification_data):
        if self.provider_code != const.PROVIDER_CODE:
            return super()._process_notification_data(notification_data)

        super()._process_notification_data(notification_data)
        self.ensure_one()
        source = notification_data.get('_cubopago_source') or 'webhook'
        self.provider_id._cubopago_log('info', 'Procesando notificación CuboPago (%s) para %s:\n%s', source, self.reference, pprint.pformat(notification_data))

        token = self._cubopago_extract_token(notification_data) or self.cubopago_payment_intent_token
        identifier = notification_data.get('identifier') or notification_data.get('referenceId')

        self.write({
            'cubopago_last_notification': json.dumps(notification_data, ensure_ascii=False, indent=2, default=str),
            'cubopago_validation_source': source,
            'cubopago_identifier': str(identifier or ''),
        })

        # MANDATORY server-to-server verification. CuboPago webhooks are not
        # signed, so we never trust the payload on its own: we re-query the
        # transaction by its token to confirm the real status and amount.
        api_data = {}
        if token:
            try:
                api_data = self.provider_id._cubopago_fetch_transaction(token, reference=self.reference) or {}
            except Exception:
                _logger.exception('CuboPago: fallo al verificar la transacción %s por API.', self.reference)
                api_data = {}
            if api_data:
                self.provider_id._cubopago_log('info', 'CuboPago verificación por API para %s:\n%s', self.reference, pprint.pformat(api_data))

        if not api_data:
            # Without a verified API response we cannot safely confirm an unsigned
            # webhook. Leave the transaction pending so a later check can resolve it.
            _logger.warning('CuboPago: sin verificación por API para %s; se deja pendiente.', self.reference)
            self._set_pending()
            return

        # Verify amount against the authoritative API response (amount in dollars).
        api_amount = self._cubopago_extract_amount_from_api(api_data)
        if api_amount is not None and self.currency_id.compare_amounts(api_amount, self.amount) != 0:
            _logger.warning('CuboPago: discrepancia de monto para %s. Esperado %s, API %s.', self.reference, self.amount, api_amount)
            self._set_error(_('CuboPago: el monto verificado (%s) no coincide con el esperado (%s).', api_amount, self.amount))
            return

        status = str(api_data.get('status') or notification_data.get('status') or '').strip().lower()
        self.write({'cubopago_status': status})

        if status in const.STATUS_APPROVED:
            _logger.info('CuboPago: transacción aprobada para %s.', self.reference)
            self._cubopago_mark_done_and_confirm_order()
            return
        if status in const.STATUS_PENDING:
            _logger.info('CuboPago: transacción pendiente para %s.', self.reference)
            self._set_pending()
            return
        if status in const.STATUS_CANCELLED:
            _logger.info('CuboPago: transacción cancelada para %s.', self.reference)
            self._set_canceled(state_message=_('CuboPago: la transacción fue cancelada (estado: %s).', status))
            return
        if status in const.STATUS_REJECTED:
            _logger.warning('CuboPago: transacción rechazada para %s. Estado: %s', self.reference, status)
            self._set_error(_('CuboPago: la transacción fue rechazada (estado: %s).', status))
            return

        _logger.warning('CuboPago: estado no reconocido para %s: %s', self.reference, status)
        self._set_pending()

    def _cubopago_mark_done_and_confirm_order(self):
        if self.state != 'done':
            self._set_done()
        if 'sale_order_ids' in self._fields:
            for order in self.sale_order_ids:
                if order.state in ('draft', 'sent'):
                    _logger.info('CuboPago: confirmando orden %s de la transacción %s.', order.name, self.reference)
                    order.action_confirm()

    # -------------------------------------------------------------------------
    # Extraction helpers
    # -------------------------------------------------------------------------
    def _cubopago_extract_reference(self, data):
        metadata = self._cubopago_get_value(data, 'metadata') or {}
        if isinstance(metadata, dict):
            ref = self._cubopago_get_value(metadata, 'orderId', 'reference')
            if ref:
                return ref
        return self._cubopago_get_value(data, 'orderId', 'reference')

    def _cubopago_extract_token(self, data):
        return self._cubopago_get_value(data, 'paymentIntentToken', 'identifier', 'token')

    def _cubopago_extract_amount_from_api(self, api_data):
        """The transactions endpoint returns the amount as a decimal string in
        the major currency unit (e.g. '1.00')."""
        value = self._cubopago_get_value(api_data, 'amount')
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def _cubopago_get_value(self, data, *keys):
        if not isinstance(data, dict):
            return None
        for key in keys:
            if key in data:
                return data[key]
        lower_map = {str(k).lower(): v for k, v in data.items()}
        for key in keys:
            value = lower_map.get(str(key).lower())
            if value is not None:
                return value
        return None

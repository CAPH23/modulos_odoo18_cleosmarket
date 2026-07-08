# -*- coding: utf-8 -*-
import logging

from odoo import _, models
from odoo.exceptions import ValidationError

from odoo.addons.payment_cobro_entrega import const
from odoo.addons.payment_cobro_entrega.controllers.main import CobroEntregaController

_logger = logging.getLogger(__name__)


class PaymentTransaction(models.Model):
    _inherit = 'payment.transaction'

    def _get_specific_rendering_values(self, processing_values):
        """Return provider-specific rendering values for the redirect form."""
        res = super()._get_specific_rendering_values(processing_values)
        if self.provider_code != const.PROVIDER_CODE:
            return res

        return {
            'api_url': CobroEntregaController._process_url,
            'reference': self.reference,
        }

    def _get_tx_from_notification_data(self, provider_code, notification_data):
        """Find the transaction from the posted reference."""
        tx = super()._get_tx_from_notification_data(provider_code, notification_data)
        if provider_code != const.PROVIDER_CODE or len(tx) == 1:
            return tx

        reference = notification_data.get('reference')
        tx = self.search([
            ('reference', '=', reference),
            ('provider_code', '=', const.PROVIDER_CODE),
        ])
        if not tx:
            raise ValidationError(
                _('Cobro contra entrega: no transaction found matching reference %s.', reference)
            )
        return tx

    def _process_notification_data(self, notification_data):
        """Mark the transaction as pending because payment will be collected on delivery."""
        super()._process_notification_data(notification_data)
        if self.provider_code != const.PROVIDER_CODE:
            return

        _logger.info(
            "Cobro contra entrega selected for transaction %s: setting transaction as pending",
            self.reference,
        )
        processed_txs = self._set_pending(
            state_message=_(
                'El cliente seleccionó Cobro contra entrega. El pedido queda confirmado para envío '
                'y el pago permanecerá pendiente hasta que se registre el cobro al momento de la entrega.'
            )
        )
        processed_txs._cleo_cod_confirm_sale_orders()
        processed_txs._cleo_cod_send_sale_order_email()

    def _cleo_cod_get_sale_orders(self):
        """Return the sale orders linked to the transaction."""
        self.ensure_one()
        sale_orders = self.env['sale.order']
        if 'sale_order_ids' in self._fields:
            sale_orders |= self.sale_order_ids
        if not sale_orders and 'invoice_ids' in self._fields:
            sale_orders |= self.invoice_ids.invoice_line_ids.sale_line_ids.order_id
        return sale_orders

    def _cleo_cod_get_customer_invoices(self):
        """Return posted customer invoices linked to the transaction sale orders."""
        self.ensure_one()
        invoices = self.env['account.move']
        sale_orders = self._cleo_cod_get_sale_orders()
        if sale_orders and 'invoice_ids' in sale_orders._fields:
            invoices |= sale_orders.invoice_ids
        if 'invoice_ids' in self._fields:
            invoices |= self.invoice_ids
        return invoices.filtered(
            lambda move: move.state == 'posted'
            and move.move_type in ('out_invoice', 'out_refund')
        )

    def _cleo_cod_is_fully_paid(self):
        """Return True when the related posted customer invoices are fully paid.

        This is used by portal QWeb templates to hide the pending-payment notices once Odoo
        already shows the invoice as paid. If there are no posted invoices yet, the order
        must still be treated as pending payment.
        """
        self.ensure_one()
        if self.provider_code != const.PROVIDER_CODE:
            return False
        invoices = self.sudo()._cleo_cod_get_customer_invoices()
        if not invoices:
            return False
        invoices_to_pay = invoices.filtered(lambda move: move.move_type == 'out_invoice')
        if not invoices_to_pay:
            return False
        return all(invoice.payment_state in ('paid', 'reversed') for invoice in invoices_to_pay)

    def _cleo_cod_confirm_sale_orders(self):
        """Confirm draft/sent sale orders so stock deliveries can be created."""
        for tx in self.sudo().filtered(lambda transaction: transaction.operation != 'validation'):
            sale_orders = tx._cleo_cod_get_sale_orders().filtered(
                lambda order: order.state in ('draft', 'sent')
            )
            if sale_orders:
                sale_orders.with_context(tracking_disable=True).action_confirm()

    def _cleo_cod_send_sale_order_email(self):
        """Send the clear pending-payment email to the related sale orders."""
        for tx in self.sudo().filtered(lambda transaction: transaction.operation != 'validation'):
            sale_orders = tx._cleo_cod_get_sale_orders().filtered(
                lambda order: order.state in ('sale', 'done')
            )
            sale_orders._cleo_cod_send_pending_payment_email()

    def _log_received_message(self):
        """Avoid logging the generic received-payment message for this manual provider."""
        other_provider_txs = self.filtered(lambda tx: tx.provider_code != const.PROVIDER_CODE)
        super(PaymentTransaction, other_provider_txs)._log_received_message()

    def _get_sent_message(self):
        """Return the message logged when the customer chooses this payment method."""
        message = super()._get_sent_message()
        if self.provider_code == const.PROVIDER_CODE:
            message = _(
                'El cliente seleccionó %(provider_name)s. El pedido deberá pagarse al momento de la entrega.',
                provider_name=self.provider_id.name,
            )
        return message

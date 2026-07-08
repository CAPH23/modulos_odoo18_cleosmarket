# -*- coding: utf-8 -*-
from odoo import http
from odoo.exceptions import AccessError, MissingError
from odoo.http import request, content_disposition
from odoo.addons.portal.controllers.portal import CustomerPortal


class CleoInvoicePortal(CustomerPortal):

    @http.route(['/my/invoices/<int:invoice_id>/cleo-ticket'], type='http', auth='public', website=True)
    def portal_invoice_cleo_ticket(self, invoice_id, access_token=None, **kw):
        """Download the Cleo ticket from the portal.

        If the invoice comes from POS, render the POS ticket. Otherwise render an
        invoice-based 80mm ticket so the portal button always works for posted
        customer invoices the customer can access.
        """
        try:
            invoice_sudo = self._document_check_access('account.move', invoice_id, access_token)
        except (AccessError, MissingError):
            return request.redirect('/my')

        pos_order = invoice_sudo.sudo().pos_order_ids[:1]
        report_name = 'cleo_invoice_design.report_cleo_invoice_ticket'
        record = invoice_sudo
        filename_source = invoice_sudo.name or 'comprobante'

        if pos_order:
            report_name = 'cleo_invoice_design.report_cleo_pos_ticket'
            record = pos_order
            filename_source = pos_order.pos_reference or pos_order.name or filename_source

        pdf, _ = request.env['ir.actions.report'].sudo()._render_qweb_pdf(report_name, [record.id])
        filename = 'ticket_cleo_%s.pdf' % filename_source.replace('/', '_').replace(' ', '_')
        return request.make_response(
            pdf,
            headers=[
                ('Content-Type', 'application/pdf'),
                ('Content-Length', str(len(pdf))),
                ('Content-Disposition', content_disposition(filename)),
            ],
        )

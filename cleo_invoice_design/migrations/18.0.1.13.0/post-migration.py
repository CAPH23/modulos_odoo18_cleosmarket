# -*- coding: utf-8 -*-
from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    """Detach the standard Invoice PDF report from the invoice mail template.

    account.email_template_edi_invoice is defined with noupdate="1" by the
    account module, so a plain <record> update in this module's data files
    is silently ignored on module upgrade (it only takes effect on a fresh
    install). Writing through the ORM here bypasses that noupdate guard.

    Without this, customers whose invoice_template_pdf_report_id preference
    already points at the Cleo comprobante (action_report_cleo_invoice_letter)
    receive it twice: once as the selected template and once as this extra
    report, both rendering the same content since the Cleo module also
    overrides the standard account.report_invoice_document layout.
    """
    env = api.Environment(cr, SUPERUSER_ID, {})
    mail_template = env.ref('account.email_template_edi_invoice', raise_if_not_found=False)
    invoice_pdf_report = env.ref('account.account_invoices', raise_if_not_found=False)
    if mail_template and invoice_pdf_report and invoice_pdf_report in mail_template.report_template_ids:
        mail_template.report_template_ids = [(3, invoice_pdf_report.id)]

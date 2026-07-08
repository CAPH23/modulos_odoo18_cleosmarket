# -*- coding: utf-8 -*-

from odoo import fields, http
from odoo.http import request
from odoo.tools import html_escape

class CleosmarketWebsite(http.Controller):
    """Rutas públicas del sitio web de Super Tienda Cleo."""

    @http.route(["/sobre-nosotros", "/sobre-nosotros/"], type="http", auth="public", website=True, sitemap=True)
    def cleosmarket_about_us(self, **kwargs):
        return request.render("Sitio_web_cleosmarket.cleosmarket_about_page_v8", {})

    @http.route(["/contactus", "/contactus/"], type="http", auth="public", website=True, sitemap=True)
    def cleosmarket_contact_us(self, **kwargs):
        return request.render(
            "Sitio_web_cleosmarket.cleosmarket_contact_page_v9",
            {"contact_success": kwargs.get("sent") == "1"},
        )



    @http.route(["/terminos-y-condiciones", "/terminos-y-condiciones/"], type="http", auth="public", website=True, sitemap=True)
    def cleosmarket_terms_conditions(self, **kwargs):
        return request.render("Sitio_web_cleosmarket.cleosmarket_terms_conditions_page", {})

    @http.route(["/politica-de-privacidad-ecommerce", "/politica-de-privacidad-ecommerce/"], type="http", auth="public", website=True, sitemap=True)
    def cleosmarket_privacy_ecommerce(self, **kwargs):
        return request.render("Sitio_web_cleosmarket.cleosmarket_privacy_ecommerce_page", {})

    @http.route(["/cancelaciones-cambios-devoluciones", "/cancelaciones-cambios-devoluciones/"], type="http", auth="public", website=True, sitemap=True)
    def cleosmarket_returns_policy(self, **kwargs):
        return request.render("Sitio_web_cleosmarket.cleosmarket_returns_refunds_page", {})

    @http.route(
        ["/contactus/submit"],
        type="http",
        auth="public",
        website=True,
        methods=["POST"],
        csrf=True,
    )
    def cleosmarket_contact_submit(self, **post):
        """Crea un lead CRM y envía una notificación por correo."""
        name = (post.get("name") or "").strip()
        phone = (post.get("phone") or "").strip()
        email_from = (post.get("email") or "").strip()
        company = (post.get("company") or "").strip()
        subject = (post.get("subject") or "Consulta desde el sitio web").strip()
        message = (post.get("message") or "").strip()

        if not name or not email_from or not message:
            return request.redirect("/contactus?error=missing")

        description = """
            <p><strong>Mensaje recibido desde la página /contactus de Super Tienda Cleo.</strong></p>
            <ul>
                <li><strong>Nombre:</strong> %s</li>
                <li><strong>Teléfono:</strong> %s</li>
                <li><strong>Correo:</strong> %s</li>
                <li><strong>Empresa:</strong> %s</li>
                <li><strong>Asunto:</strong> %s</li>
            </ul>
            <p><strong>Mensaje:</strong></p>
            <p>%s</p>
        """ % (
            html_escape(name),
            html_escape(phone or "No indicado"),
            html_escape(email_from),
            html_escape(company or "No indicada"),
            html_escape(subject),
            html_escape(message).replace("\n", "<br/>")
        )

        lead = request.env["crm.lead"].sudo().create({
            "name": "Contacto web: %s" % subject,
            "contact_name": name,
            "email_from": email_from,
            "phone": phone,
            "partner_name": company,
            "description": description,
            "type": "lead",
        })

        company_email = request.website.company_id.email or "supertiendacleo25@gmail.com"
        request.env["mail.mail"].sudo().create({
            "subject": "Nuevo mensaje web - %s" % subject,
            "email_to": "supertiendacleo25@gmail.com",
            "email_from": company_email,
            "reply_to": email_from,
            "body_html": """
                <h2>Nuevo mensaje recibido desde cleosmarket.com</h2>
                %s
                <p><strong>Lead CRM:</strong> %s</p>
            """ % (description, html_escape(lead.display_name)),
        }).send()

        return request.redirect("/contactus?sent=1")

class CleoTermsAcceptanceController(http.Controller):

    @http.route(
        "/cleo/terms/accept",
        type="json",
        auth="public",
        website=True,
        csrf=False,
    )
    def cleo_terms_accept(self, accepted=False, **kwargs):
        order = request.website.sale_get_order()

        if not order:
            return {"ok": False, "error": "No hay pedido activo."}

        if not accepted:
            return {"ok": False, "error": "Términos no aceptados."}

        forwarded_for = request.httprequest.headers.get("X-Forwarded-For")
        ip_address = forwarded_for.split(",")[0].strip() if forwarded_for else request.httprequest.remote_addr

        user_agent = request.httprequest.headers.get("User-Agent", "")

        order.sudo().write({
            "cleo_terms_accepted": True,
            "cleo_terms_accepted_datetime": fields.Datetime.now(),
            "cleo_terms_accepted_ip": ip_address,
            "cleo_terms_accepted_user_agent": user_agent,
            "cleo_terms_accepted_url": "/terminos-y-condiciones",
            "cleo_terms_accepted_version": "2026-06",
        })

        return {"ok": True}

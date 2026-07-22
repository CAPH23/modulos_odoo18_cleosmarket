# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase, tagged

from ..models.goboxful_client import GoBoxfulClient


@tagged("post_install", "-at_install")
class TestGoBoxfulHelpers(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env["ir.config_parameter"].sudo().set_param("product.weight_in_lbs", "1")
        cls.env["ir.config_parameter"].sudo().set_param("product.volume_in_cubic_feet", "0")
        # Compañía dedicada para no chocar con unique(company_id) si la
        # compañía por defecto ya tiene una cuenta Boxful real configurada.
        company = cls.env["res.company"].create({"name": "Boxful Test Company"})
        cls.env.user.sudo().write({"company_ids": [(4, company.id)]})
        cls.account = cls.env["goboxful.account"].create({
            "company_id": company.id,
            "mode": "mock",
            "responsible_user_id": cls.env.user.id,
        })
        product = cls.env["product.product"].create({
            "name": "Envío Boxful Test",
            "type": "service",
            "company_id": company.id,
        })
        cls.carrier = cls.env["delivery.carrier"].create({
            "name": "Boxful Test",
            "delivery_type": "goboxful",
            "company_id": company.id,
            "product_id": product.id,
            "goboxful_account_id": cls.account.id,
        })

    def test_weight_stays_in_lbs_when_api_expects_lbs(self):
        self.assertAlmostEqual(
            self.carrier._goboxful_weight_for_api(1.0, self.account), 1.0, places=7
        )

    def test_weight_converts_lbs_to_kg(self):
        self.account.api_weight_unit = "kg"
        self.assertAlmostEqual(
            self.carrier._goboxful_weight_for_api(1.0, self.account),
            0.45359237,
            places=7,
        )

    def test_integration_level_is_manual(self):
        self.assertEqual(self.carrier.integration_level, "rate")

    def test_sensitive_log_sanitizer(self):
        clean = GoBoxfulClient._sanitize({
            "email": "test@example.com",
            "password": "secret",
            "accessToken": "token",
        })
        self.assertEqual(clean["password"], "***")
        self.assertEqual(clean["accessToken"], "***")

    def test_category_block_inherits_to_child(self):
        parent = self.env["product.category"].create({
            "name": "PRODUCTOS CONGELADOS TEST",
            "goboxful_block_shipping": True,
        })
        child = self.env["product.category"].create({"name": "Helados", "parent_id": parent.id})
        self.assertTrue(child.goboxful_effectively_blocked)

    def test_mock_client_never_needs_credentials(self):
        me = self.account._goboxful_get_client().get_me()
        self.assertEqual(me["jwtPayload"]["clientId"], "mock-cleosmarket")

    def test_mock_label_is_a_pdf(self):
        content, mimetype = self.account._goboxful_get_client().download_label(
            "mock://label/MOCK-TEST"
        )
        self.assertTrue(content.startswith(b"%PDF-"))
        self.assertEqual(mimetype, "application/pdf")

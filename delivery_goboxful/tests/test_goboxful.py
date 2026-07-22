# -*- coding: utf-8 -*-
from datetime import datetime

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
        # Sin compañía asignada para poder usarlo en pedidos de "Boxful Test Company"
        # sin chocar con la validación _check_company de sale.order.
        cls.customer = cls.env["res.partner"].create({"name": "Boxful Test Customer"})

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

    def test_classify_courier_autoregisters_as_same_day(self):
        delivery_type = self.carrier._goboxful_classify_courier("c1", "Correo Rápido")
        self.assertEqual(delivery_type, "same_day")
        courier = self.env["goboxful.courier"].search([
            ("carrier_id", "=", self.carrier.id), ("external_id", "=", "c1"),
        ])
        self.assertEqual(len(courier), 1)
        self.assertEqual(courier.delivery_type, "same_day")

    def test_classify_courier_infers_scheduled_from_api_hint(self):
        delivery_type = self.carrier._goboxful_classify_courier(
            "c2", "Correo Estándar", api_delivery_type="next-day",
        )
        self.assertEqual(delivery_type, "scheduled")

    def test_classify_courier_respects_manual_reclassification(self):
        self.carrier._goboxful_classify_courier("c3", "Correo Lento")
        courier = self.env["goboxful.courier"].search([
            ("carrier_id", "=", self.carrier.id), ("external_id", "=", "c3"),
        ])
        courier.delivery_type = "scheduled"
        self.assertEqual(
            self.carrier._goboxful_classify_courier("c3", "Correo Lento"), "scheduled",
        )

    def test_pick_selected_option_falls_back_to_first(self):
        options = [
            {"courier_external_id": "a", "base_price": 1.0, "cod_commission": 0.0},
            {"courier_external_id": "b", "base_price": 2.0, "cod_commission": 0.0},
        ]
        order = self.env["sale.order"].new({})
        order.goboxful_selected_courier_id = "unknown-id"
        self.assertEqual(
            self.carrier._goboxful_pick_selected_option(options, order)["courier_external_id"],
            "a",
        )
        order.goboxful_selected_courier_id = "b"
        self.assertEqual(
            self.carrier._goboxful_pick_selected_option(options, order)["courier_external_id"],
            "b",
        )

    def test_build_display_options_labels_and_selection(self):
        options = [
            {
                "courier_external_id": "a", "courier_name": "Boxful Flash",
                "courier_logo": "", "delivery_type": "same_day",
                "max_weight": 5.0, "estimated_delivery": "", "base_price": 3.0,
                "cod_commission": 0.0,
            },
            {
                "courier_external_id": "b", "courier_name": "Boxful Estándar",
                "courier_logo": "", "delivery_type": "scheduled",
                "max_weight": 20.0, "estimated_delivery": "", "base_price": 2.0,
                "cod_commission": 0.0,
            },
        ]
        order = self.env["sale.order"].create({
            "partner_id": self.customer.id,
            "company_id": self.carrier.company_id.id,
        })
        display = self.carrier._goboxful_build_display_options(
            options, self.account, False, "b", order,
        )
        by_id = {opt["courier_external_id"]: opt for opt in display}
        self.assertEqual(by_id["a"]["delivery_type_label"], "Mismo día")
        self.assertEqual(by_id["b"]["delivery_type_label"], "Entrega programada")
        self.assertFalse(by_id["a"]["selected"])
        self.assertTrue(by_id["b"]["selected"])
        self.assertIn("3", by_id["a"]["price_label"])
        self.assertIn("2", by_id["b"]["price_label"])

    def test_effective_delivery_type_downgrades_when_dates_differ(self):
        # 20:00 UTC == 14:00 en America/El_Salvador (UTC-6): mismo 23 de julio.
        pickup_dt = datetime(2026, 7, 23, 20, 0, 0)
        self.assertEqual(
            self.carrier._goboxful_effective_delivery_type(
                "same_day", pickup_dt, "2026-07-24 09:00", self.account,
            ),
            "scheduled",
        )

    def test_effective_delivery_type_keeps_same_day_when_dates_match(self):
        pickup_dt = datetime(2026, 7, 23, 20, 0, 0)
        self.assertEqual(
            self.carrier._goboxful_effective_delivery_type(
                "same_day", pickup_dt, "2026-07-23 15:00", self.account,
            ),
            "same_day",
        )

    def test_effective_delivery_type_passes_through_scheduled(self):
        self.assertEqual(
            self.carrier._goboxful_effective_delivery_type(
                "scheduled", False, "", self.account,
            ),
            "scheduled",
        )

    def test_quote_hash_changes_when_same_day_only_toggled(self):
        # Sin esto, alternar "Solo couriers del mismo día" no invalida una
        # cotización ya cacheada (bug reportado: el checkout seguía mostrando
        # todos los couriers tras activar el filtro).
        order = self.env["sale.order"].create({
            "partner_id": self.customer.id,
            "company_id": self.carrier.company_id.id,
        })
        package = {"weight": 1.0}
        payload = {"cod": False, "codAmount": None}
        hash_before = self.carrier._goboxful_build_quote_hash(order, package, payload)
        self.carrier.goboxful_same_day_only = not self.carrier.goboxful_same_day_only
        hash_after = self.carrier._goboxful_build_quote_hash(order, package, payload)
        self.assertNotEqual(hash_before, hash_after)

    def test_quote_hash_changes_when_courier_reclassified(self):
        order = self.env["sale.order"].create({
            "partner_id": self.customer.id,
            "company_id": self.carrier.company_id.id,
        })
        package = {"weight": 1.0}
        payload = {"cod": False, "codAmount": None}
        self.carrier._goboxful_classify_courier("hash-test-courier", "Hash Test")
        hash_before = self.carrier._goboxful_build_quote_hash(order, package, payload)
        courier = self.env["goboxful.courier"].search([
            ("carrier_id", "=", self.carrier.id), ("external_id", "=", "hash-test-courier"),
        ])
        courier.delivery_type = "scheduled"
        hash_after = self.carrier._goboxful_build_quote_hash(order, package, payload)
        self.assertNotEqual(hash_before, hash_after)

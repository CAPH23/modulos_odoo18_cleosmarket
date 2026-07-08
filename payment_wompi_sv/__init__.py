# -*- coding: utf-8 -*-
from . import controllers
from . import models

try:
    from odoo.addons.payment import setup_provider, reset_payment_provider
except Exception:  # pragma: no cover
    setup_provider = reset_payment_provider = None


def post_init_hook(env):
    """Activate defaults for the Wompi provider after installation."""
    if setup_provider:
        setup_provider(env, 'wompi_sv')
    env['payment.provider'].sudo()._wompi_sv_create_and_attach_payment_method()
    env['payment.provider'].sudo()._wompi_sv_apply_default_v2_settings()


def uninstall_hook(env):
    """Reset provider-specific configuration on uninstall."""
    if reset_payment_provider:
        reset_payment_provider(env, 'wompi_sv')

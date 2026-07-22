# Reglas para Claude Code

- Plataforma objetivo: Odoo 18 Community, commit `02145783a5c97f939e1bfcb428ee950f7dd7be03`.
- Python del servicio: `/opt/odoo18/odoo-venv/bin/python3`.
- Nunca modificar `/opt/odoo18/odoo` ni módulos estándar.
- No registrar ni versionar credenciales o tokens.
- No ejecutar `POST /shipment` real en pruebas automatizadas.
- Mantener configuración separada por `company_id`.
- Preservar la convivencia con `delivery_pedidosya`.
- Preservar el bloqueo completo de Boxful para categorías refrigeradas.
- Usar mocks para pruebas.
- Probar instalación y actualización primero en una base staging.

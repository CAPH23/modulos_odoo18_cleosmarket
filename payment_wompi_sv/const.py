# -*- coding: utf-8 -*-

PROVIDER_CODE = 'wompi_sv'
PROVIDER_NAME = 'Wompi El Salvador'

SUPPORTED_CURRENCIES = {'USD'}
# Método propio para no modificar ni reutilizar el método global 'card' de Odoo.
# El método global 'card' puede estar compartido por otros proveedores, por eso no se debe
# cambiar su imagen desde este módulo.
DEFAULT_PAYMENT_METHOD_CODES = {'wompi_sv_card'}

OAUTH_URL = 'https://id.wompi.sv/connect/token'
API_BASE_URL = 'https://api.wompi.sv'
API_PAYMENT_LINK_ENDPOINT = '/EnlacePago'
API_TRANSACTION_ENDPOINT = '/TransaccionCompra/%s'
API_APPLICATION_ENDPOINT = '/Aplicativo'

# Wompi webhook successful status documented as ResultadoTransaccion = ExitosaAprobada.
APPROVED_STATUS = 'ExitosaAprobada'

PENDING_STATUSES = {'Pendiente', 'EnProceso', 'Iniciada'}
CANCEL_STATUSES = {'Cancelada', 'Anulada', 'Rechazada'}

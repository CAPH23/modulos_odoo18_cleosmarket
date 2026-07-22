# Seguridad

- Las credenciales y tokens solo son visibles para administradores del sistema.
- Los tokens se almacenan por compañía.
- La renovación del refresh token usa bloqueo `FOR UPDATE`, necesario porque el token rota y Odoo trabaja con varios workers.
- Los logs eliminan contraseñas, tokens y secretos. Los cuerpos JSON permanecen
  desactivados por defecto para no almacenar direcciones ni datos de clientes.
- El webhook compara el secreto con `hmac.compare_digest`.
- Los eventos webhook se deduplican mediante SHA-256 del payload y cuenta.
- La descarga de etiquetas solo acepta HTTPS y hosts configurados.
- Los timeouts durante `POST /shipment` dejan la transferencia en `verification_pending`; no se reintenta automáticamente.
- No existe cancelación automática porque no está documentado un endpoint público de cancelación.
- El modo pruebas bloquea la creación real de guías hasta que un administrador active la autorización explícita.
- No incluya credenciales en Git, capturas, archivos ZIP ni mensajes de soporte.

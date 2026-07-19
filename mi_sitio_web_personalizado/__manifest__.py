{ 
    "name": "Mi Sitio Web Personalizado",
    "version": "1.1",
    "category": "Website",
    "summary": "Personalizaciones de pie de página y redes sociales del sitio web",
    "author": "Carlos Palacios",
    "depends": ["website", "portal", "mail"],
    "data": [
        "views/layout_inherit.xml",
        "views/login_layout_inherit.xml",
        "views/portal_sidebar_inherit.xml",
        "views/mail_notification_layout_inherit.xml",
    ],
    "installable": True,
    "application": False
}
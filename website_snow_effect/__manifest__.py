{
    "name": "Website Snow Effect",
    "version": "1.0",
    "summary": "Agrega un efecto de nieve al sitio web",
    "category": "Website",
    "author": "Tu Nombre",
    "depends": ["website"],
    "data": [
        "views/layout_inherit.xml",
	"views/homepage_inherit.xml",
    ],
    "assets": {
        "web.assets_frontend": [
            "/website_snow_effect/static/lib/snow.js",
        ],
    },
    "installable": True,
    "application": False,
}

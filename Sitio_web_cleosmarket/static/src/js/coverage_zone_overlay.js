/** @odoo-module **/

(function () {
    "use strict";

    const GEOJSON_URL = "/Sitio_web_cleosmarket/static/src/data/coverage_zone.geojson";

    let cachedGeojsonPromise = null;

    function fetchCoverageZoneGeojson() {
        if (!cachedGeojsonPromise) {
            cachedGeojsonPromise = fetch(GEOJSON_URL, {
                cache: "force-cache",
            }).then(function (response) {
                if (!response.ok) {
                    throw new Error("No se pudo cargar la zona de cobertura.");
                }
                return response.json();
            });
        }
        return cachedGeojsonPromise;
    }

    function addCoverageZoneLayer(map) {
        fetchCoverageZoneGeojson()
            .then(function (geojson) {
                L.geoJSON(geojson, {
                    interactive: false,
                    style: {
                        color: "#06275d",
                        weight: 2,
                        opacity: 0.6,
                        fillColor: "#2f7fd6",
                        fillOpacity: 0.12,
                    },
                }).addTo(map);
            })
            .catch(function (error) {
                console.warn("No se pudo mostrar la zona de cobertura en el mapa:", error);
            });
    }

    function registerCoverageZoneHook() {
        if (typeof window.L === "undefined" || !window.L.Map || window.L.Map.__cleoCoverageZoneHooked) {
            return;
        }
        window.L.Map.__cleoCoverageZoneHooked = true;

        window.L.Map.addInitHook(function () {
            addCoverageZoneLayer(this);
        });
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", registerCoverageZoneHook);
    } else {
        registerCoverageZoneHook();
    }
})();

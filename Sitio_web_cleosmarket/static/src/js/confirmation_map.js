/** @odoo-module **/

(function () {
    "use strict";

    function toFloat(value) {
        const number = Number.parseFloat(String(value || "").trim().replace(",", "."));
        return Number.isFinite(number) ? number : null;
    }

    function isConfirmationPage() {
        return window.location.pathname.includes("/shop/confirmation");
    }

    function isContactusPage() {
        return window.location.pathname === "/contactus" || window.location.pathname.includes("/contactus");
    }

    function setupLeafletDefaultMarker(L) {
        if (L.Icon && L.Icon.Default) {
            delete L.Icon.Default.prototype._getIconUrl;
            L.Icon.Default.mergeOptions({
                iconRetinaUrl: "/Sitio_web_cleosmarket/static/lib/leaflet/images/marker-icon-2x.png",
                iconUrl: "/Sitio_web_cleosmarket/static/lib/leaflet/images/marker-icon.png",
                shadowUrl: "/Sitio_web_cleosmarket/static/lib/leaflet/images/marker-shadow.png",
            });
        }
    }

    function removeOldConfirmationMaps() {
        const selectors = [
            ".s_map",
            "section.s_map",
            "iframe[src*='google.com/maps']",
            "iframe[src*='maps.google']",
            "iframe[src*='openstreetmap']",
        ];

        document.querySelectorAll(selectors.join(",")).forEach(function (element) {
            if (element.closest("#cleo_confirmation_location")) {
                return;
            }

            const removable =
                element.closest(".s_map") ||
                element.closest("section") ||
                element.closest(".container") ||
                element;

            if (removable && !removable.closest("#cleo_confirmation_location")) {
                removable.remove();
            }
        });
    }

    function createConfirmationMapSection(locationData) {
        if (document.getElementById("cleo_confirmation_location")) {
            return;
        }

        const footer = document.querySelector("footer");
        const main = document.querySelector("main") || document.getElementById("wrapwrap") || document.body;

        const section = document.createElement("section");
        section.id = "cleo_confirmation_location";
        section.className = "cleo-confirmation-location";
        section.dataset.lat = locationData.latitude;
        section.dataset.lng = locationData.longitude;
        section.dataset.label = locationData.label || "Super Tienda Cleo AQUÍ";

        section.innerHTML = `
            <div class="cleo-confirmation-location-inner">
                <div class="cleo-confirmation-location-header">
                    <h3>Ubicación de Super Tienda Cleo</h3>
                    <p>Gracias por tu compra. Aquí puedes ver nuestra ubicación principal.</p>
                </div>

                <div class="cleo-confirmation-map-card">
                    <div id="cleo_confirmation_map" class="cleo-confirmation-map"></div>
                </div>
            </div>
        `;

        if (footer && footer.parentNode) {
            footer.parentNode.insertBefore(section, footer);
        } else {
            main.appendChild(section);
        }
    }

    function findCurrentContactusMapElement() {
        const wrap = document.getElementById("wrap") || document.body;

        const candidates = wrap.querySelectorAll([
            "iframe[src*='google.com/maps']",
            "iframe[src*='maps.google']",
            "iframe[src*='openstreetmap']",
            ".s_map iframe",
            "section.s_map iframe",
        ].join(","));

        for (const candidate of candidates) {
            if (candidate.closest("footer")) {
                continue;
            }
            if (candidate.closest("#cleo_confirmation_location")) {
                continue;
            }
            if (candidate.closest("#cleo_contactus_location")) {
                continue;
            }
            return candidate;
        }

        return null;
    }

    function replaceContactusMap(locationData) {
        if (document.getElementById("cleo_contactus_map")) {
            return;
        }

        const oldMap = findCurrentContactusMapElement();

        if (!oldMap) {
            console.warn("No se encontró el mapa actual de /contactus para reemplazarlo.");
            return;
        }

        const rect = oldMap.getBoundingClientRect();
        const oldHeight =
            rect && rect.height && rect.height > 80
                ? Math.round(rect.height)
                : 250;

        const mapWrapper = document.createElement("div");
        mapWrapper.id = "cleo_contactus_location";
        mapWrapper.className = "cleo-contactus-location";
        mapWrapper.dataset.lat = locationData.latitude;
        mapWrapper.dataset.lng = locationData.longitude;
        mapWrapper.dataset.label = locationData.label || "Super Tienda Cleo AQUÍ";
        mapWrapper.dataset.subtitle = "Centro de nuestra área de cobertura de entrega";
        mapWrapper.dataset.logoUrl = locationData.logo_url || "";

        mapWrapper.innerHTML = `
            <div id="cleo_contactus_map" class="cleo-contactus-map"></div>
        `;

        const newMap = mapWrapper.querySelector("#cleo_contactus_map");
        newMap.style.minHeight = oldHeight + "px";

        oldMap.replaceWith(mapWrapper);
    }

    function initLeafletMap(mapElementId, sectionId) {
        const section = document.getElementById(sectionId);
        const mapElement = document.getElementById(mapElementId);

        if (!section || !mapElement || mapElement.dataset.cleoMapReady === "1") {
            return;
        }

        if (typeof window.L === "undefined") {
            console.warn("Leaflet no está cargado.");
            return;
        }

        const lat = toFloat(section.dataset.lat);
        const lng = toFloat(section.dataset.lng);

        if (!Number.isFinite(lat) || !Number.isFinite(lng)) {
            console.warn("Coordenadas inválidas para Super Tienda Cleo.");
            return;
        }

        mapElement.dataset.cleoMapReady = "1";

        const L = window.L;
        const label = section.dataset.label || "Super Tienda Cleo AQUÍ";
        const subtitle = section.dataset.subtitle || "";
        const logoUrl = section.dataset.logoUrl || "";

        const map = L.map(mapElement, {
            scrollWheelZoom: false,
        }).setView([lat, lng], 17);

        L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
            maxZoom: 19,
            attribution: "&copy; OpenStreetMap",
        }).addTo(map);

        if (subtitle && logoUrl) {
            const logoIcon = L.divIcon({
                className: "cleo-confirmation-logo-marker-wrapper",
                html:
                    '<div class="cleo-confirmation-logo-marker">' +
                    '<div class="cleo-confirmation-logo-pin"><img src="' + logoUrl + '" alt="' + label + '" /></div>' +
                    '<div class="cleo-confirmation-logo-label"><strong>' + label + '</strong><small>' + subtitle + '</small></div>' +
                    '</div>',
                iconSize: [0, 0],
                iconAnchor: [29, 50],
            });
            L.marker([lat, lng], { icon: logoIcon }).addTo(map);
        } else {
            setupLeafletDefaultMarker(L);

            const marker = L.marker([lat, lng]).addTo(map);

            marker.bindTooltip(label, {
                permanent: true,
                direction: "right",
                offset: [18, -12],
                className: "cleo-confirmation-store-tooltip",
            });
        }

        setTimeout(function () {
            map.invalidateSize();
        }, 300);

        setTimeout(function () {
            map.invalidateSize();
        }, 900);
    }

    async function getStoreLocation() {
        const response = await fetch("/cleo/store/location", {
            method: "GET",
            credentials: "same-origin",
            cache: "no-store",
        });

        if (!response.ok) {
            throw new Error("No se pudo obtener la ubicación de la tienda.");
        }

        return await response.json();
    }

    async function initCleoMaps() {
        if (!isConfirmationPage() && !isContactusPage()) {
            return;
        }

        try {
            const locationData = await getStoreLocation();

            if (isConfirmationPage()) {
                removeOldConfirmationMaps();
                createConfirmationMapSection(locationData);
                initLeafletMap("cleo_confirmation_map", "cleo_confirmation_location");
            }

            if (isContactusPage()) {
                replaceContactusMap(locationData);
                initLeafletMap("cleo_contactus_map", "cleo_contactus_location");
            }
        } catch (error) {
            console.warn("Error cargando mapa de Super Tienda Cleo:", error);
        }
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", initCleoMaps);
    } else {
        initCleoMaps();
    }
})();

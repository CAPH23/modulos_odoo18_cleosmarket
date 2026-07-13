/** @odoo-module **/

(function () {
    "use strict";

    function toFloat(value) {
        if (value === undefined || value === null) {
            return null;
        }

        const cleanValue = String(value).trim().replace(",", ".");
        if (!cleanValue) {
            return null;
        }

        const number = Number.parseFloat(cleanValue);
        return Number.isFinite(number) ? number : null;
    }

    function isValidLatitude(value) {
        return Number.isFinite(value) && value >= -90 && value <= 90;
    }

    function isValidLongitude(value) {
        return Number.isFinite(value) && value >= -180 && value <= 180;
    }

    function formatCoordinate(value) {
        return Number(value).toFixed(7);
    }

    function initCleoAddressMap() {
        const mapElement = document.getElementById("cleo_address_map");
        const latitudeInput = document.getElementById("o_partner_latitude");
        const longitudeInput = document.getElementById("o_partner_longitude");

        if (!mapElement || !latitudeInput || !longitudeInput) {
            return;
        }

        if (mapElement.dataset.cleoMapReady === "1") {
            return;
        }

        if (typeof window.L === "undefined") {
            console.warn("Leaflet no está cargado. Revise los assets del módulo Sitio_web_cleosmarket.");
            return;
        }

        mapElement.dataset.cleoMapReady = "1";

        const L = window.L;

        if (L.Icon && L.Icon.Default) {
            delete L.Icon.Default.prototype._getIconUrl;
            L.Icon.Default.mergeOptions({
                iconRetinaUrl: "/Sitio_web_cleosmarket/static/lib/leaflet/images/marker-icon-2x.png",
                iconUrl: "/Sitio_web_cleosmarket/static/lib/leaflet/images/marker-icon.png",
                shadowUrl: "/Sitio_web_cleosmarket/static/lib/leaflet/images/marker-shadow.png",
            });
        }

        const defaultLat = toFloat(mapElement.dataset.defaultLat) || 13.69294;
        const defaultLng = toFloat(mapElement.dataset.defaultLng) || -89.21819;

        const currentLat = toFloat(latitudeInput.value);
        const currentLng = toFloat(longitudeInput.value);

        const hasSavedCoordinates = isValidLatitude(currentLat) && isValidLongitude(currentLng);

        const startLat = hasSavedCoordinates ? currentLat : defaultLat;
        const startLng = hasSavedCoordinates ? currentLng : defaultLng;
        const startZoom = hasSavedCoordinates ? 17 : 12;

        const map = L.map(mapElement).setView([startLat, startLng], startZoom);

        L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
            maxZoom: 19,
            attribution: "&copy; OpenStreetMap",
        }).addTo(map);

        let marker = null;

        function writeInputs(latlng) {
            latitudeInput.value = formatCoordinate(latlng.lat);
            longitudeInput.value = formatCoordinate(latlng.lng);

            latitudeInput.dispatchEvent(new Event("input", { bubbles: true }));
            longitudeInput.dispatchEvent(new Event("input", { bubbles: true }));
            latitudeInput.dispatchEvent(new Event("change", { bubbles: true }));
            longitudeInput.dispatchEvent(new Event("change", { bubbles: true }));
        }

        function placeMarker(latlng, writeToInputs) {
            if (!marker) {
                marker = L.marker(latlng, {
                    draggable: true,
                }).addTo(map);

                marker.on("dragend", function () {
                    writeInputs(marker.getLatLng());
                });
            } else {
                marker.setLatLng(latlng);
            }

            if (writeToInputs) {
                writeInputs(latlng);
            }
        }

        if (hasSavedCoordinates) {
            placeMarker({ lat: currentLat, lng: currentLng }, false);
        }

        map.on("click", function (event) {
            placeMarker(event.latlng, true);
        });

        const copyButton = document.getElementById("cleo_geo_copy_marker");
        if (copyButton) {
            copyButton.addEventListener("click", function () {
                if (!marker) {
                    alert("Primero seleccione un punto en el mapa.");
                    return;
                }
                writeInputs(marker.getLatLng());
            });
        }

        function geolocationErrorMessage(error) {
            switch (error.code) {
                case error.PERMISSION_DENIED:
                    return "Ubicación bloqueada para este sitio. Haga clic en el candado junto a la dirección del navegador, permita la Ubicación y vuelva a intentar, o seleccione el punto manualmente en el mapa.";
                case error.POSITION_UNAVAILABLE:
                    return "No se pudo determinar su ubicación. Verifique que el servicio de ubicación de su dispositivo/sistema operativo esté activado, o seleccione el punto manualmente en el mapa.";
                case error.TIMEOUT:
                    return "La solicitud de ubicación tardó demasiado. Puede intentarlo de nuevo o seleccionar el punto manualmente en el mapa.";
                default:
                    return "No se pudo obtener su ubicación. Puede seleccionar el punto manualmente en el mapa.";
            }
        }

        function onLocationSuccess(position) {
            const latlng = {
                lat: position.coords.latitude,
                lng: position.coords.longitude,
            };

            map.setView(latlng, 18);
            placeMarker(latlng, true);
        }

        const myLocationButton = document.getElementById("cleo_geo_use_my_location");
        if (myLocationButton) {
            myLocationButton.addEventListener("click", function () {
                if (!navigator.geolocation) {
                    alert("Su navegador no permite obtener ubicación.");
                    return;
                }

                navigator.geolocation.getCurrentPosition(
                    onLocationSuccess,
                    function (error) {
                        console.error("Geolocation error (high accuracy)", error.code, error.message);

                        // PERMISSION_DENIED no mejora reintentando con menor precisión.
                        if (error.code === error.PERMISSION_DENIED) {
                            alert(geolocationErrorMessage(error));
                            return;
                        }

                        // Reintento con menor precisión (red/WiFi) para TIMEOUT o POSITION_UNAVAILABLE.
                        navigator.geolocation.getCurrentPosition(
                            onLocationSuccess,
                            function (retryError) {
                                console.error("Geolocation error (low accuracy retry)", retryError.code, retryError.message);
                                alert(geolocationErrorMessage(retryError));
                            },
                            {
                                enableHighAccuracy: false,
                                timeout: 20000,
                                maximumAge: 0,
                            }
                        );
                    },
                    {
                        enableHighAccuracy: true,
                        timeout: 10000,
                        maximumAge: 0,
                    }
                );
            });
        }

        const clearButton = document.getElementById("cleo_geo_clear");
        if (clearButton) {
            clearButton.addEventListener("click", function () {
                latitudeInput.value = "";
                longitudeInput.value = "";

                if (marker) {
                    marker.remove();
                    marker = null;
                }
            });
        }

        setTimeout(function () {
            map.invalidateSize();
        }, 300);

        setTimeout(function () {
            map.invalidateSize();
        }, 900);
    }

    function initCleoDistrictSelect() {
        const citySelect = document.getElementById("o_city");
        const stateSelect = document.getElementById("o_state_id");

        if (!citySelect || !stateSelect) {
            return;
        }

        if (citySelect.dataset.cleoDistrictReady === "1") {
            return;
        }
        citySelect.dataset.cleoDistrictReady = "1";

        let catalog = [];
        try {
            catalog = JSON.parse(citySelect.dataset.catalog || "[]");
        } catch (error) {
            console.warn("No se pudo leer el catálogo de distritos.", error);
            return;
        }

        function populateCities(stateId, preferredValue) {
            const stateIdNum = stateId ? Number(stateId) : null;
            const matches = stateIdNum
                ? catalog.filter((city) => city.state_id === stateIdNum)
                : [];

            citySelect.innerHTML = "";

            const placeholder = document.createElement("option");
            placeholder.value = "";
            placeholder.textContent = stateIdNum
                ? "Seleccione un distrito..."
                : "Seleccione primero un municipio";
            citySelect.appendChild(placeholder);

            let matchedPreferred = false;

            matches
                .slice()
                .sort((a, b) => a.name.localeCompare(b.name, "es"))
                .forEach((city) => {
                    const option = document.createElement("option");
                    option.value = city.name;
                    option.textContent = city.name;
                    if (preferredValue && city.name === preferredValue) {
                        option.selected = true;
                        matchedPreferred = true;
                    }
                    citySelect.appendChild(option);
                });

            // Conserva un distrito guardado que ya no está en el catálogo del
            // municipio actual, para no dejar la dirección existente "sin seleccionar".
            if (preferredValue && !matchedPreferred) {
                const customOption = document.createElement("option");
                customOption.value = preferredValue;
                customOption.textContent = preferredValue;
                customOption.selected = true;
                citySelect.appendChild(customOption);
            }
        }

        populateCities(stateSelect.value, citySelect.dataset.initialCity);

        stateSelect.addEventListener("change", function () {
            populateCities(stateSelect.value, null);
        });
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", function () {
            initCleoAddressMap();
            initCleoDistrictSelect();
        });
    } else {
        initCleoAddressMap();
        initCleoDistrictSelect();
    }
})();

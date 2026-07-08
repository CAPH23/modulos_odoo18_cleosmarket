odoo.define('website_google_map_custom.custom_cluster_style', function (require) {
    "use strict";

    window.initializeMarkers = async function (odooPartnerData) {
        var map = window.google_map_instance;

        if (odooPartnerData) {
            const markers = [];
            const geocoder = new google.maps.Geocoder();
            const infoWindow = new google.maps.InfoWindow();

            for (let i = 0; i < odooPartnerData.counter; i++) {
                const p = odooPartnerData.partners[i];
                let position;

                if (!p.latitude || !p.longitude) {
                    const results = await new Promise((resolve, reject) => {
                        geocoder.geocode({ address: p.address }, (res, status) => {
                            status === 'OK' ? resolve(res) : reject();
                        });
                    });
                    position = results[0].geometry.location;
                } else {
                    position = new google.maps.LatLng(p.latitude, p.longitude);
                }

                const marker = new google.maps.Marker({
                    position: position,
                    partner: p,
                });

                marker.addListener('click', function () {
                    infoWindow.setContent(
                        `<b>${p.name}</b><br/>${p.address}`
                    );
                    infoWindow.open(map, marker);
                });

                markers.push(marker);
            }

            new MarkerClusterer(map, markers, {
                imagePath: '/website_google_map_custom/static/src/img/cluster',
                imageExtension: 'png',
                styles: [
                    {
                        url: '/website_google_map_custom/static/src/img/partners.png',
                        height: 48,
                        width: 48,
                        textColor: '#ffffff',
                        textSize: 14
                    }
                ]
            });
        }
    };
});

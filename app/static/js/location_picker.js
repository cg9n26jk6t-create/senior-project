// Interactive Lebanon map for picking a request's location (Leaflet +
// OpenStreetMap -- free, no API key). Clicking or dragging the pin fills
// the hidden latitude/longitude fields the server saves, and reverse-
// geocodes the pin through OSM's free Nominatim API to suggest an address
// (the customer can still edit that text by hand).
//
// If Leaflet fails to load (e.g. offline), the map box is simply left
// empty and the address field still works as a plain text input -- the
// map pin was never required server-side.

(function () {
  "use strict";

  const REVERSE_GEOCODE_URL = "https://nominatim.openstreetmap.org/reverse";

  document.addEventListener("DOMContentLoaded", function () {
    const mapEl = document.getElementById("location-map");
    if (!mapEl || typeof L === "undefined") return;

    const center = window.ROADRESCUE_MAP_CENTER || [33.8547, 35.8623];
    const zoom = window.ROADRESCUE_MAP_ZOOM || 9;

    const map = L.map(mapEl).setView(center, zoom);
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      attribution: "&copy; OpenStreetMap contributors",
      maxZoom: 18,
    }).addTo(map);

    const latInput = document.getElementById("location-lat");
    const lngInput = document.getElementById("location-lng");
    const addressInput = document.getElementById("location-address");

    let marker = null;

    function reverseGeocode(lat, lng) {
      const url = `${REVERSE_GEOCODE_URL}?format=jsonv2&lat=${lat}&lon=${lng}&accept-language=en`;
      fetch(url)
        .then((response) => (response.ok ? response.json() : null))
        .then((data) => {
          if (data && data.display_name) {
            addressInput.value = data.display_name;
          }
        })
        .catch(() => {
          // Reverse geocoding is a convenience, not a requirement -- if it
          // fails (offline, rate limited), the customer can just type the
          // address themselves.
        });
    }

    function setPin(lat, lng) {
      latInput.value = lat;
      lngInput.value = lng;
      if (marker) {
        marker.setLatLng([lat, lng]);
      } else {
        marker = L.marker([lat, lng], { draggable: true }).addTo(map);
        marker.on("dragend", function () {
          const pos = marker.getLatLng();
          setPin(pos.lat, pos.lng);
        });
      }
      reverseGeocode(lat, lng);
    }

    map.on("click", function (event) {
      setPin(event.latlng.lat, event.latlng.lng);
    });
  });
})();

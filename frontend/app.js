var API_BASE_URL = "http://127.0.0.1:8000"; 
var globalFires = []; 
var geoJsonLayer;

var STATE_VIEWS = {
    "Andhra Pradesh": { center: [15.9129, 79.7400], zoom: 6 },
    "Arunachal Pradesh": { center: [28.2180, 94.7278], zoom: 7 },
    "Assam": { center: [26.2006, 92.9376], zoom: 7 },
    "Bihar": { center: [25.0961, 85.3131], zoom: 7 },
    "Chhattisgarh": { center: [21.2787, 81.8661], zoom: 6 },
    "Goa": { center: [15.2993, 74.1240], zoom: 9 },
    "Gujarat": { center: [22.2587, 71.1924], zoom: 6 },
    "Haryana": { center: [29.0588, 76.0856], zoom: 7 },
    "Himachal Pradesh": { center: [31.1048, 77.1666], zoom: 7 },
    "Jharkhand": { center: [23.6102, 85.2799], zoom: 7 },
    "Karnataka": { center: [15.3173, 75.7139], zoom: 6 },
    "Kerala": { center: [10.8505, 76.2711], zoom: 7 },
    "Madhya Pradesh": { center: [22.9734, 78.6569], zoom: 6 },
    "Maharashtra": { center: [19.7515, 75.7139], zoom: 6 },
    "Manipur": { center: [24.6637, 93.9063], zoom: 8 },
    "Meghalaya": { center: [25.4670, 91.3662], zoom: 8 },
    "Mizoram": { center: [23.1645, 92.9376], zoom: 8 },
    "Nagaland": { center: [26.1584, 94.5624], zoom: 8 },
    "Odisha": { center: [20.9517, 85.0985], zoom: 6 },
    "Punjab": { center: [31.1471, 75.3412], zoom: 7 },
    "Rajasthan": { center: [27.0238, 74.2179], zoom: 6 },
    "Sikkim": { center: [27.5330, 88.5122], zoom: 9 },
    "Tamil Nadu": { center: [11.1271, 78.6569], zoom: 6 },
    "Telangana": { center: [18.1124, 79.0193], zoom: 6 },
    "Tripura": { center: [23.9408, 91.9882], zoom: 8 },
    "Uttar Pradesh": { center: [26.8467, 80.9462], zoom: 6 },
    "Uttarakhand": { center: [30.0668, 79.0193], zoom: 7 },
    "West Bengal": { center: [22.9868, 87.8550], zoom: 6 }
};

var mapContainer = L.DomUtil.get('map');
if (mapContainer != null) {
    mapContainer._leaflet_id = null;
}

var map = L.map('map', { zoomControl: false }).setView([22.0, 79.0], 5);
L.control.zoom({ position: 'bottomright' }).addTo(map);

var tiles = {
    standard: L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', { maxZoom: 18 }),
    satellite: L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', { maxZoom: 18 })
};
tiles.standard.addTo(map);

function initDashboard() {
    setTimeout(() => {
        map.invalidateSize();
        fetchFiresData();
        startClock();
        fetchArchiveList();
    }, 300);

    var menuBtn = document.getElementById("menu-btn");
    if (menuBtn) {
        menuBtn.addEventListener("click", () => {
            document.getElementById("menu-content").classList.toggle("hidden");
        });
    }

    document.getElementById("category-filter").addEventListener("change", applyFilters);
    document.getElementById("state-filter").addEventListener("change", applyFilters);
    document.getElementById("frp-filter").addEventListener("input", applyFilters);
    
    document.getElementById("close-drawer").addEventListener("click", () => {
        document.getElementById("side-drawer").classList.add("hidden");
    });

    document.getElementById("map-style").addEventListener("change", (e) => {
        var style = e.target.value;
        map.removeLayer(tiles.standard);
        map.removeLayer(tiles.satellite);
        var mapDiv = document.getElementById("map");

        if (style === "satellite") {
            tiles.satellite.addTo(map);
            mapDiv.classList.remove("high-contrast-map");
        } else if (style === "high-contrast") {
            tiles.standard.addTo(map);
            mapDiv.classList.add("high-contrast-map");
        } else {
            tiles.standard.addTo(map);
            mapDiv.classList.remove("high-contrast-map");
        }
    });

    document.getElementById("btn-check-new").addEventListener("click", () => {
        var oldIds = new Set(globalFires.map(f => f.properties.id));
        
        showNotification("Running pipeline... Please wait. This may take a few moments.");
        fetch(`${API_BASE_URL}/api/run-pipeline`, { method: "POST" })
            .then(res => res.json())
            .then(() => {
                fetch(`${API_BASE_URL}/api/fires/india`)
                    .then(res => res.json())
                    .then(data => {
                        if (!data.features) return;
                        globalFires = data.features;
                        
                        var newFiresCount = globalFires.filter(f => !oldIds.has(f.properties.id)).length;
                        
                        initializeStatistics(globalFires);
                        updateDashboard(globalFires);
                        populateActiveFiresMenu(globalFires);

                        if (newFiresCount > 0) {
                            showNotification(`${newFiresCount} new fires detected`);
                        } else {
                            showNotification("0 new fires detected");
                        }
                    });
            });
    });

    document.getElementById("btn-save-archive").addEventListener("click", () => {
        fetch(`${API_BASE_URL}/api/archive/save`, { method: "POST" })
            .then(res => res.json())
            .then(data => {
                showNotification(`saved to archive as "${data.run_name}"`);
                fetchArchiveList();
            });
    });
}

if (document.readyState === 'loading') {
    document.addEventListener("DOMContentLoaded", initDashboard);
} else {
    initDashboard(); 
}

window.toggleSubmenu = function(id) {
    var el = document.getElementById(id);
    if (el) el.classList.toggle("hidden");
};

window.flyToFire = function(lat, lon, id) {
    map.flyTo([lat, lon], 12, { duration: 1.5 });
    var fire = globalFires.find(f => f.properties.id === id);
    if (fire) window.openDrawer(fire.properties);
};

window.loadArchive = function(name) {
    var formData = new FormData();
    formData.append("run_name", name);
    
    fetch(`${API_BASE_URL}/api/archive/load`, {
        method: "POST",
        body: formData
    })
    .then(res => res.json())
    .then(() => {
        showNotification(`Loaded Archive: ${name}`);
        fetchFiresData();
    });
};

window.openDrawer = function(props) {
    document.getElementById("side-drawer").classList.remove("hidden");
    
    var displayType = "WILDFIRE";
    if (props.source_type) {
        if (props.source_type === "industrial_fire") {
            displayType = "INDUSTRIAL DISASTER";
        } else {
            displayType = props.source_type.replace('_', ' ').toUpperCase();
        }
    }
    
    var zoneBadge = props.is_industrial ? `<span class="tag-badge">Industrial Zone</span>` : props.is_mining ? `<span class="tag-badge">Mining Zone</span>` : "";
    var city = props.city && props.city !== "Unknown" ? props.city : "Unknown";
    var state = props.state && props.state !== "Unknown" ? props.state : "Unknown";

    document.getElementById("drawer-content").innerHTML = `
        <div class="data-row">
            <span class="data-label">Status</span>
            <div class="data-value" style="font-size: 18px; color: #cc0000; font-weight: bold;">${displayType}</div>
        </div>
        <div class="data-row">
            <span class="data-label">Confidence</span>
            <div class="data-value" style="font-weight: bold;">${props.confidence || "N/A"}</div>
        </div>
        <div class="data-row">
            <span class="data-label">Facility Information</span>
            <div class="data-value">${props.facility_name || "N/A"}</div>
            ${zoneBadge}
        </div>
        <div class="data-row">
            <span class="data-label">Location</span>
            <div class="data-value">${city}, ${state}</div>
        </div>
        <div class="data-row">
            <span class="data-label">Fire Radiative Power (FRP)</span>
            <div class="data-value">${props.frp_mw} k MW</div>
        </div>
        <div class="data-row">
            <span class="data-label">Detection Timeline</span>
            <div class="data-value">${props.detected_at}</div>
        </div>
        <div class="data-row">
            <span class="data-label">Coordinates & ID</span>
            <div class="data-value">ID: ${props.id} <br> ${parseFloat(props.latitude).toFixed(4)}, ${parseFloat(props.longitude).toFixed(4)}</div>
        </div>
    `;
};

function showNotification(message) {
    var toast = document.getElementById("notification-toast");
    toast.innerText = message;
    toast.classList.remove("hidden", "fade-out");

    setTimeout(() => {
        toast.classList.add("fade-out");
        setTimeout(() => toast.classList.add("hidden"), 500); 
    }, 45000); 
}

function fetchFiresData() {
    fetch(`${API_BASE_URL}/api/fires/india`)
        .then(res => res.json())
        .then(data => {
            if (!data.features) return;
            globalFires = data.features;
            
            initializeStatistics(globalFires);
            updateDashboard(globalFires);
            populateActiveFiresMenu(globalFires);

            if (geoJsonLayer && geoJsonLayer.getLayers().length > 0) {
                setTimeout(() => map.fitBounds(geoJsonLayer.getBounds(), { padding: [20, 20], maxZoom: 6 }), 200);
            }
        })
        .catch(err => console.error("Failed to fetch map data:", err));
}

function startClock() {
    function updateClock() {
        var now = new Date();
        document.getElementById("clock-time").innerText = now.toLocaleTimeString();
        document.getElementById("clock-date").innerText = now.toLocaleDateString();
    }
    setInterval(updateClock, 1000);
    updateClock();
}

function populateActiveFiresMenu(features) {
    var cats = {
        "industrial_fire": "Industrial Disasters",
        "gas_flare": "Gas Flares",
        "mining_activity": "Mining Activity",
        "agricultural_burning": "Agricultural Burns",
        "wildfire": "Wildfires"
    };

    var html = "";
    for (const [key, label] of Object.entries(cats)) {
        var matchingFires = features.filter(f => f.properties.source_type === key);
        html += `<div class="submenu-category" onclick="window.toggleSubmenu('${key}-submenu')">${label} (${matchingFires.length}) <span class="arrow">&#9660;</span></div>`;
        html += `<div id="${key}-submenu" class="hidden sub-submenu">`;
        matchingFires.forEach(f => {
            var city = f.properties.city || "Unknown";
            var state = f.properties.state || "Unknown";
            html += `<div class="fire-item" onclick="window.flyToFire(${f.geometry.coordinates[1]}, ${f.geometry.coordinates[0]}, ${f.properties.id})">Fire in ${city}, ${state} detected at ${f.properties.detected_at}</div>`;
        });
        html += `</div>`;
    }
    document.getElementById("active-fires-wrapper").innerHTML = html;
}

function fetchArchiveList() {
    fetch(`${API_BASE_URL}/api/archive/list`)
        .then(res => res.json())
        .then(data => {
            var html = "";
            data.archives.forEach(name => {
                html += `<div class="fire-item" onclick="window.loadArchive('${name}')">${name}</div>`;
            });
            document.getElementById("archive-store-wrapper").innerHTML = html;
        });
}

function initializeStatistics(features) {
    var controlled = 0, unintended = 0;
    
    features.forEach(f => {
        var type = f.properties.source_type;
        if (type === "gas_flare" || type === "mining_activity") {
            controlled++;
        } else if (type === "wildfire" || type === "agricultural_burning" || type === "industrial_fire") {
            unintended++;
        }
    });

    document.getElementById("stat-total").innerText = features.length;
    document.getElementById("stat-controlled").innerText = controlled;
    document.getElementById("stat-unintended").innerText = unintended;
    
    var maxFrp = features.length > 0 ? Math.max(...features.map(f => f.properties.frp_mw || 0)) : 0;
    document.getElementById("max-frp-label").innerText = `Max FRP: ${maxFrp.toFixed(1)} k MW`;
}

function applyFilters() {
    var category = document.getElementById("category-filter").value;
    var state = document.getElementById("state-filter").value;
    var minFrp = parseFloat(document.getElementById("frp-filter").value) || 0;

    var filtered = globalFires.filter(f => {
        var matchCat = category === "all" || f.properties.source_type === category;
        var matchState = state === "all" || f.properties.state === state;
        var matchFrp = (f.properties.frp_mw || 0) >= minFrp;
        return matchCat && matchState && matchFrp;
    });

    updateDashboard(filtered);

    if (state !== "all" && STATE_VIEWS[state]) {
        map.flyTo(STATE_VIEWS[state].center, STATE_VIEWS[state].zoom, { duration: 1.5 });
    } else if (state === "all") {
        map.flyTo([22.0, 79.0], 5, { duration: 1.5 });
    }
}

function updateDashboard(features) {
    map.invalidateSize();
    
    if (geoJsonLayer) map.removeLayer(geoJsonLayer);

    var validFeatures = [];
    features.forEach(f => {
        if (f.geometry && f.geometry.coordinates) {
            var lon = parseFloat(f.geometry.coordinates[0]);
            var lat = parseFloat(f.geometry.coordinates[1]);
            
            if (!isNaN(lon) && !isNaN(lat) && lat >= -90 && lat <= 90 && lon >= -180 && lon <= 180) {
                f.geometry.coordinates = [lon, lat];
                validFeatures.push(f);
            }
        }
    });

    var featureCollection = {
        "type": "FeatureCollection",
        "features": validFeatures
    };

    geoJsonLayer = L.geoJSON(featureCollection, {
        pointToLayer: (feature, latlng) => {
            var type = feature.properties.source_type;
            
            if (type === "wildfire" || type === "agricultural_burning" || type === "industrial_fire") {
                var pulseClass = "pulse-wildfire";
                if (type === "industrial_fire") pulseClass = "pulse-industrial";
                if (type === "agricultural_burning") pulseClass = "pulse-agricultural";

                return L.marker(latlng, {
                    icon: L.divIcon({
                        className: `custom-div-icon ${pulseClass}`,
                        iconSize: [14, 14],
                        iconAnchor: [7, 7]
                    })
                });
            } else {
                var color = type === "gas_flare" ? "#ffa500" : "#000000"; 
                return L.circleMarker(latlng, { radius: 7, fillColor: color, color: "#fff", weight: 1.5, opacity: 1, fillOpacity: 0.9 });
            }
        }
    });
    
    geoJsonLayer.on('click', (e) => {
        var props = e.layer.feature.properties;
        window.flyToFire(props.latitude, props.longitude, props.id);
    });
    
    geoJsonLayer.addTo(map);
}
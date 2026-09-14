const API_BASE_URL = "http://127.0.0.1:8000";
let globalFires = []; 
let geoJsonLayer;

const STATE_VIEWS = {
    "Andaman and Nicobar Islands": { center: [11.7401, 92.6586], zoom: 6 },
    "Andhra Pradesh": { center: [15.9129, 79.7400], zoom: 6 },
    "Arunachal Pradesh": { center: [28.2180, 94.7278], zoom: 7 },
    "Assam": { center: [26.2006, 92.9376], zoom: 7 },
    "Bihar": { center: [25.0961, 85.3131], zoom: 7 },
    "Chandigarh": { center: [30.7333, 76.7794], zoom: 11 },
    "Chhattisgarh": { center: [21.2787, 81.8661], zoom: 7 },
    "Dadra and Nagar Haveli and Daman and Diu": { center: [20.4283, 72.8397], zoom: 9 },
    "Delhi": { center: [28.7041, 77.1025], zoom: 10 },
    "Goa": { center: [15.2993, 74.1240], zoom: 9 },
    "Gujarat": { center: [22.2587, 71.1924], zoom: 7 },
    "Haryana": { center: [29.0588, 76.0856], zoom: 7 },
    "Himachal Pradesh": { center: [31.1048, 77.1734], zoom: 7 },
    "Jammu and Kashmir": { center: [33.7782, 76.5762], zoom: 7 },
    "Jharkhand": { center: [23.6102, 85.2799], zoom: 7 },
    "Karnataka": { center: [15.3173, 75.7139], zoom: 7 },
    "Kerala": { center: [10.8505, 76.2711], zoom: 7 },
    "Ladakh": { center: [34.1526, 77.5771], zoom: 7 },
    "Lakshadweep": { center: [10.5667, 72.6417], zoom: 7 },
    "Madhya Pradesh": { center: [22.9734, 78.6569], zoom: 6 },
    "Maharashtra": { center: [19.7515, 75.7139], zoom: 6 },
    "Manipur": { center: [24.6637, 93.9063], zoom: 8 },
    "Meghalaya": { center: [25.4670, 91.3662], zoom: 8 },
    "Mizoram": { center: [23.1645, 92.9376], zoom: 8 },
    "Nagaland": { center: [26.1584, 94.5624], zoom: 8 },
    "Odisha": { center: [20.9517, 85.0985], zoom: 7 },
    "Puducherry": { center: [11.9416, 79.8083], zoom: 10 },
    "Punjab": { center: [31.1471, 75.3412], zoom: 7 },
    "Rajasthan": { center: [27.0238, 74.2179], zoom: 6 },
    "Sikkim": { center: [27.5330, 88.5122], zoom: 8 },
    "Tamil Nadu": { center: [11.1271, 78.6569], zoom: 6 },
    "Telangana": { center: [18.1124, 79.0193], zoom: 7 },
    "Tripura": { center: [23.9408, 91.9882], zoom: 8 },
    "Uttar Pradesh": { center: [26.8467, 80.9462], zoom: 6 },
    "Uttarakhand": { center: [30.0668, 79.0193], zoom: 7 },
    "West Bengal": { center: [22.9868, 87.8550], zoom: 7 }
};

const map = L.map('map', { zoomControl: false }).setView([22.0, 79.0], 5);
L.control.zoom({ position: 'bottomleft' }).addTo(map);

const tiles = {
    standard: L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', { maxZoom: 18 }),
    satellite: L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', { maxZoom: 18 })
};
tiles.standard.addTo(map);

document.addEventListener("DOMContentLoaded", () => {
    fetch(`${API_BASE_URL}/api/fires/india`)
        .then(res => res.json())
        .then(data => {
            if (!data.features) return;
            globalFires = data.features;
            
            initializeStatistics(globalFires);
            updateDashboard(globalFires);
        });

    document.getElementById("category-filter").addEventListener("change", applyFilters);
    document.getElementById("state-filter").addEventListener("change", applyFilters);
    document.getElementById("frp-filter").addEventListener("input", applyFilters);
    
    document.getElementById("close-drawer").addEventListener("click", () => {
        document.getElementById("side-drawer").classList.add("hidden");
    });

    document.getElementById("map-style").addEventListener("change", (e) => {
        const style = e.target.value;
        map.removeLayer(tiles.standard);
        map.removeLayer(tiles.satellite);
        const mapContainer = document.getElementById("map");

        if (style === "satellite") {
            tiles.satellite.addTo(map);
            mapContainer.classList.remove("high-contrast-map");
        } else if (style === "high-contrast") {
            tiles.standard.addTo(map);
            mapContainer.classList.add("high-contrast-map");
        } else {
            tiles.standard.addTo(map);
            mapContainer.classList.remove("high-contrast-map");
        }
    });
});

function initializeStatistics(features) {
    let controlled = 0, unintended = 0;
    
    features.forEach(f => {
        const type = f.properties.source_type;
        if (type === "gas_flare" || type === "mining_activity") {
            controlled++;
        } else if (type === "wildfire" || type === "agricultural_burning" || type === "industrial_fire") {
            unintended++;
        }
    });

    document.getElementById("stat-total").innerText = features.length;
    document.getElementById("stat-controlled").innerText = controlled;
    document.getElementById("stat-unintended").innerText = unintended;
    
    const maxFrp = features.length > 0 ? Math.max(...features.map(f => f.properties.frp_mw || 0)) : 0;
    document.getElementById("max-frp-label").innerText = `Max FRP: ${maxFrp.toFixed(1)} k MW`;
}

function applyFilters() {
    const category = document.getElementById("category-filter").value;
    const state = document.getElementById("state-filter").value;
    const minFrp = parseFloat(document.getElementById("frp-filter").value) || 0;

    const filtered = globalFires.filter(f => {
        const matchCat = category === "all" || f.properties.source_type === category;
        const matchState = state === "all" || f.properties.state === state;
        const matchFrp = (f.properties.frp_mw || 0) >= minFrp;
        return matchCat && matchState && matchFrp;
    });

    updateDashboard(filtered);

    if (state !== "all" && STATE_VIEWS[state]) {
        map.flyTo(STATE_VIEWS[state].center, STATE_VIEWS[state].zoom, { duration: 1.5 });
    } else {
        map.flyTo([22.0, 79.0], 5, { duration: 1.5 });
    }
}

function updateDashboard(features) {
    if (geoJsonLayer) map.removeLayer(geoJsonLayer);

    geoJsonLayer = L.geoJSON(features, {
        pointToLayer: (feature, latlng) => {
            let color = "#ff0000"; 
            const type = feature.properties.source_type;
            if (type === "industrial_fire") color = "#800080"; 
            if (type === "gas_flare") color = "#ffa500";       
            if (type === "mining_activity") color = "#000000"; 
            if (type === "agricultural_burning") color = "#008000";

            return L.circleMarker(latlng, { radius: 7, fillColor: color, color: "#fff", weight: 1.5, opacity: 1, fillOpacity: 0.9 });
        }
    });
    
    geoJsonLayer.on('click', (e) => openDrawer(e.layer.feature.properties));
    geoJsonLayer.addTo(map);
}

function openDrawer(props) {
    document.getElementById("side-drawer").classList.remove("hidden");
    
    let displayType = "WILDFIRE";
    if (props.source_type) {
        if (props.source_type === "industrial_fire") {
            displayType = "INDUSTRIAL DISASTER";
        } else {
            displayType = props.source_type.replace('_', ' ').toUpperCase();
        }
    }
    
    const zoneBadge = props.is_industrial ? `<span class="tag-badge">Industrial Zone</span>` : props.is_mining ? `<span class="tag-badge">Mining Zone</span>` : "";
    const city = props.city && props.city !== "Unknown" ? props.city : "Unknown";
    const state = props.state && props.state !== "Unknown" ? props.state : "Unknown";

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
}
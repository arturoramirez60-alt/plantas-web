(() => {
    const mapElement = document.querySelector("#community-map");
    if (!mapElement) return;

    const countOutput = document.querySelector("[data-community-count]");
    const selectionOutput = document.querySelector("[data-community-selection]");
    const gardenList = document.querySelector("[data-community-gardens]");
    const mapStatus = document.querySelector("[data-map-status]");
    const filters = document.querySelectorAll("[data-community-filter]");

    if (!window.L) {
        console.error("No se pudo cargar Leaflet para el mapa.");
        if (mapStatus) mapStatus.textContent = "No se pudo cargar el mapa. Revisa tu conexión.";
        return;
    }

    const mexicoBounds = L.latLngBounds([14.5, -118.5], [32.8, -86.7]);
    const map = L.map(mapElement, {
        maxBounds: mexicoBounds.pad(0.08),
        maxBoundsViscosity: 0.8,
        minZoom: 4,
        maxZoom: 12,
        scrollWheelZoom: true,
    });
    const baseTiles = L.tileLayer("https://tile.openstreetmap.de/{z}/{x}/{y}.png", {
        maxZoom: 20,
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors · tiles <a href="https://www.openstreetmap.de/">OpenStreetMap.de</a>',
    });
    let tileLoadFailed = false;
    baseTiles.on("tileerror", (event) => {
        tileLoadFailed = true;
        console.warn("No se pudo cargar un mosaico del mapa.", event.error || event.tile?.src);
        if (mapStatus) mapStatus.textContent = "No se pudieron cargar algunos mosaicos. Revisa tu conexión.";
    });
    baseTiles.on("load", () => {
        if (!tileLoadFailed && mapStatus) mapStatus.textContent = "Mapa cargado";
    });
    baseTiles.addTo(map);
    map.fitBounds(mexicoBounds, { padding: [14, 14] });

    const gardenMarkers = L.layerGroup().addTo(map);
    let searchTimer;
    let requestNumber = 0;

    function setSelection(garden) {
        if (!selectionOutput) return;
        selectionOutput.replaceChildren();

        const title = document.createElement("h3");
        title.textContent = garden.name;
        selectionOutput.append(title);

        const location = document.createElement("p");
        location.textContent = `${garden.city} · ${garden.zone}${garden.is_demo ? " · DEMO ficticio" : ""}`;
        selectionOutput.append(location);

        const plants = document.createElement("p");
        plants.textContent = garden.plants.length
            ? `Cultiva: ${garden.plants.map((plant) => plant.name).join(", ")}`
            : "Aún está preparando su huerto.";
        selectionOutput.append(plants);

        const profile = document.createElement("a");
        profile.href = garden.profile;
        profile.textContent = "Ver perfil del huerto ↗";
        selectionOutput.append(profile);
        gardenList?.querySelectorAll(".map-garden-button").forEach((button) => {
            button.classList.toggle("is-active", Number(button.dataset.gardenId) === garden.id);
        });
    }

    function renderGardens(gardens) {
        gardenMarkers.clearLayers();
        gardenList?.replaceChildren();

        gardens.forEach((garden) => {
            const marker = L.circleMarker([garden.lat, garden.lng], {
                radius: 7,
                color: garden.is_demo ? "#9a6b22" : "#a94e34",
                weight: 2,
                fillColor: garden.is_demo ? "#e5aa54" : "#dc764f",
                fillOpacity: 0.9,
            });
            marker.bindTooltip(garden.name, { direction: "top", offset: [0, -6] });
            marker.on("click", () => setSelection(garden));
            gardenMarkers.addLayer(marker);

            if (gardenList) {
                const button = document.createElement("button");
                button.type = "button";
                button.className = "map-garden-button";
                button.dataset.gardenId = garden.id;
                button.textContent = garden.name;
                const place = document.createElement("small");
                place.textContent = `${garden.city} · ${garden.zone}`;
                button.append(place);
                button.addEventListener("click", () => {
                    map.panTo([garden.lat, garden.lng]);
                    setSelection(garden);
                });
                gardenList.append(button);
            }
        });

        if (selectionOutput) {
            selectionOutput.replaceChildren();
            const message = document.createElement("p");
            message.textContent = gardens.length
                ? "Selecciona un punto del mapa o un huerto de la lista."
                : "Aún no hay huertos publicados en México.";
            selectionOutput.append(message);
        }
    }

    async function loadGardens() {
        const currentRequest = ++requestNumber;
        const params = new URLSearchParams();
        filters.forEach((filter) => {
            if (filter.type === "checkbox" && filter.checked) {
                params.set(filter.dataset.communityFilter, "1");
            } else if (filter.type !== "checkbox" && filter.value.trim()) {
                params.set(filter.dataset.communityFilter, filter.value.trim());
            }
        });
        if (countOutput) countOutput.textContent = "Buscando huertos…";

        try {
            const response = await fetch(`${mapElement.dataset.communityUrl}?${params.toString()}`);
            if (!response.ok) throw new Error(`Error HTTP ${response.status} al cargar la comunidad.`);
            const gardens = await response.json();
            if (currentRequest !== requestNumber) return;
            renderGardens(gardens);
            if (countOutput) {
                countOutput.textContent = `${gardens.length} ${gardens.length === 1 ? "huerto" : "huertos"} en México`;
            }
        } catch (error) {
            if (currentRequest !== requestNumber) return;
            console.error("No se pudieron cargar los huertos de México.", error);
            if (countOutput) countOutput.textContent = "No se pudo cargar la comunidad. Intenta de nuevo.";
        }
    }

    new ResizeObserver(() => map.invalidateSize({ pan: false })).observe(mapElement);
    filters.forEach((filter) => {
        filter.addEventListener(filter.type === "search" ? "input" : "change", () => {
            window.clearTimeout(searchTimer);
            searchTimer = window.setTimeout(loadGardens, filter.type === "search" ? 250 : 0);
        });
    });
    loadGardens();
})();

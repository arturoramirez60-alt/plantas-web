(() => {
    const seedDataElement = document.querySelector("#seed-data");
    let seeds = [];
    if (seedDataElement) {
        try {
            seeds = JSON.parse(seedDataElement.textContent);
        } catch (error) {
            console.error("No se pudo leer el catálogo de semillas.", error);
        }
    }

    const seedSelect = document.querySelector("#seed-select");
    const kitSelect = document.querySelector("#kit-select");
    const kitTypeInput = document.querySelector("#builder-kit-type");
    const seedIdInput = document.querySelector("#builder-seed-id");
    const priceOutput = document.querySelector("#builder-price");
    const includesOutput = document.querySelector("#builder-includes");
    const potOutput = document.querySelector("#builder-pot");
    const nameOutput = document.querySelector("#builder-seed-name");
    const demoMode = seedDataElement?.dataset.demoMode === "true";

    function updateBuilder() {
        if (!seedSelect || !kitSelect || !seeds.length) return;
        const seed = seeds.find((entry) => String(entry.id) === seedSelect.value);
        const kitType = kitSelect.value;
        if (!seed || seed.prices[kitType] == null) return;
        nameOutput.textContent = seed.name;
        potOutput.textContent = kitType === "seed_only" ? "" : `Maceta recomendada: ${seed.pot_size}`;
        priceOutput.textContent = demoMode ? "Gratis" : `$${Number(seed.prices[kitType]).toLocaleString("es-MX")} MXN`;
        includesOutput.replaceChildren(...seed.contents[kitType].map((item) => {
            const element = document.createElement("li");
            element.textContent = item;
            return element;
        }));
        seedIdInput.value = seed.id;
        kitTypeInput.value = kitType;
    }

    seedSelect?.addEventListener("change", updateBuilder);
    kitSelect?.addEventListener("change", updateBuilder);
    updateBuilder();

    const filterButtons = document.querySelectorAll("[data-catalog-filter]");
    const catalogItems = document.querySelectorAll("[data-catalog-item]");
    const emptyCatalog = document.querySelector("[data-catalog-empty]");
    filterButtons.forEach((button) => {
        button.addEventListener("click", () => {
            const filter = button.dataset.catalogFilter;
            let visible = 0;
            filterButtons.forEach((candidate) => candidate.classList.toggle("is-active", candidate === button));
            catalogItems.forEach((item) => {
                const show = filter === "all" || item.dataset.kind === filter;
                item.hidden = !show;
                if (show) visible += 1;
            });
            if (emptyCatalog) emptyCatalog.hidden = visible !== 0;
        });
    });

    document.querySelectorAll("[data-guide-step]").forEach((checkbox) => {
        const key = `raiz-guide-${checkbox.dataset.guideStep}`;
        checkbox.checked = localStorage.getItem(key) === "done";
        checkbox.addEventListener("change", () => {
            if (checkbox.checked) localStorage.setItem(key, "done");
            else localStorage.removeItem(key);
        });
    });

    const mapElement = document.querySelector("#community-map");
    if (mapElement && window.L && window.L.markerClusterGroup) {
        const map = L.map(mapElement).setView([19.4326, -99.1332], 5);
        L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
            maxZoom: 19,
            attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
        }).addTo(map);
        const countOutput = document.querySelector("[data-community-count]");
        const markerGroup = L.markerClusterGroup();
        markerGroup.addTo(map);
        const filters = document.querySelectorAll("[data-community-filter]");
        let requestNumber = 0;
        let hasFittedBounds = false;

        function popupFor(garden) {
            const popup = document.createElement("article");
            popup.className = "garden-popup";
            if (garden.photo) {
                const photo = document.createElement("img");
                photo.src = garden.photo;
                photo.alt = `Huerto ${garden.name}`;
                popup.append(photo);
            }
            const name = document.createElement("strong");
            name.textContent = garden.name;
            popup.append(name);
            const alias = document.createElement("p");
            alias.textContent = `Por ${garden.alias}${garden.is_demo ? " · DEMO ficticio" : ""}`;
            popup.append(alias);
            const location = document.createElement("p");
            location.textContent = `${garden.city} · ${garden.zone}`;
            popup.append(location);
            const typeLabels = {
                interior: "Interior",
                exterior: "Exterior",
                balcon: "Balcón",
                terraza: "Terraza",
                otro: "Otro",
            };
            const description = document.createElement("p");
            description.textContent = garden.description;
            popup.append(description);
            const gardenType = document.createElement("p");
            gardenType.textContent = `Huerto ${typeLabels[garden.type] || "Otro"}`;
            popup.append(gardenType);
            const plants = document.createElement("p");
            plants.textContent = garden.plants.length
                ? `Cultiva: ${garden.plants.map((plant) => plant.name).join(", ")}`
                : "Aún está preparando su huerto.";
            popup.append(plants);
            const sharing = [];
            if (garden.share_seeds) sharing.push("Semillas");
            if (garden.share_cuttings) sharing.push("Esquejes");
            if (garden.share_advice) sharing.push("Consejos");
            const availability = document.createElement("p");
            availability.textContent = sharing.length ? `Comparte: ${sharing.join(", ")}` : "No indica intercambios disponibles.";
            popup.append(availability);
            const profile = document.createElement("a");
            profile.href = garden.profile;
            profile.textContent = "Ver perfil del huerto ↗";
            popup.append(profile);
            return popup;
        }

        async function loadGardens() {
            const currentRequest = ++requestNumber;
            const params = new URLSearchParams();
            filters.forEach((filter) => {
                if (filter.type === "checkbox" && filter.checked) params.set(filter.dataset.communityFilter, "1");
                else if (filter.type !== "checkbox" && filter.value.trim()) params.set(filter.dataset.communityFilter, filter.value.trim());
            });
            if (countOutput) countOutput.textContent = "Buscando huertos…";
            try {
                const response = await fetch(`${mapElement.dataset.communityUrl}?${params.toString()}`);
                if (!response.ok) throw new Error("No se pudo cargar la comunidad.");
                const gardens = await response.json();
                if (currentRequest !== requestNumber) return;
                markerGroup.clearLayers();
                gardens.forEach((garden) => {
                    L.marker([garden.lat, garden.lng]).bindPopup(popupFor(garden)).addTo(markerGroup);
                });
                if (gardens.length && !hasFittedBounds) {
                    map.fitBounds(L.latLngBounds(gardens.map((garden) => [garden.lat, garden.lng])).pad(0.18), { maxZoom: 11 });
                    hasFittedBounds = true;
                }
                if (countOutput) {
                    countOutput.textContent = `${gardens.length} ${gardens.length === 1 ? "huerto encontrado" : "huertos encontrados"}`;
                }
            } catch (error) {
                if (currentRequest !== requestNumber) return;
                console.error(error);
                if (countOutput) countOutput.textContent = "No se pudo cargar la comunidad. Intenta de nuevo.";
            }
        }

        let searchTimer;
        filters.forEach((filter) => {
            filter.addEventListener(filter.type === "search" ? "input" : "change", () => {
                window.clearTimeout(searchTimer);
                searchTimer = window.setTimeout(loadGardens, filter.type === "search" ? 250 : 0);
            });
        });
        loadGardens();
    } else if (mapElement) {
        const countOutput = document.querySelector("[data-community-count]");
        if (countOutput) countOutput.textContent = "No se pudo cargar el mapa. Revisa la conexión e inténtalo de nuevo.";
    }
})();

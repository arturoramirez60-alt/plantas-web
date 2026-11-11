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

    function updateBuilder() {
        if (!seedSelect || !kitSelect || !seeds.length) return;
        const seed = seeds.find((entry) => String(entry.id) === seedSelect.value);
        const kitType = kitSelect.value;
        if (!seed || !seed.prices[kitType]) return;
        nameOutput.textContent = seed.name;
        potOutput.textContent = kitType === "seed_only" ? "" : `Maceta recomendada: ${seed.pot_size}`;
        priceOutput.innerHTML = `$${Number(seed.prices[kitType]).toLocaleString("es-MX")} <small>MXN</small>`;
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
    if (mapElement && window.L) {
        const map = L.map(mapElement).setView([19.4326, -99.1332], 5);
        L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
            maxZoom: 19,
            attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
        }).addTo(map);
        const countOutput = document.querySelector("[data-community-count]");
        fetch(mapElement.dataset.communityUrl)
            .then((response) => {
                if (!response.ok) throw new Error("No se pudo cargar la comunidad.");
                return response.json();
            })
            .then((members) => {
                members.forEach((member) => {
                    const popup = document.createElement("div");
                    const name = document.createElement("strong");
                    name.textContent = member.username;
                    popup.append(name);
                    if (member.city) {
                        const city = document.createElement("p");
                        city.textContent = member.city;
                        popup.append(city);
                    }
                    const plants = document.createElement("p");
                    plants.textContent = member.plants.length ? `Cultiva: ${member.plants.join(", ")}` : "Aún está preparando su huerto.";
                    popup.append(plants);
                    if (member.contact) {
                        const contact = document.createElement("a");
                        contact.href = `mailto:${member.contact}`;
                        contact.textContent = "Contactar";
                        popup.append(contact);
                    }
                    L.marker([member.lat, member.lng]).addTo(map).bindPopup(popup);
                });
                if (members.length) {
                    const bounds = L.latLngBounds(members.map((member) => [member.lat, member.lng]));
                    map.fitBounds(bounds.pad(0.18), { maxZoom: 10 });
                }
                if (countOutput) countOutput.textContent = `${members.length} ${members.length === 1 ? "huerto compartido" : "huertos compartidos"}`;
            })
            .catch(() => {
                if (countOutput) countOutput.textContent = "No se pudo cargar la comunidad.";
            });
    }
})();

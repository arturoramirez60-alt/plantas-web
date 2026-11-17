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

})();

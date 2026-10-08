const PAGE_SIZE = 25;
const state = {
  view: "overview",
  page: 0,
  query: "",
  source: "",
  stock: "",
  sort: "recent",
  overview: null,
  toastTimer: null,
  searchTimer: null,
};

const $ = (selector) => document.querySelector(selector);
const rows = $("#product-rows");

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (character) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  })[character]);
}

function formatNumber(value) {
  return new Intl.NumberFormat("en-BD", { maximumFractionDigits: 0 }).format(value || 0);
}

function formatPrice(value) {
  if (value === null || value === undefined || value === "") return "Not listed";
  return `৳${new Intl.NumberFormat("en-BD", { maximumFractionDigits: 2 }).format(value)}`;
}

function formatDate(value, options = { day: "numeric", month: "short", year: "numeric" }) {
  if (!value) return "Not recorded";
  const date = new Date(String(value).includes("T") ? value : `${value.replace(" ", "T")}Z`);
  return Number.isNaN(date.getTime()) ? "Not recorded" : new Intl.DateTimeFormat("en-BD", options).format(date);
}

function retailerName(value) {
  return String(value || "Unknown").replace(/(^|[-\s])([a-z])/g, (_, prefix, letter) => `${prefix}${letter.toUpperCase()}`);
}

function showToast(message) {
  const toast = $("#toast");
  toast.textContent = message;
  toast.classList.add("is-visible");
  window.clearTimeout(state.toastTimer);
  state.toastTimer = window.setTimeout(() => toast.classList.remove("is-visible"), 4200);
}

async function request(url) {
  const response = await fetch(url, { headers: { Accept: "application/json" } });
  if (!response.ok) {
    let detail = `Request failed (${response.status}).`;
    try {
      const body = await response.json();
      detail = body.detail || detail;
    } catch {
      // Keep the HTTP status message when an upstream error isn't JSON.
    }
    throw new Error(detail);
  }
  return response.json();
}

function setConnection(connected) {
  const indicator = document.querySelector(".live-indicator");
  indicator.innerHTML = connected
    ? "<span></span>Connected to local data"
    : "<span></span>Data connection unavailable";
  indicator.classList.toggle("is-disconnected", !connected);
}

async function loadOverview() {
  const data = await request("/api/overview");
  state.overview = data;
  $("#metric-products").textContent = formatNumber(data.products);
  $("#metric-observations").textContent = formatNumber(data.observations);
  $("#metric-stockouts").textContent = formatNumber(data.out_of_stock);
  $("#nav-product-count").textContent = formatNumber(data.products);
  $("#nav-stock-count").textContent = formatNumber(data.out_of_stock);
  $("#retailer-total").textContent = formatNumber(data.retailers);
  $("#last-updated").textContent = formatDate(data.last_updated, {
    day: "numeric", month: "short", year: "numeric", hour: "numeric", minute: "2-digit",
  });
  renderRetailers(data.retailer_breakdown);
  renderActivity(data.daily_activity);

  const sourceSelect = $("#source-filter");
  const selected = state.source;
  sourceSelect.innerHTML = '<option value="">All retailers</option>' + data.retailer_breakdown
    .map((retailer) => `<option value="${escapeHtml(retailer.source)}">${escapeHtml(retailerName(retailer.source))}</option>`)
    .join("");
  sourceSelect.value = selected;
  setConnection(true);
  return data;
}

function renderRetailers(retailers) {
  const list = $("#retailer-list");
  if (!retailers.length) {
    list.innerHTML = '<p class="muted-copy">No retailer observations yet.</p>';
    return;
  }
  const max = Math.max(...retailers.map((retailer) => retailer.products), 1);
  list.innerHTML = retailers.map((retailer) => `
    <button class="retailer-row" type="button" data-source="${escapeHtml(retailer.source)}" aria-label="Show ${escapeHtml(retailerName(retailer.source))} listings">
      <span class="retailer-name">${escapeHtml(retailerName(retailer.source))}</span>
      <span class="retailer-number">${formatNumber(retailer.products)} items</span>
      <span class="retailer-bar"><i style="width:${Math.max(4, retailer.products / max * 100)}%"></i></span>
    </button>`).join("");
}

function renderActivity(activity) {
  const container = $("#activity-chart");
  if (!activity.length) {
    container.innerHTML = '<p class="chart-empty">No collection activity has been recorded yet.</p>';
    $("#chart-start").textContent = "";
    $("#chart-end").textContent = "";
    return;
  }
  const width = 600;
  const height = 86;
  const inset = { left: 10, right: 10, top: 9, bottom: 8 };
  const values = activity.map((point) => point.observations);
  const maximum = Math.max(...values, 1);
  const xStep = activity.length > 1 ? (width - inset.left - inset.right) / (activity.length - 1) : 0;
  const points = activity.map((point, index) => ({
    x: activity.length > 1 ? inset.left + index * xStep : width / 2,
    y: height - inset.bottom - (point.observations / maximum) * (height - inset.top - inset.bottom),
    ...point,
  }));
  const path = points.map((point, index) => `${index ? "L" : "M"}${point.x.toFixed(1)},${point.y.toFixed(1)}`).join(" ");
  const area = `${path} L${points.at(-1).x},${height - inset.bottom} L${points[0].x},${height - inset.bottom} Z`;
  const tickY = height - inset.bottom;
  const labels = points.length === 1
    ? `<text x="${points[0].x}" y="${height - 1}" text-anchor="middle">${escapeHtml(formatDate(points[0].day, { day: "numeric", month: "short" }))}</text>`
    : `<text x="${inset.left}" y="${height - 1}">${escapeHtml(formatDate(points[0].day, { day: "numeric", month: "short" }))}</text><text x="${width - inset.right}" y="${height - 1}" text-anchor="end">${escapeHtml(formatDate(points.at(-1).day, { day: "numeric", month: "short" }))}</text>`;
  const circles = points.map((point) => `<circle cx="${point.x}" cy="${point.y}" r="3.3"><title>${escapeHtml(point.day)}: ${formatNumber(point.observations)} observations</title></circle>`).join("");
  container.innerHTML = `<svg viewBox="0 0 ${width} ${height}" preserveAspectRatio="none" role="img" aria-label="${activity.length} collection dates, ${formatNumber(values.reduce((sum, value) => sum + value, 0))} observations">
    <path d="M${inset.left},${inset.top} H${width - inset.right} M${inset.left},${(inset.top + tickY) / 2} H${width - inset.right} M${inset.left},${tickY} H${width - inset.right}" class="chart-grid"/>
    <path d="${area}" class="chart-area"/><path d="${path}" class="chart-line"/>${circles}
    <g class="chart-labels">${labels}</g></svg>`;
  $("#chart-start").textContent = points.length > 1 ? formatDate(points[0].day, { day: "numeric", month: "short" }) : "";
  $("#chart-end").textContent = points.length > 1 ? formatDate(points.at(-1).day, { day: "numeric", month: "short" }) : "";
}

function updateHeading() {
  const headings = {
    overview: ["Overview", "Product watch", "A live view of the latest listings"],
    products: ["Product watch", "Product watch", "A live view of the latest listings"],
    stockouts: ["Out of stock", "Out of stock", "Listings currently marked unavailable"],
    shrinkflation: ["Pack-size watch", "Pack-size watch", "Potential pack-size changes to review"],
  };
  const [crumb, title, kicker] = headings[state.view];
  $("#page-name").textContent = crumb;
  $("#ledger-title").textContent = title;
  $("#ledger-kicker").textContent = kicker;
  document.querySelectorAll(".nav-item").forEach((button) => {
    const active = button.dataset.view === state.view;
    button.classList.toggle("is-active", active);
    button.setAttribute("aria-current", active ? "page" : "false");
  });
}

function productRow(item) {
  const availability = item.stock_flag || "unknown";
  const availabilityText = {
    in_stock: "Available",
    out_of_stock: "Out of stock",
    unknown: "Not reported",
  }[availability] || "Not reported";
  const historyButton = item.id
    ? `<button class="history-link" type="button" data-history="${item.id}" aria-label="View price history for ${escapeHtml(item.title)}"><svg><use href="#i-arrow"/></svg>History</button>`
    : "";
  const listPrice = item.list_price && item.list_price > item.price
    ? `<span class="price-list">${escapeHtml(formatPrice(item.list_price))}</span>`
    : "";
  const category = item.category_path ? `<span class="product-category">${escapeHtml(item.category_path)}</span>` : "";
  return `<tr>
    <td><span class="product-title" title="${escapeHtml(item.title)}">${escapeHtml(item.title)}</span>${category}</td>
    <td><span class="source-name">${escapeHtml(retailerName(item.source))}</span></td>
    <td><span class="price-value">${escapeHtml(formatPrice(item.price))}</span>${listPrice}</td>
    <td><span class="status-pill status-${escapeHtml(availability)}">${escapeHtml(availabilityText)}</span></td>
    <td>${escapeHtml(formatDate(item.scraped_at, { day: "numeric", month: "short" }))}</td>
    <td>${historyButton}</td>
  </tr>`;
}

function renderRows(items, total, page, paginated = true) {
  if (!items.length) {
    const message = state.view === "shrinkflation"
      ? "No pack-size reductions are supported by the available product history."
      : state.view === "stockouts"
        ? "No listings are currently marked out of stock. Availability comes from the latest retailer snapshot."
        : "No products match these filters. Try a different search or retailer.";
    rows.innerHTML = `<tr><td class="table-message" colspan="6">${escapeHtml(message)}</td></tr>`;
  } else {
    rows.innerHTML = items.map(productRow).join("");
  }
  const pages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  $("#result-count").textContent = `${formatNumber(total)} ${total === 1 ? "listing" : "listings"}`;
  $("#page-number").textContent = `${page + 1} of ${pages}`;
  $("#page-summary").textContent = paginated
    ? `Showing ${total ? formatNumber(page * PAGE_SIZE + 1) : 0}–${formatNumber(Math.min((page + 1) * PAGE_SIZE, total))} of ${formatNumber(total)}`
    : `${formatNumber(total)} results`;
  $("#previous-page").disabled = page === 0;
  $("#next-page").disabled = !paginated || page >= pages - 1;
}

function matchesFilters(item) {
  const query = state.query.trim().toLocaleLowerCase();
  return (!state.source || item.source === state.source)
    && (!query || `${item.title || ""} ${item.category_path || ""}`.toLocaleLowerCase().includes(query));
}

function sortItems(items) {
  const sorted = [...items];
  if (state.sort === "name") sorted.sort((a, b) => a.title.localeCompare(b.title));
  if (state.sort === "price_low") sorted.sort((a, b) => (a.price ?? Infinity) - (b.price ?? Infinity));
  if (state.sort === "price_high") sorted.sort((a, b) => (b.price ?? -Infinity) - (a.price ?? -Infinity));
  if (state.sort === "recent") sorted.sort((a, b) => String(b.scraped_at).localeCompare(String(a.scraped_at)));
  return sorted;
}

async function loadProducts() {
  rows.innerHTML = '<tr><td class="table-message" colspan="6">Loading listings…</td></tr>';
  $("#result-count").textContent = "Loading listings…";
  $("#page-summary").textContent = "";
  $("#previous-page").disabled = true;
  $("#next-page").disabled = true;
  try {
    if (state.view === "stockouts" || state.view === "shrinkflation") {
      const path = state.view === "stockouts" ? "/api/stockouts/current" : "/api/shrinkflation/alerts";
      const data = await request(path);
      const items = sortItems(data.filter(matchesFilters));
      const pageItems = items.slice(state.page * PAGE_SIZE, (state.page + 1) * PAGE_SIZE);
      renderRows(pageItems, items.length, state.page, items.length > PAGE_SIZE);
      return;
    }

    const params = new URLSearchParams({
      limit: PAGE_SIZE,
      offset: state.page * PAGE_SIZE,
      sort: state.sort,
    });
    if (state.query.trim()) params.set("q", state.query.trim());
    if (state.source) params.set("source", state.source);
    if (state.stock) params.set("stock_flag", state.stock);
    const data = await request(`/api/products?${params}`);
    renderRows(data.items, data.total, state.page);
    setConnection(true);
  } catch (error) {
    rows.innerHTML = `<tr><td class="table-message" colspan="6">${escapeHtml(error.message)} Check that the API is running and the database is available.</td></tr>`;
    $("#result-count").textContent = "Could not load listings";
    $("#page-summary").textContent = "Data could not be loaded";
    $("#previous-page").disabled = true;
    $("#next-page").disabled = true;
    setConnection(false);
    showToast(error.message);
  }
}

async function refreshAll() {
  const button = $("#refresh-button");
  button.classList.add("is-loading");
  try {
    await loadOverview();
    await loadProducts();
  } catch (error) {
    setConnection(false);
    showToast(error.message);
  } finally {
    button.classList.remove("is-loading");
  }
}

async function openHistory(snapshotId) {
  const dialog = $("#history-dialog");
  $("#history-title").textContent = "Loading product history…";
  $("#history-source").textContent = "Product history";
  $("#history-chart").innerHTML = "";
  $("#history-list").innerHTML = '<p class="muted-copy">Loading recorded prices…</p>';
  dialog.showModal();
  try {
    const data = await request(`/api/products/${encodeURIComponent(snapshotId)}/history`);
    $("#history-title").textContent = data.title;
    $("#history-source").textContent = retailerName(data.source);
    renderHistory(data.history);
  } catch (error) {
    $("#history-list").innerHTML = `<p class="muted-copy">${escapeHtml(error.message)}</p>`;
    showToast(error.message);
  }
}

function renderHistory(history) {
  const chart = $("#history-chart");
  const values = history.filter((point) => point.price !== null && point.price !== undefined);
  if (values.length < 2) {
    chart.innerHTML = '<p class="chart-empty">A price trend needs at least two recorded prices. Check back after another collection.</p>';
  } else {
    const width = 500;
    const height = 160;
    const inset = 16;
    const prices = values.map((point) => point.price);
    const min = Math.min(...prices);
    const max = Math.max(...prices);
    const range = max - min || 1;
    const points = values.map((point, index) => ({
      x: inset + index * (width - inset * 2) / (values.length - 1),
      y: height - inset - (point.price - min) / range * (height - inset * 2),
    }));
    const path = points.map((point, index) => `${index ? "L" : "M"}${point.x.toFixed(1)},${point.y.toFixed(1)}`).join(" ");
    const area = `${path} L${points.at(-1).x},${height - inset} L${points[0].x},${height - inset} Z`;
    chart.innerHTML = `<svg viewBox="0 0 ${width} ${height}" role="img" aria-label="Price ranged from ${escapeHtml(formatPrice(min))} to ${escapeHtml(formatPrice(max))}">
      <path d="M${inset},${height - inset} H${width - inset}" class="chart-grid"/>
      <path d="${area}" class="chart-area"/><path d="${path}" class="chart-line"/>
      ${points.map((point, index) => `<circle cx="${point.x}" cy="${point.y}" r="3.5"><title>${escapeHtml(formatDate(values[index].scraped_at))}: ${escapeHtml(formatPrice(values[index].price))}</title></circle>`).join("")}
      <text x="${inset}" y="12">${escapeHtml(formatPrice(max))}</text><text x="${inset}" y="${height - 1}">${escapeHtml(formatPrice(min))}</text>
    </svg>`;
  }
  $("#history-list").innerHTML = [...history].reverse().map((point) => `
    <div class="history-row">
      <span>${escapeHtml(formatDate(point.scraped_at, { day: "numeric", month: "short", year: "numeric" }))} · ${escapeHtml(point.stock_flag || "unknown").replaceAll("_", " ")}</span>
      <strong>${escapeHtml(formatPrice(point.price))}</strong>
    </div>`).join("");
}

function applyView(view) {
  state.view = view;
  state.page = 0;
  state.query = "";
  state.stock = "";
  $("#search-input").value = "";
  $("#stock-filter").value = "";
  updateHeading();
  if (view === "overview") {
    window.scrollTo({ top: 0, behavior: "smooth" });
  } else {
    $("#product-ledger").scrollIntoView({ behavior: "smooth", block: "start" });
  }
  loadProducts();
}

function start() {
  $("#today-label").textContent = new Intl.DateTimeFormat("en-BD", {
    weekday: "long", day: "numeric", month: "long",
  }).format(new Date());
  updateHeading();
  document.querySelectorAll(".nav-item").forEach((button) => {
    button.addEventListener("click", () => applyView(button.dataset.view));
  });
  $("#search-input").addEventListener("input", (event) => {
    window.clearTimeout(state.searchTimer);
    state.query = event.target.value;
    state.page = 0;
    state.searchTimer = window.setTimeout(loadProducts, 240);
  });
  $("#source-filter").addEventListener("change", (event) => {
    state.source = event.target.value;
    state.page = 0;
    loadProducts();
  });
  $("#stock-filter").addEventListener("change", (event) => {
    state.stock = event.target.value;
    state.page = 0;
    loadProducts();
  });
  $("#sort-select").addEventListener("change", (event) => {
    state.sort = event.target.value;
    state.page = 0;
    loadProducts();
  });
  $("#previous-page").addEventListener("click", () => {
    if (state.page > 0) { state.page -= 1; loadProducts(); }
  });
  $("#next-page").addEventListener("click", () => {
    state.page += 1;
    loadProducts();
  });
  $("#refresh-button").addEventListener("click", refreshAll);
  $("#retailer-list").addEventListener("click", (event) => {
    const button = event.target.closest("[data-source]");
    if (!button) return;
    state.source = button.dataset.source;
    $("#source-filter").value = state.source;
    applyView("products");
  });
  rows.addEventListener("click", (event) => {
    const button = event.target.closest("[data-history]");
    if (button) openHistory(button.dataset.history);
  });
  $("#dialog-close").addEventListener("click", () => $("#history-dialog").close());
  $("#history-dialog").addEventListener("click", (event) => {
    if (event.target === event.currentTarget) event.currentTarget.close();
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "/" && !["INPUT", "TEXTAREA", "SELECT"].includes(document.activeElement.tagName)) {
      event.preventDefault();
      $("#search-input").focus();
    }
  });
  refreshAll();
}

document.addEventListener("DOMContentLoaded", start);

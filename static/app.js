const form = document.querySelector('#analysis-form');
const button = document.querySelector('#analyze-button');
const buttonText = button.querySelector('.button-text');
const progress = document.querySelector('#progress');
const progressSteps = [...document.querySelectorAll('.progress-step')];
const resultCard = document.querySelector('#result-card');
const viabilityPill = document.querySelector('#viability-pill');
const motivesList = document.querySelector('#motives-list');
const policiesList = document.querySelector('#policies-list');
const evidenceList = document.querySelector('#evidence-list');
const claimText = document.querySelector('#claim-text');
const copyButton = document.querySelector('#copy-button');
const pdfLink = document.querySelector('#pdf-link');
const historyBody = document.querySelector('#history-body');
const toast = document.querySelector('#toast');
const usageUsed = document.querySelector('#usage-used');
const usageLimit = document.querySelector('#usage-limit');
const reportButtons = [...document.querySelectorAll('[data-report]')];

const dashboardState = {
  radiography: null,
  radiographyInsights: [],
  review: null,
  map: null,
  improvementPlan: [],
};

const loadingMessages = ['Analizando reseña…', 'Consultando políticas…', 'Generando reclamación…'];
let loadingTimer;

function showToast(message, isError = false) {
  toast.textContent = message;
  toast.classList.toggle('is-error', isError);
  toast.classList.add('is-visible');
  window.setTimeout(() => toast.classList.remove('is-visible'), 3200);
}

function setLoading(isLoading) {
  button.disabled = isLoading;
  button.classList.toggle('is-loading', isLoading);
  progress.hidden = !isLoading;
  if (!isLoading) {
    buttonText.textContent = 'Analizar reseña';
    window.clearInterval(loadingTimer);
    progressSteps.forEach((step) => step.classList.remove('is-active', 'is-done'));
    progressSteps[0].classList.add('is-active');
    return;
  }

  let index = 0;
  buttonText.textContent = loadingMessages[index];
  progressSteps.forEach((step, stepIndex) => {
    step.classList.toggle('is-active', stepIndex === 0);
    step.classList.remove('is-done');
  });

  loadingTimer = window.setInterval(() => {
    progressSteps[index]?.classList.remove('is-active');
    progressSteps[index]?.classList.add('is-done');
    index = Math.min(index + 1, loadingMessages.length - 1);
    buttonText.textContent = loadingMessages[index];
    progressSteps[index]?.classList.add('is-active');
  }, 650);
}

function listItem(text) {
  const li = document.createElement('li');
  li.textContent = text;
  return li;
}

function renderResult(data) {
  if (usageUsed && data.analyses_used_month !== undefined) {
    usageUsed.textContent = data.analyses_used_month;
  }
  resultCard.hidden = false;
  viabilityPill.className = `viability ${data.viability}`;
  viabilityPill.textContent = `Viabilidad estimada: ${data.viability}`;

  motivesList.replaceChildren();
  data.detected_motives.forEach((motive) => {
    motivesList.appendChild(listItem(`${motive.category}: ${motive.reason}`));
  });
  if (!data.detected_motives.length) {
    motivesList.appendChild(listItem('No se han identificado señales fuertes de infracción con el análisis local.'));
  }

  policiesList.replaceChildren();
  data.applicable_policies.forEach((policy) => {
    const item = document.createElement('div');
    item.className = 'policy-item';
    item.innerHTML = `<strong>${policy.name}</strong><span>${policy.description}</span>`;
    policiesList.appendChild(item);
  });
  if (!data.applicable_policies.length) {
    const item = document.createElement('div');
    item.className = 'policy-item';
    item.innerHTML = '<strong>Sin política específica detectada</strong><span>Revisa manualmente la reseña y aporta evidencias objetivas si decides reclamar.</span>';
    policiesList.appendChild(item);
  }

  evidenceList.replaceChildren();
  data.recommended_evidence.forEach((evidence) => evidenceList.appendChild(listItem(evidence)));

  claimText.value = data.claim_text;
  pdfLink.href = `/claims/${data.id}/pdf`;
  dashboardState.review = data;
  resultCard.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

async function refreshHistory() {
  const response = await fetch('/history');
  const data = await response.json();
  if (data.usage && usageUsed && usageLimit) {
    usageUsed.textContent = data.usage.analyses_used_month;
    usageLimit.textContent = data.usage.analysis_limit_label;
  }
  historyBody.replaceChildren();
  if (!data.items.length) {
    const empty = document.createElement('tr');
    empty.className = 'empty-row';
    empty.innerHTML = '<td colspan="6">Todavía no hay reclamaciones guardadas.</td>';
    historyBody.appendChild(empty);
    return;
  }

  data.items.forEach((item) => {
    const row = document.createElement('tr');
    const cells = [
      `#${item.id}`,
      item.business_name,
      item.reviewer_name,
      item.stars,
    ];

    cells.forEach((value) => {
      const cell = document.createElement('td');
      cell.textContent = value;
      row.appendChild(cell);
    });

    const viabilityCell = document.createElement('td');
    const pill = document.createElement('span');
    pill.className = `mini-pill ${item.viability}`;
    pill.textContent = item.viability;
    viabilityCell.appendChild(pill);
    row.appendChild(viabilityCell);

    const pdfCell = document.createElement('td');
    const link = document.createElement('a');
    link.href = `/claims/${item.id}/pdf`;
    link.textContent = 'PDF';
    pdfCell.appendChild(link);
    row.appendChild(pdfCell);

    historyBody.appendChild(row);
  });
}

form.addEventListener('submit', async (event) => {
  event.preventDefault();
  if (form.dataset.authenticated !== 'true') {
    showToast('Inicia sesión o regístrate para analizar reseñas.', true);
    window.setTimeout(() => { window.location.href = '/login'; }, 900);
    return;
  }
  setLoading(true);
  try {
    const formData = new FormData(form);
    const response = await fetch('/analyze', { method: 'POST', body: formData });
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || 'No se pudo analizar la reseña.');
    }
    renderResult(data);
    await refreshHistory();
    showToast('Análisis completado y guardado en el historial.');
  } catch (error) {
    showToast(error.message, true);
  } finally {
    setLoading(false);
  }
});


copyButton.addEventListener('click', async () => {
  try {
    await navigator.clipboard.writeText(claimText.value);
    showToast('Reclamación copiada al portapapeles.');
  } catch (error) {
    claimText.select();
    document.execCommand('copy');
    showToast('Reclamación copiada.');
  }
});

const radiographyForm = document.querySelector('#radiography-form');
const radiographyResult = document.querySelector('#radiography-result');
const radiographyBrandName = document.querySelector('#radiography-brand-name');
const radiographyInsights = document.querySelector('#radiography-insights');
const companyMapForm = document.querySelector('#company-map-form');
const addDelegationButton = document.querySelector('#add-delegation');
const delegationsContainer = document.querySelector('#delegations-container');
const businessMapElement = document.querySelector('#business-map');
const mapWarning = document.querySelector('#map-warning');
const locationsList = document.querySelector('#locations-list');
const coveragePill = document.querySelector('#coverage-pill');
const improvementGrid = document.querySelector('#improvement-grid');
let businessMap;
let businessMarkersLayer;

function formValue(formData, key, fallback = '') {
  return String(formData.get(key) || fallback).trim();
}

function insightCard(title, text, priority = '') {
  const article = document.createElement('article');
  article.className = 'insight-card';
  const header = document.createElement('div');
  if (priority) {
    const badge = document.createElement('span');
    badge.className = `priority-tag ${priority.toLowerCase()}`;
    badge.textContent = priority;
    header.appendChild(badge);
  }
  const heading = document.createElement('h3');
  heading.textContent = title;
  const paragraph = document.createElement('p');
  paragraph.textContent = text;
  header.appendChild(heading);
  article.append(header, paragraph);
  return article;
}

function buildRadiographyInsights(data) {
  const issue = data.currentIssue || 'no se ha indicado un bloqueo concreto';
  const feedback = data.customerFeedback || 'sin comentarios adicionales de clientes';
  return [
    ['Primera impresión de la marca', `${data.brandName} se presenta en el sector ${data.sector} con una oferta centrada en ${data.offer}. La primera impresión debe hacer evidente en pocos segundos qué problema resuelve y por qué es una opción fiable para ${data.audience}.`, 'Alta'],
    ['Nivel de confianza que transmite', `La confianza dependerá de la coherencia entre lo que quiere transmitir (${data.brandMessage || 'confianza, claridad y profesionalidad'}) y las pruebas visibles: reseñas recientes, datos de contacto, fotografías reales, mensajes consistentes y respuesta a incidencias.`, 'Alta'],
    ['Puntos fuertes detectados', `La especialización sectorial, una propuesta clara para ${data.audience} y la posibilidad de ordenar web, redes y ubicación (${data.location || 'ubicación principal pendiente de definir'}) son activos reputacionales que pueden reforzarse rápidamente.`, 'Media'],
    ['Puntos débiles reputacionales', `El principal punto a revisar es: ${issue}. También conviene auditar si los canales visibles (${data.channels || 'web/redes no indicadas'}) explican bien precios, proceso, garantías y expectativas.`, 'Alta'],
    ['Riesgos de percepción', `Si el cliente encuentra mensajes ambiguos, pocas señales de actividad o feedback sin respuesta (${feedback}), puede interpretar falta de control, poca transparencia o experiencia irregular.`, 'Media'],
    ['Posibles frenos de compra o reserva', 'Dudas sobre precio, resultados, disponibilidad, ubicación, tiempos de respuesta, profesionalidad percibida y gestión de reseñas negativas pueden frenar una compra o reserva aunque la oferta sea buena.', 'Media'],
    ['Qué puede estar pensando un cliente potencial', `“¿Puedo confiar en ${data.brandName}? ¿La experiencia será consistente? ¿Hay pruebas reales de clientes como yo? ¿Qué pasa si tengo un problema?”`, ''],
    ['Recomendaciones concretas', 'Reforzar prueba social real, responder reseñas con tono profesional, simplificar mensajes comerciales, mostrar equipo/procesos, actualizar Google Business y alinear web, redes y atención.', 'Alta'],
    ['Plan de acción inicial', '1) Corregir el freno más visible. 2) Actualizar perfiles públicos. 3) Reunir evidencias de confianza. 4) Solicitar reseñas reales tras experiencias verificables. 5) Revisar avances cada mes.', 'Alta'],
  ];
}

function renderImprovementPlan(data) {
  if (!improvementGrid) return;
  const cards = [
    ['Google Business', `Actualizar categoría, servicios, fotos, horarios y respuestas. Prioridad alta si el problema detectado es: ${data.currentIssue || 'baja confianza visible'}.`],
    ['Web', `Explicar en portada qué ofrece ${data.brandName}, para quién y por qué confiar. Añadir contacto claro, pruebas sociales y objeciones frecuentes.`],
    ['Redes sociales', `Publicar señales reales de actividad: casos, procesos, equipo, resultados y contenido útil para ${data.audience}.`],
    ['Comunicación', `Alinear el mensaje “${data.brandMessage || 'profesionalidad y confianza'}” con textos simples, concretos y verificables.`],
    ['Reseñas reales', 'Pedir opiniones honestas a clientes reales después del servicio, evitando incentivos condicionados o textos artificiales.'],
    ['Primeros pasos', 'Prioridad alta: confianza básica. Prioridad media: coherencia visual. Prioridad baja: optimizaciones de conversión una vez corregidos los frenos principales.'],
  ];
  improvementGrid.replaceChildren();
  dashboardState.improvementPlan = cards.map(([title, text]) => ({ title, text }));
  cards.forEach(([title, text]) => {
    const article = document.createElement('article');
    const strong = document.createElement('strong');
    const paragraph = document.createElement('p');
    strong.textContent = title;
    paragraph.textContent = text;
    article.append(strong, paragraph);
    improvementGrid.appendChild(article);
  });
}

radiographyForm?.addEventListener('submit', (event) => {
  event.preventDefault();
  const formData = new FormData(radiographyForm);
  const data = {
    brandName: formValue(formData, 'brand_name', 'La marca'),
    sector: formValue(formData, 'sector', 'su sector'),
    offer: formValue(formData, 'offer', 'su oferta principal'),
    audience: formValue(formData, 'audience', 'su público objetivo'),
    brandMessage: formValue(formData, 'brand_message'),
    currentIssue: formValue(formData, 'current_issue'),
    customerFeedback: formValue(formData, 'customer_feedback'),
    channels: formValue(formData, 'channels'),
    location: formValue(formData, 'location'),
  };

  const insights = buildRadiographyInsights(data);
  dashboardState.radiography = data;
  dashboardState.radiographyInsights = insights.map(([title, text, priority]) => ({ title, text, priority }));
  radiographyBrandName.textContent = `Radiografía de ${data.brandName}`;
  radiographyInsights.replaceChildren();
  insights.forEach(([title, text, priority]) => {
    radiographyInsights.appendChild(insightCard(title, text, priority));
  });
  renderImprovementPlan(data);
  radiographyResult.hidden = false;
  radiographyResult.scrollIntoView({ behavior: 'smooth', block: 'start' });
  showToast('Radiografía reputacional generada en el panel.');
});

function delegationTemplate(index) {
  const wrapper = document.createElement('div');
  wrapper.className = 'fieldset-card delegation-card';
  wrapper.dataset.delegation = String(index);
  wrapper.innerHTML = `
    <div class="delegation-header">
      <h3>Delegación ${index + 1}</h3>
      <button class="secondary-button compact-button remove-delegation" type="button">Eliminar</button>
    </div>
    <label>Nombre de la delegación<input name="delegation_name_${index}" type="text" placeholder="Ej. Oficina norte" required></label>
    <label>Dirección<input name="delegation_address_${index}" type="text" required></label>
    <div class="grid-two">
      <label>Ciudad<input name="delegation_city_${index}" type="text" required></label>
      <label>Provincia<input name="delegation_province_${index}" type="text" required></label>
    </div>
    <div class="grid-two">
      <label>Código postal <span class="optional-label">opcional</span><input name="delegation_postal_${index}" type="text"></label>
      <label>País<input name="delegation_country_${index}" type="text" value="España" required></label>
    </div>
    <label>Tipo
      <select name="delegation_type_${index}" required>
        <option value="Sede">Sede</option>
        <option value="Delegación">Delegación</option>
        <option value="Oficina">Oficina</option>
        <option value="Punto de atención">Punto de atención</option>
        <option value="Punto de servicio">Punto de servicio</option>
      </select>
    </label>`;
  wrapper.querySelector('.remove-delegation').addEventListener('click', () => wrapper.remove());
  return wrapper;
}

addDelegationButton?.addEventListener('click', () => {
  const index = delegationsContainer.children.length;
  delegationsContainer.appendChild(delegationTemplate(index));
});

function collectDelegations(formData) {
  return [...delegationsContainer.querySelectorAll('.delegation-card')].map((card) => {
    const index = card.dataset.delegation;
    return {
      name: formValue(formData, `delegation_name_${index}`),
      address: formValue(formData, `delegation_address_${index}`),
      city: formValue(formData, `delegation_city_${index}`),
      province: formValue(formData, `delegation_province_${index}`),
      postal: formValue(formData, `delegation_postal_${index}`),
      country: formValue(formData, `delegation_country_${index}`, 'España'),
      type: formValue(formData, `delegation_type_${index}`, 'Delegación'),
      isMain: false,
    };
  });
}

const CITY_COORDINATES = {
  'a coruña': [43.3623, -8.4115], albacete: [38.9943, -1.8585], alicante: [38.3452, -0.4810], almeria: [36.8340, -2.4637],
  avila: [40.6565, -4.6818], badajoz: [38.8794, -6.9707], barcelona: [41.3874, 2.1686], bilbao: [43.2630, -2.9350],
  burgos: [42.3439, -3.6969], caceres: [39.4753, -6.3724], cadiz: [36.5271, -6.2886], castellon: [39.9864, -0.0513],
  'ciudad real': [38.9848, -3.9274], cordoba: [37.8882, -4.7794], cuenca: [40.0704, -2.1374], girona: [41.9794, 2.8214],
  granada: [37.1773, -3.5986], guadalajara: [40.6325, -3.1602], huelva: [37.2614, -6.9447], huesca: [42.1401, -0.4089],
  jaen: [37.7796, -3.7849], leon: [42.5987, -5.5671], lleida: [41.6176, 0.6200], logrono: [42.4627, -2.4449],
  madrid: [40.4168, -3.7038], malaga: [36.7213, -4.4214], murcia: [37.9922, -1.1307], oviedo: [43.3619, -5.8494],
  palencia: [42.0097, -4.5288], palma: [39.5696, 2.6502], pamplona: [42.8125, -1.6458], pontevedra: [42.4299, -8.6446],
  salamanca: [40.9701, -5.6635], 'san sebastian': [43.3183, -1.9812], santander: [43.4623, -3.8099], segovia: [40.9429, -4.1088],
  sevilla: [37.3891, -5.9845], soria: [41.7666, -2.4790], tarragona: [41.1189, 1.2445], teruel: [40.3457, -1.1065],
  toledo: [39.8628, -4.0273], valencia: [39.4699, -0.3763], valladolid: [41.6523, -4.7245], vigo: [42.2406, -8.7207],
  vitoria: [42.8467, -2.6716], zamora: [41.5035, -5.7446], zaragoza: [41.6488, -0.8891], ceuta: [35.8894, -5.3213], melilla: [35.2923, -2.9381],
};

function normalizeCity(value) {
  return String(value || '').trim().toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '');
}

function resolveCoordinates(location) {
  const key = normalizeCity(location.city || location.province);
  if (CITY_COORDINATES[key]) return { latLng: CITY_COORDINATES[key], approximated: true, fallback: false };
  return { latLng: [40.4168, -3.7038], approximated: true, fallback: true };
}

function ensureBusinessMap() {
  if (!businessMapElement || !window.L) return null;
  if (!businessMap) {
    businessMap = L.map(businessMapElement, { scrollWheelZoom: true }).setView([40.4168, -3.7038], 6);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 19,
      attribution: '&copy; OpenStreetMap contributors',
    }).addTo(businessMap);
    businessMarkersLayer = L.layerGroup().addTo(businessMap);
    window.setTimeout(() => businessMap.invalidateSize(), 120);
  }
  return businessMap;
}

function markerPopup(location) {
  const rows = [
    ['Nombre', location.name],
    ['Tipo', location.isMain ? 'Sede principal' : location.type],
    ['Dirección', location.address],
    ['Ciudad', location.city],
    ['Provincia', location.province],
    ['País', location.country],
  ];
  return `<div class="leaflet-popup-card"><strong>${escapeHtml(location.name)}</strong>${rows.map(([label, value]) => `<span><b>${label}:</b> ${escapeHtml(value || 'No indicado')}</span>`).join('')}</div>`;
}

function initializeEmptyBusinessMap() {
  const map = ensureBusinessMap();
  if (!map && businessMapElement) {
    businessMapElement.textContent = 'No se ha podido cargar Leaflet. Revisa la conexión y recarga el dashboard.';
  }
}

function renderCompanyMap(companyName, presenceType, locations) {
  coveragePill.textContent = `${companyName} · Cobertura ${presenceType}`;
  const map = ensureBusinessMap();
  const resolvedLocations = locations.map((location) => {
    const resolved = resolveCoordinates(location);
    return { ...location, coordinates: resolved.latLng, approximated: resolved.approximated, fallback: resolved.fallback };
  });
  dashboardState.map = { companyName, presenceType, locations: resolvedLocations };

  if (map && businessMarkersLayer) {
    businessMarkersLayer.clearLayers();
    const bounds = [];
    resolvedLocations.forEach((location) => {
      const marker = L.marker(location.coordinates, { title: `${location.name} · ${location.city}` })
        .bindPopup(markerPopup(location));
      marker.addTo(businessMarkersLayer);
      bounds.push(location.coordinates);
    });
    if (bounds.length > 1) map.fitBounds(bounds, { padding: [34, 34], maxZoom: 12 });
    if (bounds.length === 1) map.setView(bounds[0], 12);
    window.setTimeout(() => map.invalidateSize(), 120);
  }

  const fallbackLocations = resolvedLocations.filter((location) => location.fallback);
  mapWarning.hidden = fallbackLocations.length === 0;
  mapWarning.textContent = fallbackLocations.length
    ? `Ubicación aproximada: no se encontró ${fallbackLocations.map((location) => location.city || location.name).join(', ')}. Se ha usado Madrid como referencia por defecto.`
    : '';

  locationsList.replaceChildren();
  resolvedLocations.forEach((location) => {
    const item = document.createElement('article');
    item.className = `location-item ${location.isMain ? 'is-main' : ''}`;
    const name = document.createElement('strong');
    const type = document.createElement('span');
    const address = document.createElement('p');
    name.textContent = location.name;
    type.textContent = location.isMain ? 'Sede principal' : location.type;
    address.textContent = [location.address, location.city, location.province, location.postal, location.country].filter(Boolean).join(', ');
    item.append(name, type, address);
    locationsList.appendChild(item);
  });
}

companyMapForm?.addEventListener('submit', (event) => {
  event.preventDefault();
  const formData = new FormData(companyMapForm);
  const companyName = formValue(formData, 'company_name', 'Empresa');
  const presenceType = formValue(formData, 'presence_type', 'Local');
  const hq = {
    name: formValue(formData, 'hq_name', 'Sede principal'),
    address: formValue(formData, 'hq_address'),
    city: formValue(formData, 'hq_city'),
    province: formValue(formData, 'hq_province'),
    postal: formValue(formData, 'hq_postal'),
    country: formValue(formData, 'hq_country', 'España'),
    type: 'Sede',
    isMain: true,
  };
  renderCompanyMap(companyName, presenceType, [hq, ...collectDelegations(formData)]);
  showToast('Mapa empresarial actualizado.');
});

initializeEmptyBusinessMap();


function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>"]/g, (char) => ({
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
  }[char]));
}

function generatedDate() {
  return new Intl.DateTimeFormat('es-ES', { dateStyle: 'long', timeStyle: 'short' }).format(new Date());
}

function currentCompanyName() {
  return dashboardState.radiography?.brandName
    || dashboardState.map?.companyName
    || formValue(new FormData(form), 'business_name')
    || 'Empresa o marca no indicada';
}

function currentReviewFormData() {
  const formData = new FormData(form);
  return {
    businessName: formValue(formData, 'business_name'),
    reviewText: formValue(formData, 'review_text'),
    stars: formValue(formData, 'stars'),
    reviewDate: formValue(formData, 'review_date'),
    reviewerName: formValue(formData, 'reviewer_name'),
    additionalContext: formValue(formData, 'additional_context'),
  };
}

function currentMapFormData() {
  if (dashboardState.map) return dashboardState.map;
  const formData = new FormData(companyMapForm);
  const hq = {
    name: formValue(formData, 'hq_name', 'Sede principal'),
    address: formValue(formData, 'hq_address'),
    city: formValue(formData, 'hq_city'),
    province: formValue(formData, 'hq_province'),
    postal: formValue(formData, 'hq_postal'),
    country: formValue(formData, 'hq_country', 'España'),
    type: 'Sede',
    isMain: true,
  };
  return {
    companyName: formValue(formData, 'company_name', currentCompanyName()),
    presenceType: formValue(formData, 'presence_type', 'Local'),
    locations: [hq, ...collectDelegations(formData)].filter((location) => location.name || location.city || location.address),
  };
}

function currentImprovementPlan() {
  if (dashboardState.improvementPlan.length) return dashboardState.improvementPlan;
  return [...improvementGrid.querySelectorAll('article')].map((article) => ({
    title: article.querySelector('strong')?.textContent || 'Acción',
    text: article.querySelector('p')?.textContent || article.textContent.trim(),
  }));
}

function section(title, content) {
  return `<section class="report-section"><h2>${escapeHtml(title)}</h2>${content}</section>`;
}

function definitionList(items) {
  return `<div class="report-grid">${items.map(([label, value]) => `<article><strong>${escapeHtml(label)}</strong><p>${escapeHtml(value || 'No indicado')}</p></article>`).join('')}</div>`;
}

function bulletList(items) {
  const safeItems = items.length ? items : ['Sin datos generados todavía en este bloque.'];
  return `<ul>${safeItems.map((item) => `<li>${escapeHtml(item)}</li>`).join('')}</ul>`;
}

function reportShell(title, companyName, sections, isGeneral = false) {
  return `<!doctype html><html lang="es"><head><meta charset="utf-8"><title>${escapeHtml(title)}</title><style>
    :root { --blue: #00a3ff; --purple: #7d5cff; --ink: #101525; --muted: #5d6680; --line: #dce4f5; }
    * { box-sizing: border-box; } body { margin: 0; background: #eef3fb; color: var(--ink); font-family: Inter, Arial, sans-serif; }
    .report { max-width: 980px; margin: 0 auto; padding: 36px; } .cover, .report-section { background: #fff; border: 1px solid var(--line); border-radius: 24px; box-shadow: 0 18px 60px rgba(25, 39, 80, .10); margin-bottom: 18px; padding: 30px; }
    .cover { background: linear-gradient(135deg, rgba(0,163,255,.12), rgba(125,92,255,.12)), #fff; min-height: ${isGeneral ? '360px' : '220px'}; display: grid; align-content: center; }
    .eyebrow { color: var(--blue); font-weight: 900; letter-spacing: .13em; text-transform: uppercase; } h1 { font-size: 2.45rem; line-height: 1; margin: 8px 0 14px; } h2 { border-bottom: 2px solid rgba(0,163,255,.18); padding-bottom: 10px; } h3 { color: var(--purple); }
    .meta { color: var(--muted); line-height: 1.7; } .report-grid { display: grid; gap: 12px; grid-template-columns: repeat(2, minmax(0, 1fr)); } article { border: 1px solid var(--line); border-radius: 16px; padding: 14px; background: #f8faff; } article strong { color: var(--ink); } p, li { color: var(--muted); line-height: 1.65; } ul { padding-left: 20px; } .footer { color: var(--muted); font-size: .9rem; text-align: center; }
    @media print { body { background: #fff; } .report { padding: 0; } .cover, .report-section { box-shadow: none; break-inside: avoid; } .no-print { display: none; } }
  </style></head><body><main class="report"><button class="no-print" onclick="window.print()">Imprimir / Guardar como PDF</button><div class="cover"><p class="eyebrow">Wave Reputation Manager</p><h1>${escapeHtml(title)}</h1><p class="meta"><strong>${escapeHtml(companyName)}</strong><br>Fecha de generación: ${escapeHtml(generatedDate())}<br>Wave Music Business / Wave Music Tools</p></div>${sections.join('')}<p class="footer">Wave Reputation Manager · Wave Music Business / Wave Music Tools<br>Informe orientativo generado como apoyo estratégico, no garantiza retirada de reseñas ni sustituye asesoramiento legal.</p></main><script>window.addEventListener('load', () => setTimeout(() => window.print(), 250));<\/script></body></html>`;
}

function radiographyReportSections() {
  const data = dashboardState.radiography;
  const intro = data ? definitionList([
    ['Empresa o marca', data.brandName], ['Sector', data.sector], ['Oferta', data.offer], ['Público objetivo', data.audience],
    ['Mensaje de marca', data.brandMessage], ['Problema percibido', data.currentIssue], ['Canales', data.channels], ['Ubicación', data.location],
  ]) : '<p>No se ha generado todavía la radiografía. El informe se prepara con los datos actuales disponibles.</p>';
  const insights = dashboardState.radiographyInsights.map((item) => `<article><strong>${escapeHtml(item.title)}</strong><p>${escapeHtml(item.text)}</p></article>`).join('');
  return [section('Datos introducidos', intro), section('Resultado generado y recomendaciones', `<div class="report-grid">${insights || '<article><p>Genera la radiografía para completar este bloque.</p></article>'}</div>`)];
}

function reviewReportSections() {
  const input = currentReviewFormData();
  const result = dashboardState.review;
  return [
    section('Datos introducidos por el usuario', definitionList([
      ['Negocio', input.businessName], ['Reseña analizada', input.reviewText], ['Estrellas', input.stars], ['Fecha de reseña', input.reviewDate], ['Usuario visible', input.reviewerName], ['Contexto adicional', input.additionalContext],
    ])),
    section('Resultado generado', result ? definitionList([
      ['Viabilidad estimada', result.viability],
      ['Posibles incumplimientos', result.detected_motives.map((motive) => `${motive.category}: ${motive.reason}`).join('\n')],
      ['Reclamación generada', result.claim_text],
    ]) : '<p>Analiza una reseña para completar viabilidad, posibles incumplimientos y reclamación generada.</p>'),
    section('Advertencias y recomendaciones', bulletList(result?.recommended_evidence || ['Aporta evidencias objetivas antes de reclamar y revisa las políticas oficiales vigentes.'])),
  ];
}

function mapReportSections() {
  const data = currentMapFormData();
  const locations = data.locations || [];
  return [
    section('Datos del mapa empresarial', definitionList([['Empresa o marca', data.companyName], ['Cobertura', data.presenceType], ['Número de ubicaciones', String(locations.length)]])),
    section('Sede principal y delegaciones', `<div class="report-grid">${locations.map((location) => `<article><strong>${escapeHtml(location.isMain ? 'Sede principal' : location.type)} · ${escapeHtml(location.name)}</strong><p>${escapeHtml([location.address, location.city, location.province, location.postal, location.country].filter(Boolean).join(', ') || 'Ubicación no indicada')}</p></article>`).join('') || '<article><p>Añade ubicaciones para completar el listado.</p></article>'}</div>`),
    section('Recomendaciones', bulletList(['Mantener datos NAP coherentes en Google Business, web y redes.', 'Revisar reseñas y mensajes por sede cuando el negocio crezca.', 'Priorizar respuestas locales y evidencias específicas por ubicación.'])),
  ];
}

function improvementReportSections() {
  const plan = currentImprovementPlan();
  return [section('Plan de Mejora Reputacional', `<div class="report-grid">${plan.map((item) => `<article><strong>${escapeHtml(item.title)}</strong><p>${escapeHtml(item.text)}</p></article>`).join('')}</div>`), section('Errores a evitar', bulletList(['Prometer la retirada garantizada de reseñas.', 'Usar reseñas falsas o incentivos condicionados.', 'Responder de forma impulsiva o poco verificable.', 'Cambiar precios, planes o accesos al margen de la estrategia reputacional.']))];
}

function generalReportSections() {
  const company = currentCompanyName();
  const review = dashboardState.review;
  const mapData = currentMapFormData();
  return [
    section('Resumen ejecutivo', `<p>Informe general de reputación para ${escapeHtml(company)} con los datos actuales del dashboard: radiografía, reseña negativa, mapa empresarial y plan de mejora.</p>`),
    section('Radiografía Reputacional', radiographyReportSections().map((item) => item).join('')),
    section('Análisis de Reseñas Negativas', reviewReportSections().map((item) => item).join('')),
    section('Mapa de Empresa / Delegaciones', mapReportSections().map((item) => item).join('')),
    section('Plan de Mejora Reputacional', improvementReportSections().map((item) => item).join('')),
    section('Conclusión final', bulletList([`Diagnóstico general: ${dashboardState.radiography ? 'existen oportunidades claras para reforzar confianza, coherencia y prueba social.' : 'genera la radiografía para completar el diagnóstico reputacional.'}`, review ? `Reseñas: viabilidad estimada ${review.viability}; revisar evidencias antes de reclamar.` : 'Reseñas: analiza una reseña concreta si necesitas preparar reclamación.', `Cobertura: ${mapData.presenceType || 'pendiente'} con ${mapData.locations?.length || 0} ubicaciones registradas.`, 'Próximos pasos: priorizar señales de confianza, datos locales y respuestas profesionales.'])),
  ];
}

function openReport(type) {
  const company = currentCompanyName();
  const reports = {
    radiography: ['Informe de Radiografía Reputacional', radiographyReportSections()],
    review: ['Informe de Reseña Negativa', reviewReportSections()],
    map: ['Informe de Mapa Empresarial', mapReportSections()],
    improvement: ['Plan de Mejora Reputacional', improvementReportSections()],
    general: ['Informe General de Reputación', generalReportSections(), true],
  };
  const [title, sections, isGeneral] = reports[type] || reports.general;
  const reportWindow = window.open('', '_blank');
  if (!reportWindow) {
    showToast('Activa las ventanas emergentes para imprimir o guardar el informe como PDF.', true);
    return;
  }
  reportWindow.document.open();
  reportWindow.document.write(reportShell(title, company, sections, isGeneral));
  reportWindow.document.close();
}

reportButtons.forEach((reportButton) => {
  reportButton.addEventListener('click', () => openReport(reportButton.dataset.report));
});

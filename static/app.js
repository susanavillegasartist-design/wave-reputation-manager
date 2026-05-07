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
const companyMap = document.querySelector('#company-map');
const locationsList = document.querySelector('#locations-list');
const coveragePill = document.querySelector('#coverage-pill');
const improvementGrid = document.querySelector('#improvement-grid');

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

  radiographyBrandName.textContent = `Radiografía de ${data.brandName}`;
  radiographyInsights.replaceChildren();
  buildRadiographyInsights(data).forEach(([title, text, priority]) => {
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

function renderCompanyMap(companyName, presenceType, locations) {
  coveragePill.textContent = `${companyName} · Cobertura ${presenceType}`;
  companyMap.replaceChildren();
  const gridLines = document.createElement('div');
  gridLines.className = 'map-grid-lines';
  companyMap.appendChild(gridLines);
  locations.forEach((location, index) => {
    const marker = document.createElement('button');
    marker.type = 'button';
    marker.className = `map-marker ${location.isMain ? 'is-main' : ''}`;
    marker.style.left = `${18 + ((index * 23) % 68)}%`;
    marker.style.top = `${24 + ((index * 17) % 54)}%`;
    marker.textContent = location.isMain ? '★' : String(index);
    marker.setAttribute('aria-label', `${location.name}, ${location.city}`);
    marker.title = `${location.name} · ${location.city}`;
    companyMap.appendChild(marker);
  });

  locationsList.replaceChildren();
  locations.forEach((location) => {
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

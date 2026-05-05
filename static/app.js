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

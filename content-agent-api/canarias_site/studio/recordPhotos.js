// Contextual photo controls reuse the same protected library and upload API.
const imageKeys = new Set(['image_url', 'image_alt', 'image_credit', 'image_source_url']);
export {imageKeys};
const slug = value => String(value || '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase().replaceAll(' ', '-');
const publicImage = value => /^https?:\/\//i.test(value || '');

async function photoRequest(path) {
  const response = await fetch(path, {cache: 'no-store'});
  if (response.status === 401) window.top.location.assign('/login');
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new Error(typeof data.detail === 'string' ? data.detail : data.details?.join(' · ') || 'Nie udało się wczytać zdjęć.');
  }
  return response;
}

export async function preparePhoto(file) {
  if (!['image/jpeg', 'image/png', 'image/webp'].includes(file.type)) throw new Error('Wybierz zdjęcie JPEG, PNG lub WebP.');
  if (file.size > 20_000_000) throw new Error('Zdjęcie może mieć najwyżej 20 MB.');
  let bitmap;
  try { bitmap = await createImageBitmap(file); }
  catch { throw new Error('Nie można odczytać tego zdjęcia. Wybierz inny plik JPEG, PNG lub WebP.'); }
  const factor = Math.min(1, 1920 / Math.max(bitmap.width, bitmap.height));
  const canvas = document.createElement('canvas');
  canvas.width = Math.max(1, Math.round(bitmap.width * factor));
  canvas.height = Math.max(1, Math.round(bitmap.height * factor));
  const context = canvas.getContext('2d');
  context.fillStyle = '#fff';
  context.fillRect(0, 0, canvas.width, canvas.height);
  context.drawImage(bitmap, 0, 0, canvas.width, canvas.height);
  bitmap.close();
  const encoded = canvas.toDataURL('image/jpeg', 0.86).split(',')[1];
  if (encoded.length * 3 / 4 > 5_000_000) throw new Error('Zmniejsz zdjęcie przed wysłaniem: wynik może mieć najwyżej 5 MB.');
  return {filename: file.name.replace(/\.[^.]+$/, '') + '.jpg', data: encoded};
}

export function recordPhotoControls({item, node, field, api, payload, apply, message, openFullLibrary}) {
  const panel = node('section', undefined, {class: 'record-photo wide', 'aria-label': 'Zdjęcie wpisu'});
  panel.append(node('h3', 'Zdjęcie wpisu'));
  const figure = node('figure');
  const image = node('img', undefined, {alt: '', loading: 'lazy'});
  const caption = node('figcaption');
  const empty = node('p', 'Ten wpis nie ma jeszcze zdjęcia. Wgraj je z komputera lub wybierz z biblioteki.');
  figure.append(image, caption);
  panel.append(figure, empty);
  const feedback = node('p', '', {class: 'view-help', role: 'status', 'aria-live': 'polite'});
  function updatePreview() {
    const draft = payload();
    figure.hidden = !publicImage(draft.image_url);
    empty.hidden = !figure.hidden;
    if (!figure.hidden) {
      image.src = draft.image_url;
      image.alt = draft.image_alt || '';
      image.hidden = false;
      caption.textContent = draft.image_credit || '';
    } else image.removeAttribute('src');
    remove.disabled = figure.hidden;
  }
  image.onerror = () => { image.hidden = true; feedback.textContent = 'Nie udało się wyświetlić zdjęcia. Możesz wybrać inny plik; obecny adres pozostaje w szkicu.'; };
  const actions = node('div', undefined, {class: 'record-photo-actions'});
  const upload = node('input', undefined, {type: 'file', accept: 'image/jpeg,image/png,image/webp', hidden: ''});
  const uploadButton = node('button', 'Wgraj zdjęcie z komputera', {type: 'button'});
  uploadButton.onclick = () => upload.click();
  const choose = node('button', 'Wybierz zdjęcie z biblioteki', {type: 'button'});
  const remove = node('button', 'Usuń zdjęcie z wpisu', {type: 'button'});
  remove.onclick = () => { apply({url: '', alt: '', credit: '', source_url: ''}); message('Usunięto zdjęcie ze szkicu. Plik pozostaje w bibliotece. Zapisz i opublikuj wpis, aby zmienić stronę.'); };
  actions.append(uploadButton, choose, remove, upload);
  panel.append(actions, node('p', 'Wgranie dodaje publiczny plik do biblioteki strony i przypisuje go do tego szkicu. Wpis zmieni się dopiero po zapisaniu i publikacji.', {class: 'view-help'}));
  const metadata = node('div', undefined, {class: 'photo-metadata'});
  for (const key of ['image_alt', 'image_credit']) metadata.append(field(key, item.draft[key] || ''));
  const addresses = node('details');
  addresses.append(node('summary', 'Adres i źródło zdjęcia'));
  for (const key of ['image_url', 'image_source_url']) addresses.append(field(key, item.draft[key] || ''));
  const full = node('button', 'Otwórz pełną bibliotekę zdjęć', {type: 'button'});
  full.onclick = openFullLibrary;
  addresses.append(full);
  panel.append(metadata, addresses, feedback);
  for (const input of panel.querySelectorAll('[data-key]')) input.addEventListener('input', updatePreview);
  upload.onchange = async () => {
    const file = upload.files[0];
    if (!file) return;
    const identity = JSON.stringify(item.identity);
    // Hold the editor on this record until the upload finishes.
    const dialog = node('dialog', undefined, {class: 'photo-picker', 'aria-label': 'Wgrywanie zdjęcia'});
    dialog.append(node('p', 'Wgrywam zdjęcie do biblioteki strony…', {role: 'status'}));
    dialog.addEventListener('cancel', event => event.preventDefault());
    document.body.append(dialog); dialog.showModal();
    try {
      const prepared = await preparePhoto(file), draft = payload();
      const saved = await api('/media', {method: 'POST', body: JSON.stringify({island: item.identity.island, ...prepared, alt: draft.image_alt || '', credit: draft.image_credit || ''})});
      apply({...saved, source_url: ''}, identity);
      message('Zdjęcie dodano do szkicu i biblioteki strony. Teraz: Zapisz treść roboczą → Podgląd i zmiany → Opublikuj treść.');
    } catch (error) { feedback.textContent = error.message; message(error.message, true); }
    finally { dialog.close(); dialog.remove(); upload.value = ''; }
  };
  choose.onclick = () => openPicker({item, node, api, payload, apply, message});
  // Called after the controls have been attached to the form.
  return {panel, updatePreview};
}

async function openPicker({item, node, api, payload, apply, message}) {
  const identity = JSON.stringify(item.identity);
  const dialog = node('dialog', undefined, {class: 'photo-picker', 'aria-label': 'Wybierz zdjęcie do wpisu'});
  const heading = node('div', undefined, {class: 'photo-picker-heading'});
  const close = node('button', 'Zamknij wybór zdjęcia', {type: 'button'});
  close.onclick = () => dialog.close();
  heading.append(node('h2', 'Wybierz zdjęcie'), close);
  const searchLabel = node('label', 'Szukaj zdjęcia');
  const search = node('input', undefined, {type: 'search', placeholder: 'Nazwa, miejsce lub folder…'});
  searchLabel.append(search);
  const scopeLabel = node('label', 'Wyspa zdjęcia');
  const scope = node('select');
  scope.append(new Option('Wybrana wyspa', item.identity.island), new Option('Wszystkie wyspy', 'global'));
  scopeLabel.append(scope);
  const filters = node('div', undefined, {class: 'photo-picker-filters'});
  filters.append(searchLabel, scopeLabel);
  const status = node('p', 'Wczytuję bibliotekę…', {role: 'status'});
  const grid = node('div', undefined, {class: 'photo-picker-grid'});
  const selection = node('p', 'Wybierz miniaturę, a następnie kliknij „Użyj wybranego zdjęcia”.');
  const selectedPreview = node('img', undefined, {class: 'photo-picker-preview', alt: '', hidden: ''});
  const creditLabel = node('label', 'Autor / prawa wybranego zdjęcia');
  const credit = node('input', undefined, {maxlength: '200'}); creditLabel.append(credit);
  const use = node('button', 'Użyj wybranego zdjęcia', {type: 'button', disabled: ''});
  dialog.append(heading, filters, status, grid, selectedPreview, selection, creditLabel,
    node('p', 'Zdjęcie z Drive zostanie skopiowane do publicznej biblioteki strony dopiero po kliknięciu „Użyj”. Oryginał pozostaje na Drive.', {class: 'view-help'}), use);
  document.body.append(dialog); dialog.showModal();
  let rows = [], selected = null, selectionToken = 0, closed = false, reading = false;
  dialog.addEventListener('close', () => { closed = true; selectionToken++; dialog.remove(); });
  dialog.addEventListener('cancel', event => { if (reading) event.preventDefault(); });
  function render() {
    const q = search.value.toLocaleLowerCase();
    const matching = rows.filter(row => (scope.value === 'global' || slug(row.island) === scope.value) &&
      [row.name, row.folder, row.island].join(' ').toLocaleLowerCase().includes(q));
    grid.replaceChildren();
    for (const row of matching.slice(0, 100)) {
      const button = node('button', undefined, {type: 'button', class: 'photo-picker-item', 'aria-pressed': String(row === selected)});
      const thumb = node('img', undefined, {src: row.preview, alt: '', loading: 'lazy'});
      thumb.onerror = () => { thumb.hidden = true; };
      button.append(thumb, node('strong', row.name), node('small', row.site ? 'Biblioteka strony' : row.folder || 'Katalog źródłowy'));
      button.onclick = async () => {
        const token = ++selectionToken;
        selected = row; use.disabled = true; selection.textContent = 'Wczytuję opis zdjęcia…'; render();
        try {
          const detail = row.site ? row.value : await (await photoRequest('/api/v1/photos/' + encodeURIComponent(row.id))).json();
          if (closed || token !== selectionToken) return;
          selected = {...row, value: detail};
          credit.value = detail.credit || '';
          selectedPreview.src = row.preview; selectedPreview.hidden = false;
          selection.textContent = row.name;
          use.disabled = false;
        } catch (error) { if (!closed && token === selectionToken) selection.textContent = error.message; }
      };
      grid.append(button);
    }
    status.textContent = matching.length ? `${matching.length} zdjęć${matching.length > 100 ? ' · pokazano pierwsze 100; zawęź wyszukiwanie' : ''}.` : 'Brak zdjęć dla tych filtrów. Wybierz wszystkie wyspy, zmień wyszukiwanie lub wgraj zdjęcie z komputera.';
  }
  search.oninput = render; scope.onchange = render;
  use.onclick = async () => {
    if (!selected || use.disabled) return;
    reading = true; use.disabled = true; close.disabled = true;
    grid.querySelectorAll('button').forEach(button => { button.disabled = true; });
    search.disabled = true; scope.disabled = true;
    selection.textContent = 'Przygotowuję zdjęcie do wpisu…';
    try {
      const row = selected, value = row.value;
      let saved;
      if (row.site) saved = {...value, credit: credit.value, source_url: ''};
      else {
        const response = await photoRequest('/api/v1/photos/' + encodeURIComponent(row.id) + '/preview');
        const file = new File([await response.blob()], row.name, {type: response.headers.get('Content-Type')?.split(';')[0]});
        const prepared = await preparePhoto(file);
        const alt = value.alt_texts?.es || value.alt_texts?.pl || payload().image_alt || '';
        saved = await api('/media', {method: 'POST', body: JSON.stringify({island: item.identity.island, ...prepared, alt, credit: credit.value})});
        // Source links identify the private original; do not publish Drive IDs.
        saved.source_url = '';
      }
      apply(saved, identity);
      dialog.close();
      message('Zdjęcie wybrano do szkicu. Zapisz treść roboczą, sprawdź podgląd i opublikuj wpis.');
    } catch (error) { selection.textContent = error.message; use.disabled = false; }
    finally { reading = false; close.disabled = false; search.disabled = false; scope.disabled = false; grid.querySelectorAll('button').forEach(button => { button.disabled = false; }); }
  };
  const results = await Promise.allSettled([api('/media?' + new URLSearchParams({island: 'global'})), photoRequest('/api/v1/photos').then(response => response.json())]);
  if (closed) return;
  const notes = [];
  if (results[0].status === 'fulfilled') rows.push(...results[0].value.items.map(value => ({site: true, name: value.filename, island: value.island, preview: value.url, value})));
  else notes.push('Biblioteka strony: ' + results[0].reason.message);
  if (results[1].status === 'fulfilled') rows.push(...results[1].value.filter(value => value.status !== 'skipped').map(value => ({id: value.photo_id, name: value.current_name, island: value.island, folder: value.folder_path, preview: '/api/v1/photos/' + encodeURIComponent(value.photo_id) + '/preview'})));
  else notes.push('Katalog Drive / źródła: ' + results[1].reason.message);
  render();
  if (notes.length) dialog.append(node('p', notes.join(' '), {class: 'inspection-error'}));
}

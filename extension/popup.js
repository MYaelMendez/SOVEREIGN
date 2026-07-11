// >_æ| popup controller
// gold on void, terminal feel, sovereign

const input = document.getElementById('cmd');
const results = document.getElementById('results');
let selectedIdx = 0;
let currentItems = [];

// ── render ──
function render(items) {
  currentItems = items;
  selectedIdx = 0;

  if (items.length === 0) {
    results.innerHTML = `
      <div class="empty">
        <div class="big">>_æ|</div>
        <div>type a command. the URL is the command.</div>
      </div>`;
    return;
  }

  results.innerHTML = items.map((item, i) => `
    <div class="result-item ${i === 0 ? 'selected' : ''}" data-idx="${i}" data-url="${item.url}">
      <div class="icon">${item.icon}</div>
      <div class="text">
        <div class="title">${highlight(item.title, input.value)}</div>
        <div class="desc">${item.desc}</div>
      </div>
    </div>
  `).join('');

  // Click handlers
  results.querySelectorAll('.result-item').forEach(el => {
    el.addEventListener('click', () => {
      chrome.tabs.create({ url: el.dataset.url });
      window.close();
    });
    el.addEventListener('mouseenter', () => {
      selectItem(parseInt(el.dataset.idx));
    });
  });
}

// ── highlight matching text ──
function highlight(title, query) {
  if (!query) return title;
  const q = query.replace(/^>\s*/, '');
  const re = new RegExp(`(${q.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})`, 'gi');
  return title.replace(re, '<span class="match">$1</span>');
}

// ── selection ──
function selectItem(idx) {
  selectedIdx = Math.max(0, Math.min(idx, currentItems.length - 1));
  results.querySelectorAll('.result-item').forEach((el, i) => {
    el.classList.toggle('selected', i === selectedIdx);
  });
  // Scroll into view
  const sel = results.querySelector('.result-item.selected');
  if (sel) sel.scrollIntoView({ block: 'nearest' });
}

// ── execute ──
function execute() {
  if (currentItems.length === 0) return;
  const item = currentItems[selectedIdx];
  chrome.tabs.create({ url: item.url });
  window.close();
}

// ── events ──
input.addEventListener('input', () => {
  const items = searchCommands(input.value);
  render(items);
});

input.addEventListener('keydown', (e) => {
  switch (e.key) {
    case 'ArrowDown':
      e.preventDefault();
      selectItem(selectedIdx + 1);
      break;
    case 'ArrowUp':
      e.preventDefault();
      selectItem(selectedIdx - 1);
      break;
    case 'Enter':
      e.preventDefault();
      execute();
      break;
    case 'Escape':
      window.close();
      break;
  }
});

// ── boot ──
render(searchCommands(''));
input.focus();

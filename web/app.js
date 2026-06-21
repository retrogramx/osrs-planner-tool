const form = document.getElementById('search-form');
const statusEl = document.getElementById('status');
const profileEl = document.getElementById('profile');

const SKILL_ORDER = ['attack','hitpoints','mining','strength','agility','smithing','defence','herblore',
  'fishing','ranged','thieving','cooking','prayer','crafting','firemaking','magic','fletching','woodcutting',
  'runecraft','slayer','farming','construction','hunter'];

form.addEventListener('submit', async (e) => {
  e.preventDefault();
  const rsn = document.getElementById('rsn-search').value.trim();
  if (!rsn) return;
  statusEl.textContent = `Loading ${rsn}…`;
  profileEl.hidden = true;
  try {
    const res = await fetch(`/accounts/${encodeURIComponent(rsn)}/profile`);
    if (!res.ok) { statusEl.textContent = (await res.json()).detail || 'Something went wrong'; return; }
    render(await res.json());
    statusEl.textContent = '';
  } catch (err) { statusEl.textContent = 'Could not reach the server.'; }
});

function render(p) {
  const typeLabel = {normal:'Main', ironman:'Ironman', hardcore_ironman:'HCIM', ultimate_ironman:'UIM'}[p.account_type] || p.account_type;
  document.getElementById('identity').innerHTML =
    `<h2>${p.rsn}</h2><div class="meta">${typeLabel} · Total level ${p.total_level}</div>` +
    (p.clog_synced ? '' : '<div class="note">Collection log not synced</div>');

  const byName = Object.fromEntries(p.skills.map(s => [s.name.toLowerCase(), s]));
  document.getElementById('skills').innerHTML = SKILL_ORDER.map(slug => {
    const s = byName[slug];
    return `<div class="skill"><img src="/assets/sprites/skills/${slug}.png" alt="${slug}"/>` +
           `<span>${s ? s.level : '–'}</span></div>`;
  }).join('');

  const g = p.goals[0];
  const badge = {met:'✅ Done', blocked:'🔒 Blocked', unknown:'❓ Unknown'}[g.status] || g.status;
  const steps = g.steps.map(st => {
    const icon = {met:'✅', unmet:'🔒', unknown:'❓'}[st.status] || '•';
    return `<li class="step ${st.status}">${icon} ${st.label}</li>`;
  }).join('');
  document.getElementById('goal').innerHTML =
    `<h3>${g.label}</h3><div class="badge ${g.status}">${badge}</div>` +
    (steps ? `<ul class="steps">${steps}</ul>` : '<p>No remaining requirements.</p>');

  profileEl.hidden = false;
}

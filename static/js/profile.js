// profile.js — handles the profile form (crops, save)

function addCrop() {
  const input = document.getElementById('new-crop');
  const value = input.value.trim();
  if (!value) return;

  const container = document.getElementById('crop-tags');
  const tag = document.createElement('span');
  tag.className = 'crop-tag';
  tag.setAttribute('data-crop', value);
  tag.innerHTML = `${value}<button type="button" onclick="removeCrop(this)">&times;</button>`;
  container.appendChild(tag);

  input.value = '';
  input.focus();
}

function removeCrop(btn) {
  btn.closest('.crop-tag').remove();
}

document.getElementById('new-crop').addEventListener('keydown', (e) => {
  if (e.key === 'Enter') {
    e.preventDefault();
    addCrop();
  }
});

document.getElementById('save-profile-btn').addEventListener('click', async () => {
  const name = document.getElementById('p-name').value.trim();
  const location = document.getElementById('p-location').value.trim();
  const phone = document.getElementById('p-phone').value.trim();
  const crops = Array.from(document.querySelectorAll('.crop-tag')).map(el => el.getAttribute('data-crop'));

  try {
    await fetch('/api/profile', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, location, phone, crops })
    });

    const confirm = document.getElementById('save-confirm');
    confirm.classList.add('show');
    setTimeout(() => confirm.classList.remove('show'), 2200);
  } catch (err) {
    alert('Could not save profile. Please try again.');
  }
});

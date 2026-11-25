document.addEventListener('DOMContentLoaded', () => {
  const toast = document.getElementById('toast');
  let toastTimer;
  const showToast = (message) => {
    if (!toast) return;
    toast.textContent = message;
    toast.classList.add('show');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => toast.classList.remove('show'), 2800);
  };

  document.querySelectorAll('.js-add-cart').forEach((form) => {
    form.addEventListener('submit', async (event) => {
      event.preventDefault();
      const button = form.querySelector('button');
      if (button) button.disabled = true;
      try {
        const response = await fetch(form.action, { method: 'POST', body: new FormData(form) });
        const data = await response.json();
        if (!response.ok || !data.ok) throw new Error(data.error || 'Could not add to bag');
        const count = document.getElementById('cart-count');
        if (count) count.textContent = data.cart_count;
        showToast(data.message || 'Added to your bag.');
      } catch (error) {
        showToast(error.message);
      } finally {
        if (button) button.disabled = false;
      }
    });
  });

  document.querySelectorAll('.cart-qty').forEach((select) => {
    select.addEventListener('change', async () => {
      const body = new FormData();
      body.append('quantity', select.value);
      const response = await fetch(`/api/cart/${select.dataset.productId}/update`, { method: 'POST', body });
      if (response.ok) window.location.reload();
    });
  });

  const mobileMenu = document.querySelector('.mobile-menu');
  const nav = document.querySelector('.main-nav');
  if (mobileMenu && nav) {
    mobileMenu.addEventListener('click', () => nav.classList.toggle('mobile-open'));
  }
});

/* ============================================================
   Autoservice CRM — Custom JavaScript
   ============================================================ */

document.addEventListener('DOMContentLoaded', function () {

  // --- 1. Активний пункт навігації ---
  const currentPath = window.location.pathname;
  document.querySelectorAll('.navbar-nav .nav-link').forEach(function (link) {
    const href = link.getAttribute('href');
    if (href && href !== '#' && currentPath.startsWith(href)) {
      link.classList.add('active');
    }
  });

  // --- 2. Авто-приховування сповіщень (Django messages) ---
  const toasts = document.querySelectorAll('.toast');
  toasts.forEach(function (toastEl) {
    const bsToast = new bootstrap.Toast(toastEl, { delay: 5000 });
    bsToast.show();
  });


  // --- 3. Ролі-чіпси: перемикання активного класу ---
  document.querySelectorAll('.role-chip-input').forEach(function (input) {
    input.addEventListener('change', function () {
      const chip = this.closest('.role-chip');
      if (chip) {
        chip.classList.toggle('role-chip-active', this.checked);
      }
    });
  });

  // --- 4. Фільтрація телефону — лише цифри (data-phone-input) ---
  document.querySelectorAll('[data-phone-input]').forEach(function (input) {
    input.addEventListener('input', function () {
      this.value = this.value.replace(/\D/g, '');
    });
  });

  // --- 5. Авто-фокус на перше поле форми ---
  const form = document.querySelector('form:not(.no-autofocus)');
  if (form) {
    const firstInput = form.querySelector('input:not([type="hidden"]):not([type="checkbox"]):not([type="radio"]), select, textarea');
    if (firstInput && !firstInput.hasAttribute('autofocus')) {
      // Only focus if not already focused by browser
      if (!document.activeElement || document.activeElement === document.body) {
        firstInput.focus();
      }
    }
  }

});

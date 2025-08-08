  document.addEventListener('DOMContentLoaded', function () {
    const toastElements = document.querySelectorAll('.toast');
    toastElements.forEach(toastEl => {
      const toast = bootstrap.Toast.getOrCreateInstance(toastEl,{delay:10000});
      toast.show();
    });
  });

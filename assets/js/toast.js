document.addEventListener('DOMContentLoaded', function () {
  const toastLiveExample = document.getElementById('liveToast');
  if (toastLiveExample) { // On vérifie si l'élément existe avant de l'initialiser
    const toast = new bootstrap.Toast(toastLiveExample);
    toast.show();
  }
});

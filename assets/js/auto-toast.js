document.addEventListener('DOMContentLoaded', function () {
    const toastLiveExample = document.getElementById('autoToast');
    const toastBootstrap = bootstrap.Toast.getOrCreateInstance(toastLiveExample);
    toastBootstrap.show();
  });
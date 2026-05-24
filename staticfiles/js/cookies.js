document.addEventListener('DOMContentLoaded', function () {
    const modal = document.getElementById('cookie-policy-popup');
    const acceptCookies = document.getElementById('acceptCookies');
    const configureCookies = document.getElementById('configureCookies');
  
    if (!getCookie('cookieConsent')) {
      modal.classList.add('animate__fadeIn'); // Animación de entrada
      modal.style.display = 'block';
    } else {
      modal.style.display = 'none'; // Si ya hemos aceptado las cookies, no mostrar la ventana emergente
    }
  
    acceptCookies.addEventListener('click', function () {
      setCookie('cookieConsent', 'accepted', 365);
      modal.classList.remove('animate__fadeIn'); // Eliminar la animación de entrada
      modal.classList.add('animate__fadeOut'); // Animación de salida
      setTimeout(() => {
        modal.style.display = 'none';
      }, 500); // Tiempo para la animación de salida
    });
  
    configureCookies.addEventListener('click', function () {
      window.open('/configuracion-cookies', '_blank'); // Abrir una página interna con los enlaces
    });
  
    function setCookie(nombre, valor, dias) {
      const fecha = new Date();
      fecha.setTime(fecha.getTime() + (dias * 24 * 60 * 60 * 1000));
      const caduca = "; expires=" + fecha.toUTCString();
      document.cookie = nombre + "=" + valor + caduca + "; path=/; SameSite=Lax";
    }
  
    function getCookie(name) {
      const nameEQ = name + "=";
      const ca = document.cookie.split(';');
      for (let i = 0; i < ca.length; i++) {
        let c = ca[i].trim();
        if (c.indexOf(nameEQ) === 0) return c.substring(nameEQ.length, c.length);
      }
      return null;
    }
  });
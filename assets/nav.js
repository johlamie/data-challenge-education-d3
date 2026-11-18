/* Navigation sans rechargement pour les liens du rail et du menu mobile.

   Les liens de navigation sont des <a> (et non des dcc.Link) parce que Dash 4.5 refuse les
   attributs aria-* sur dcc.Link, et que l'item actif doit porter aria-current="page". Ce script
   rend le gain de dcc.Link sans en perdre l'accessibilité : il intercepte le clic gauche simple
   sur a[data-nav], pousse l'adresse dans l'historique et prévient dcc.Location (id="url"), qui
   déclenche le routeur ; le document n'est jamais rechargé et le bouton Précédent fonctionne.

   Ne touche jamais : « Se déconnecter » (pas de data-nav), un lien externe, un téléchargement,
   un clic avec Ctrl/Cmd/Maj/Alt, un clic milieu ou droit, une cible _blank.
   Sans JavaScript, chaque lien reste un <a href> ordinaire : la navigation fonctionne encore. */
(function () {
  function interceptable(e, a) {
    if (e.defaultPrevented || e.button !== 0) { return false; }
    if (e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) { return false; }
    if (!a || a.hasAttribute('download') || (a.target && a.target !== '_self')) { return false; }
    return a.origin === window.location.origin;
  }
  /* Le menu mobile est piloté par le callback Dash de #nav-bascule : on le referme en
     rejouant un clic sur le bouton, pour que l'état Dash et le DOM restent d'accord. */
  function fermerMenu() {
    var menu = document.getElementById('nav-menu');
    var bouton = document.getElementById('nav-bascule');
    if (menu && bouton && !menu.hidden) { bouton.click(); }
  }
  /* Échap referme le menu « Pages » et rend le focus au bouton qui l'a ouvert : un menu déplié
     au clavier doit pouvoir se refermer sans le parcourir en entier (même chemin que fermerMenu,
     donc l'état Dash reste d'accord avec le DOM). */
  document.addEventListener('keydown', function (e) {
    if (e.key !== 'Escape') { return; }
    var menu = document.getElementById('nav-menu');
    var bouton = document.getElementById('nav-bascule');
    if (!menu || !bouton || menu.hidden) { return; }
    fermerMenu();
    bouton.focus();
  });
  document.addEventListener('click', function (e) {
    var a = e.target && e.target.closest ? e.target.closest('a[data-nav]') : null;
    if (!a || !interceptable(e, a)) { return; }
    e.preventDefault();
    var cible = a.pathname + a.search + a.hash;
    if (cible !== window.location.pathname + window.location.search + window.location.hash) {
      window.history.pushState({}, '', cible);
      /* dcc.Location écoute « popstate » et l'événement interne qu'émet dcc.Link. */
      window.dispatchEvent(new CustomEvent('_dashprivate_pushstate'));
      window.dispatchEvent(new PopStateEvent('popstate'));
      window.scrollTo(0, 0);
    }
    fermerMenu();
  });
})();

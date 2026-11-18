/* Tri d'un `dash_table.DataTable` au clavier.

   Le composant ne rend qu'une icône de 8 × 15 px (`.column-header--sort`) sans `tabindex` ni
   rôle : le tri est donc hors d'atteinte au clavier, alors que la page dit « cliquez sur un
   en-tête pour trier ». La zone de clic est élargie à toute la cellule d'en-tête en CSS
   (`assets/style.css`, § tableau de données) ; ce script ajoute la partie qu'un style ne peut pas
   faire : rendre l'icône focalisable, lui donner un nom accessible et déclencher le tri sur
   Entrée ou Espace.

   Le tableau est redessiné par React à chaque tri, filtre ou mise à jour de données : un
   MutationObserver remarque les icônes neuves. Le sélecteur `:not([tabindex])` rend l'opération
   idempotente — l'observateur ne se réveille donc pas en boucle sur ses propres écritures.
   Sans JavaScript, le clic (CSS seul) continue de trier. */
(function () {
  var SEL = '.dash-table-container .column-header--sort';
  function nomColonne(icone) {
    var th = icone.closest ? icone.closest('th') : null;
    var nom = th ? th.querySelector('.column-header-name') : null;
    return nom ? nom.textContent.trim() : '';
  }
  function marquer() {
    var icones = document.querySelectorAll(SEL + ':not([tabindex])');
    for (var i = 0; i < icones.length; i++) {
      var ic = icones[i];
      ic.setAttribute('tabindex', '0');
      ic.setAttribute('role', 'button');
      ic.setAttribute('aria-label', 'Trier par ' + nomColonne(ic));
    }
  }
  document.addEventListener('keydown', function (e) {
    if (e.key !== 'Enter' && e.key !== ' ') { return; }
    var ic = e.target && e.target.closest ? e.target.closest(SEL) : null;
    if (!ic) { return; }
    e.preventDefault();
    ic.click();
  });
  if (window.MutationObserver) {
    new MutationObserver(marquer).observe(document.documentElement, { childList: true, subtree: true });
  }
  if (document.readyState !== 'loading') { marquer(); }
  else { document.addEventListener('DOMContentLoaded', marquer); }
})();

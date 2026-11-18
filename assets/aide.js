/* Infobulles d'aide ([data-aide] : icône .aide, cellule de chiffre .kpi-aide, libellé .terme-aide) : survol sur ordinateur, toucher sur mobile, clavier (Tab, Entrée, Échap).
   Une seule bulle, positionnée en fixed sur la page (jamais coupée par un bloc), texte inséré par textContent. */
(function () {
  var bulle = null, cible = null, epinglee = false;
  var META = /^(Unité|Sens|Source|Lecture) : ([\s\S]*)$/;
  function creer() {
    bulle = document.createElement('div');
    bulle.id = 'bulle-aide';
    bulle.className = 'bulle';
    bulle.setAttribute('role', 'tooltip');
    document.body.appendChild(bulle);
  }
  function remplir(t) {
    bulle.textContent = '';
    t.split('\n').forEach(function (l, i) {
      var d = document.createElement('div'), m = l.match(META);
      if (m) {
        var b = document.createElement('span');
        b.className = 'b-lib';
        b.textContent = m[1] + ' : ';
        d.appendChild(b);
        d.appendChild(document.createTextNode(m[2]));
        d.className = 'b-meta';
      } else {
        d.textContent = l;
        d.className = i === 0 ? 'b-def' : 'b-meta';
      }
      bulle.appendChild(d);
    });
  }
  function placer(el) {
    if (!document.body.contains(el)) { cacher(); return; }
    var r = el.getBoundingClientRect(), vw = window.innerWidth, vh = window.innerHeight;
    bulle.style.maxWidth = Math.min(330, vw - 16) + 'px';
    bulle.style.left = '0px'; bulle.style.top = '0px';
    var bw = bulle.offsetWidth, bh = bulle.offsetHeight;
    var x = Math.max(8, Math.min(r.left + r.width / 2 - bw / 2, vw - bw - 8));
    var y = r.bottom + 6;
    if (y + bh > vh - 8) { y = r.top - bh - 6; }
    if (y < 8) { y = Math.max(8, Math.min(r.bottom + 6, vh - bh - 8)); }
    bulle.style.left = Math.round(x) + 'px'; bulle.style.top = Math.round(y) + 'px';
  }
  function montrer(el, epingler) {
    if (!bulle) { creer(); }
    if (cible && cible !== el) { cible.removeAttribute('aria-describedby'); }
    remplir(el.getAttribute('data-aide') || '');
    bulle.classList.add('visible');
    cible = el; epinglee = !!epingler;
    /* aucun aria-expanded : un déclencheur d'infobulle n'ouvre pas de région (ARIA invalide sur
       un élément générique comme une cellule de chiffre) ; seul aria-describedby la rattache. */
    el.setAttribute('aria-describedby', 'bulle-aide');
    placer(el);
  }
  function cacher() {
    if (bulle) { bulle.classList.remove('visible'); }
    if (cible) { cible.removeAttribute('aria-describedby'); }
    cible = null; epinglee = false;
  }
  function aideDe(e) { return e.target && e.target.closest ? e.target.closest('[data-aide]') : null; }
  document.addEventListener('mouseover', function (e) { var el = aideDe(e); if (el && !epinglee) { montrer(el, false); } });
  document.addEventListener('mouseout', function (e) {
    var el = aideDe(e);
    if (el && !epinglee && el === cible && !(e.relatedTarget && el.contains(e.relatedTarget))) { cacher(); }
  });
  /* toucher ou clic : épingle la bulle ; second toucher sur la même icône ou ailleurs : la ferme */
  document.addEventListener('click', function (e) {
    var el = aideDe(e);
    if (el) {
      e.preventDefault(); e.stopPropagation();
      if (cible === el && epinglee) { cacher(); } else { montrer(el, true); }
      return;
    }
    if (epinglee) { cacher(); }
  }, true);
  document.addEventListener('focusin', function (e) { var el = aideDe(e); if (el && !epinglee) { montrer(el, false); } });
  document.addEventListener('focusout', function (e) { var el = aideDe(e); if (el && el === cible && !epinglee) { cacher(); } });
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') { cacher(); return; }
    var el = aideDe(e);
    if (el && (e.key === 'Enter' || e.key === ' ')) { e.preventDefault(); montrer(el, !epinglee || cible !== el); }
  });
  window.addEventListener('scroll', function () { if (cible) { placer(cible); } }, true);
  window.addEventListener('resize', function () { if (cible) { placer(cible); } });
})();

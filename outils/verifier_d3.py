"""Vérification de l'interface dans un vrai navigateur (Playwright, Chromium sans écran).

Usage : python outils/verifier_d3.py URL_BASE [--code-stdin] [--captures DOSSIER]
- sans session : / doit rediriger (302) vers /connexion et /_dash-layout répondre 401 ;
- pour chaque page et chaque taille (1366×768, 1440×900, 1920×1080, mobile 390×844) : erreurs JS, requêtes
  externes, débordement horizontal (page et éléments), hauteur des vues « un écran » sur ordinateur ;
  critère d'acceptation : la **Vue d'ensemble** ne défile pas **du tout** à 1366×768 et à
  1440×900 (`scrollHeight == clientHeight`) et ses 10 lignes de liste sont visibles sans défilement interne
  (`defilement_interdit`, `liste_qui_defile`) ; sur les autres vues « un écran », seul un dépassement
  supérieur à la tolérance (260 px à 1366 et 1440, 80 px à 1920) est signalé, la hauteur mesurée reste
  toujours rapportée ;
- infobulles : survol d'un chiffre clé et d'une icône « i » ; nombre d'icônes « i » par page ;
- interactions : changement de critère du classement, export CSV, scénario et normes, province d'implantation.
Avec --captures, enregistre les captures (fichiers 600). Le code d'accès est lu sur l'entrée standard, jamais
affiché ni écrit. Le résumé imprimé ne contient que des comptes et des noms de pages.
"""
import json
import os
import sys
import urllib.error
import urllib.request
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright

PAGES = [("vue_ensemble", "/"), ("classement", "/classement"), ("fiche", "/fiche"), ("besoins_2030", "/besoins-2030"),
         ("implantation", "/implantation"), ("a_propos", "/a-propos")]
PLEIN_ECRAN = {"vue_ensemble", "classement", "implantation"}
TAILLES = {"1366": {"width": 1366, "height": 768}, "1440": {"width": 1440, "height": 900},
           "1920": {"width": 1920, "height": 1080}, "mobile": {"width": 390, "height": 844}}
# défilement vertical accepté sur les vues « un écran » : au-delà, c'est un défaut
TOLERANCE_DEFILEMENT = {"1366": 260, "1440": 260, "1920": 80}
# Critère d'acceptation plus strict que la tolérance ci-dessus pour cette vue : la Vue
# d'ensemble ne défile **pas du tout** aux deux tailles de référence, et ses 10 lignes de liste
# sont visibles sans défilement interne.
SANS_DEFILEMENT = {("vue_ensemble", "1366"), ("vue_ensemble", "1440")}

JS_LISTE = """() => {
  const e = document.querySelector('#page .zone-liste');
  return e ? [e.scrollHeight, e.clientHeight, e.querySelectorAll('tbody tr').length] : null;
}"""

JS_DEBORDEMENTS = """() => {
  const vw = document.documentElement.clientWidth, out = [];
  if (document.documentElement.scrollWidth > vw + 1) out.push('page:' + document.documentElement.scrollWidth);
  for (const el of document.querySelectorAll('#page *')) {
    const r = el.getBoundingClientRect();
    if (r.width === 0 || r.height === 0) continue;
    const st = getComputedStyle(el);
    if (st.visibility === 'hidden' || st.position === 'fixed') continue;
    if (el.closest('.dash-spreadsheet-container, .js-plotly-plot, .table-responsive, .zone-top10, .zone-liste, .table-defile, .dash-dropdown-content, .dash-dropdown-wrapper')) continue;
    if (r.right > vw + 1 || r.left < -1) out.push((el.className && el.className.toString().slice(0, 40)) || el.tagName);
  }
  for (const el of document.querySelectorAll('#page .carte-bloc, #page .panneau, #page .kpi, #page .filtre')) {
    if (el.scrollWidth > el.clientWidth + 2 && getComputedStyle(el).overflowX !== 'auto') out.push('interne:' + (el.className || '').toString().slice(0, 40));
  }
  return Array.from(new Set(out)).slice(0, 12);
}"""


def attendre(page, timeout=40000):
    page.wait_for_load_state("networkidle", timeout=timeout)
    page.wait_for_function("""() => document.querySelector('#page') && document.querySelector('#page').children.length > 0
        && !document.querySelector('[data-dash-is-loading="true"]')""", timeout=timeout)
    page.wait_for_timeout(900)


def choisir(page, id_, texte):
    page.click(f"#{id_}")
    page.wait_for_timeout(300)
    page.get_by_role("option", name=texte).first.click()
    page.wait_for_timeout(1800)


def http(url):
    req = urllib.request.Request(url)

    class SansRedir(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *a, **k):
            return None
    try:
        r = urllib.request.build_opener(SansRedir).open(req, timeout=20)
        return r.status, r.headers.get("Location")
    except urllib.error.HTTPError as e:
        return e.code, e.headers.get("Location")


def main():
    base = sys.argv[1].rstrip("/")
    code = sys.stdin.readline().strip() if "--code-stdin" in sys.argv else None
    dossier = sys.argv[sys.argv.index("--captures") + 1] if "--captures" in sys.argv else None
    if dossier:
        os.makedirs(dossier, mode=0o700, exist_ok=True)
    hote = urlparse(base).netloc
    res = {"sans_session": {}, "pages": [], "erreurs_js": [], "console_erreurs": [], "requetes_externes": [],
           "debordements": {}, "defilement": {}, "defilement_excessif": {}, "defilement_interdit": {},
           "liste_qui_defile": {}, "hauteurs": {}, "icones_aide": {}, "interactions": {}}
    if code:
        res["sans_session"] = {"/": http(base + "/"), "/_dash-layout": http(base + "/_dash-layout")[0],
                               "/sante": http(base + "/sante")[0]}
    with sync_playwright() as p:
        nav = p.chromium.launch(headless=True, args=["--no-sandbox"])
        for taille, vp in TAILLES.items():
            ctx = nav.new_context(viewport=vp, locale="fr-FR", accept_downloads=True,
                                  device_scale_factor=2 if taille == "mobile" else 1, has_touch=taille == "mobile")
            page = ctx.new_page()
            page.on("pageerror", lambda e: res["erreurs_js"].append(str(e)[:200]))
            page.on("console", lambda m: m.type == "error" and res["console_erreurs"].append(m.text[:200]))
            page.on("request", lambda r: urlparse(r.url).netloc not in (hote, "") and not r.url.startswith(("data:", "blob:"))
                    and res["requetes_externes"].append(r.url[:120]))
            if code:
                page.goto(base + "/")
                page.fill("#code", code)
                page.click("button[type=submit]")
                page.wait_for_load_state("networkidle")
            for nom, chemin in PAGES:
                r = page.goto(base + chemin)
                attendre(page)
                cle = f"{nom}@{taille}"
                deb = page.evaluate(JS_DEBORDEMENTS)
                if deb:
                    res["debordements"][cle] = deb
                if taille != "mobile" and nom in PLEIN_ECRAN:
                    h = page.evaluate("() => [document.documentElement.scrollHeight,"
                                      " document.documentElement.clientHeight, window.innerHeight]")
                    res["hauteurs"][cle] = h
                    if h[0] > h[1] + 1:
                        res["defilement"][cle] = h
                    if h[0] > h[1] + TOLERANCE_DEFILEMENT[taille]:
                        res["defilement_excessif"][cle] = h
                    if (nom, taille) in SANS_DEFILEMENT:
                        # critère strict : scrollHeight == clientHeight, au pixel près
                        if h[0] > h[1]:
                            res["defilement_interdit"][cle] = h
                        liste = page.evaluate(JS_LISTE)
                        if liste and liste[0] > liste[1] + 1:
                            res["liste_qui_defile"][cle] = liste
                if taille == "1366":
                    res["icones_aide"][nom] = page.locator("#page .aide").count()
                res["pages"].append({"page": nom, "taille": taille, "http": r.status if r else None,
                                     "graphiques": page.locator(".js-plotly-plot").count()})
                if dossier and taille in ("1366", "1440", "1920"):
                    chemin_png = os.path.join(dossier, f"d3_{nom}_{taille}.png")
                    page.screenshot(path=chemin_png, full_page=nom not in PLEIN_ECRAN)
                    os.chmod(chemin_png, 0o600)
                if dossier and taille == "mobile" and nom in ("vue_ensemble", "fiche"):
                    chemin_png = os.path.join(dossier, f"d3_{nom}_mobile.png")
                    page.screenshot(path=chemin_png, full_page=False)
                    os.chmod(chemin_png, 0o600)
            if taille == "1366":
                it = res["interactions"]
                page.goto(base + "/")
                attendre(page)
                page.hover(".kpi-aide >> nth=0")
                page.wait_for_timeout(300)
                it["infobulle_kpi"] = page.locator("#bulle-aide.visible").count() == 1
                page.mouse.move(5, 5)
                page.hover("#page .aide >> nth=0")
                page.wait_for_timeout(300)
                it["infobulle_icone"] = page.locator("#bulle-aide.visible").count() == 1
                page.goto(base + "/classement")
                attendre(page)
                choisir(page, "cla-mesure", "Enseignants manquants")
                it["classement_critere"] = page.locator("#cla-titre-carte").inner_text()
                with page.expect_download() as dl:
                    page.click("#cla-export-btn")
                it["export_csv_lignes"] = len(open(dl.value.path(), encoding="utf-8-sig").read().strip().splitlines()) - 1
                page.goto(base + "/besoins-2030")
                attendre(page)
                avant = page.locator("#bes-kpis .kpi-val >> nth=1").inner_text()
                choisir(page, "bes-nc", "60")
                it["besoins_norme_change"] = page.locator("#bes-kpis .kpi-val >> nth=1").inner_text() != avant
                page.goto(base + "/implantation")
                attendre(page)
                choisir(page, "imp-sites", "Sites fiables seulement")
                it["implantation_filtre_lignes"] = page.locator("#imp-table tbody tr").count()
                page.goto(base + "/fiche")
                attendre(page)
                it["fiche_carte_bleue"] = page.evaluate(
                    "() => Array.from(document.querySelectorAll('#fic-carte path.js-fill')).filter(p => "
                    "(p.style.fill || '').includes('168, 195, 226')).length")
            ctx.close()
        nav.close()
    res["resume"] = {"pages_testees": len(res["pages"]), "erreurs_js": len(res["erreurs_js"]),
                     "console_erreurs": len(res["console_erreurs"]), "requetes_externes": len(res["requetes_externes"]),
                     "pages_avec_debordement": len(res["debordements"]), "vues_qui_defilent": len(res["defilement"]),
                     "defilement_excessif": len(res["defilement_excessif"]),
                     "defilement_interdit": len(res["defilement_interdit"]),
                     "liste_qui_defile": len(res["liste_qui_defile"]),
                     "icones_aide_site": sum(1 for v in res["icones_aide"].values() for _ in range(v))}
    print(json.dumps(res, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()

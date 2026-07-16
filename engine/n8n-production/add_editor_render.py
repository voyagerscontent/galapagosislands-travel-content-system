#!/usr/bin/env python3
"""WFP6 output chain: editor Doc + HTML + JSON-LD into '07 Polished for Editor', then notify.

Chain:
  Output OK? --true--> Render editor copy --> Export editor Doc --> Export HTML
                   --> Export JSON-LD --> Notify webmasters --> Advance to Auditor Review

Why the editor Doc is built by hand and not the stock Drive node:
WFP6's artifact is production HTML. The Drive node's 'createFromText' uploads as text/plain,
so converting to a Doc yields a page of visible HTML source — useless to a human editor.
Drive DOES render HTML into real Doc formatting, but only if the upload declares text/html,
and the node cannot set the source mime type. So we build a multipart/related upload by hand.

The Doc is a reader-facing RENDER for the editor, plus instructions. It is not the deliverable:
- the production HTML ships as a real .html file, and
- the JSON-LD ships as a real .json file,
both alongside it in the same folder, because the webmaster needs the code, not a screenshot.

Instruction language is SPANISH (the webmasters' native language) and every instruction is
highlighted GREEN so it cannot be mistaken for copy. The rule stated at the top of the Doc is:
delete everything green before publishing.

WFP6 returns three keys — polished_html, conversion_review, section_guide — so 'Validate Output'
is patched here to carry all three.
"""
import json, urllib.request, os

N8N = "https://voyagerscontent.app.n8n.cloud"
PUB = os.environ["N8N_PUB"]
WID = "U0MrpTN3hv4RfNMI"
FN = "WFP6_polish.json"
ADV = "Advance to Auditor Review"
FOLDER = "1jf8kwaFmFHpYTgmLYSVSMU4yq-YBM5bH"   # ContentEngine / 07 Polished for Editor
BOUNDARY = "n8nEditorCopyBoundary7f3a91"
DRIVE_CRED = {"id": "BXOLO4YcNnpHp3SD", "name": "Google Drive account"}
SMTP_CRED = {"id": "BMPXVO3yLf7Zifhv", "name": "SMTP account"}
FROM_EMAIL = "businessops@latintrails.com"          # matches the proven WF8 Notify sender
TO_EMAIL = "webmaster@latintrails.com"
CC_EMAIL = "webmaster@voyagers.travel,marketing@voyagers.travel"

V = "$('Validate Output').item.json"

# ── Validate Output: carry all three WFP6 keys ───────────────────────────────
VALIDATE_TAIL = (
    "try{ const p=JSON.parse(raw); const a=p['polished_html'];"
    " if(typeof a==='string'&&a.length>40){out.artifact=a;out.ok=true;} else out.error='Missing/short polished_html';"
    " out.conversion=(typeof p['conversion_review']==='string')?p['conversion_review']:'';"
    " try{ out.sections=JSON.stringify(p['section_guide']||[]); }catch(e){ out.sections='[]'; }"
    "}catch(e){out.error='Unparseable LLM output: '+e.message;}\n"
)

RENDER_JS = r"""
const V   = $('Validate Output').first().json;
const rec = $('Re-check and Claim (guarded)').first().json;
const html = String(V.artifact || '');
const conversion = String(V.conversion || '');
let sections = [];
try { sections = JSON.parse(V.sections || '[]'); } catch(e) { sections = []; }

const pick = (re) => { const m = html.match(re); return m ? m[1].trim() : ''; };
const dec  = (s) => String(s).replace(/&lt;/g,'<').replace(/&gt;/g,'>')
                             .replace(/&quot;/g,'"').replace(/&#39;/g,"'").replace(/&amp;/g,'&');
const esc  = (s) => String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');

const title = dec(pick(/<title[^>]*>([\s\S]*?)<\/title>/i));
const desc  = dec(pick(/<meta\s+name=["']description["']\s+content=["']([\s\S]*?)["']/i));
const canon = dec(pick(/<link\s+rel=["']canonical["']\s+href=["']([\s\S]*?)["']/i));
const name  = rec['Name'] || rec['Meta Title'] || 'Untitled';
const ptype = rec['Page Type'] || '';
const brief = rec['Topic / Brief'] || '';

// GREEN = internal instruction, never published. Drive maps background-color to Doc highlight.
const G = (s) => '<span style="background-color:#00FF00">' + s + '</span>';
const Gp = (s) => '<p>' + G(s) + '</p>';

// body only — the editor reviews prose, not <head>, the JSON-LD blob or CSS
let body = pick(/<body[^>]*>([\s\S]*?)<\/body>/i) || html;
body = body.replace(/<script[\s\S]*?<\/script>/gi,'').replace(/<style[\s\S]*?<\/style>/gi,'');

// Anchor each heading with its [H1]/[H2]/[H3] marker + Spanish purpose, so the webmaster
// can see exactly where each level goes and what the section is for.
const purposeOf = {};
for (const s of sections) {
  if (s && s.heading) purposeOf[String(s.heading).trim().toLowerCase()] = {
    lvl: s.level || 2, purpose: s.purpose_es || ''
  };
}
body = body.replace(/<h([123])([^>]*)>([\s\S]*?)<\/h\1>/gi, (m, lvl, attrs, inner) => {
  const plain = dec(inner.replace(/<[^>]+>/g,'')).trim();
  const hit = purposeOf[plain.toLowerCase()];
  const purpose = hit && hit.purpose ? hit.purpose : '';
  const tag = G('[H' + lvl + ']') + (purpose ? ' ' + G('Propósito: ' + esc(purpose)) : '');
  return '<p>' + tag + '</p><h' + lvl + attrs + '>' + inner + '</h' + lvl + '>';
});

const flag = (n, lo, hi) => (n >= lo && n <= hi) ? 'OK' : 'FUERA DE RANGO (' + lo + '-' + hi + ')';

let head = '';
head += '<h1>' + esc(name) + ' — Copia para el editor</h1>';
head += Gp('Estimada/o webmaster,');
head += Gp('Favor publicar esta página en el URL: ' + esc(canon || '(ver Airtable)'));
head += Gp('IMPORTANTE — TODO EL TEXTO RESALTADO EN VERDE ES UNA INSTRUCCIÓN INTERNA Y NO SE '
         + 'PUBLICA. Elimine todo el texto verde antes de publicar. El texto sin resaltar es el '
         + 'contenido de la página.');
head += Gp('Los marcadores [H1], [H2] y [H3] indican exactamente qué nivel de encabezado usar en '
         + 'el CMS. El encabezado va inmediatamente debajo de su marcador. Debe haber un solo [H1].');
head += Gp('Tipo de página: ' + esc(ptype) + '. El HTML de producción y el schema JSON-LD están en '
         + 'esta misma carpeta como archivos .html y .json — úselos para el CMS.');
head += Gp('Propósito de esta página: ' + esc(brief));

head += '<h2>' + G('Metadatos — revisar antes de publicar') + '</h2>';
head += '<table border="1" cellpadding="6" cellspacing="0"><tbody>'
      + '<tr><td>' + G('Meta title') + '<br>' + title.length + ' ' + G('caracteres — ' + flag(title.length,50,60)) + '</td><td>' + esc(title) + '</td></tr>'
      + '<tr><td>' + G('Meta description') + '<br>' + desc.length + ' ' + G('caracteres — ' + flag(desc.length,140,160)) + '</td><td>' + esc(desc) + '</td></tr>'
      + '<tr><td>' + G('URL canónico') + '</td><td>' + esc(canon) + '</td></tr>'
      + '</tbody></table>';

if (conversion) {
  head += '<h2>' + G('Revisión del experto en conversión') + '</h2>';
  head += Gp('Instrucciones de conversión para el webmaster. NO son texto de la página. El embudo '
           + 'debe ser SUTIL: este es un sitio editorial independiente y un embudo visible destruye '
           + 'la confianza de la que depende.');
  head += '<pre>' + G(esc(conversion)) + '</pre>';
}

head += '<h2>' + G('La página') + '</h2>';
head += Gp('Todo lo que sigue sin resaltar es el contenido a publicar.');
head += '<hr>';

const doc = '<html><head><meta charset="utf-8"></head><body>' + head + body + '</body></html>';

const B = '""" + BOUNDARY + r"""';
const meta = JSON.stringify({ name: name + ' — Editor Copy',
                              parents: ['""" + FOLDER + r"""'],
                              mimeType: 'application/vnd.google-apps.document' });
const multipart =
  '--' + B + '\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n' + meta + '\r\n' +
  '--' + B + '\r\nContent-Type: text/html; charset=UTF-8\r\n\r\n' + doc + '\r\n' +
  '--' + B + '--';

// JSON-LD extracted for the webmaster as its own file
const ld = [];
const re = /<script[^>]*application\/ld\+json[^>]*>([\s\S]*?)<\/script>/gi;
let m; while ((m = re.exec(html)) !== null) ld.push(m[1].trim());

return [{ json: { multipart, docName: name, jsonld: ld.join('\n\n') || '{}', pageHtml: html } }];
"""


def drive_text(name_expr, content_expr, mime_label):
    return {
        "type": "n8n-nodes-base.googleDrive", "typeVersion": 3,
        "onError": "continueRegularOutput",
        "parameters": {
            "resource": "file", "operation": "createFromText",
            "content": content_expr, "name": name_expr,
            "driveId": {"__rl": True, "mode": "list", "value": "My Drive"},
            "folderId": {"__rl": True, "mode": "id", "value": FOLDER},
            "options": {"convertToGoogleDocument": False},
        },
        "credentials": {"googleDriveOAuth2Api": DRIVE_CRED},
    }


def put(wid, wf):
    body = {"name": wf["name"], "nodes": wf["nodes"], "connections": wf["connections"],
            "settings": wf.get("settings", {"executionOrder": "v1"})}
    r = urllib.request.Request(N8N + "/api/v1/workflows/" + wid, data=json.dumps(body).encode(),
                               headers={"X-N8N-API-KEY": PUB, "Content-Type": "application/json"}, method="PUT")
    try:
        return "ok" if json.load(urllib.request.urlopen(r)).get("id") else "??"
    except urllib.error.HTTPError as e:
        return "ERR %d %s" % (e.code, e.read().decode()[:200])


p = os.path.join(os.path.dirname(__file__), FN)
wf = json.load(open(p))

NEW = ["Render editor copy", "Export editor Doc", "Export HTML", "Export JSON-LD",
       "Notify webmasters", "Export to Drive"]
wf["nodes"] = [n for n in wf["nodes"] if n["name"] not in NEW]
# drop their connection entries too — n8n rejects a source that no longer exists
for k in NEW:
    wf["connections"].pop(k, None)

# patch the validator to carry conversion_review + section_guide
for n in wf["nodes"]:
    if n["name"] == "Validate Output":
        js = n["parameters"]["jsCode"]
        head_js = js.split("try{ const p=JSON.parse(raw);")[0]
        tail_js = js.split("\n", -1)
        rest = js[js.index("if(!out.ok && nodeErr)"):] if "if(!out.ok && nodeErr)" in js else "return [{json: out}];"
        n["parameters"]["jsCode"] = (
            head_js.replace("out={recordId:rid,baseId:bid,tableId:tid,ok:false,error:'',artifact:''}",
                            "out={recordId:rid,baseId:bid,tableId:tid,ok:false,error:'',artifact:'',conversion:'',sections:'[]'}")
            + VALIDATE_TAIL + rest)

anchor = next(n for n in wf["nodes"] if n["name"] == ADV)
x, y = anchor["position"]

nodes = [
    ("Render editor copy", {"type": "n8n-nodes-base.code", "typeVersion": 2,
                            "parameters": {"jsCode": RENDER_JS}}),
    ("Export editor Doc", {"type": "n8n-nodes-base.httpRequest", "typeVersion": 4.2,
                           "onError": "continueRegularOutput",
                           "parameters": {
                               "method": "POST",
                               "url": "https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart&supportsAllDrives=true",
                               "authentication": "predefinedCredentialType",
                               "nodeCredentialType": "googleDriveOAuth2Api",
                               "sendBody": True, "contentType": "raw",
                               "rawContentType": "multipart/related; boundary=" + BOUNDARY,
                               "body": "={{ $('Render editor copy').item.json.multipart }}",
                               "options": {}},
                           "credentials": {"googleDriveOAuth2Api": DRIVE_CRED}}),
    ("Export HTML", drive_text("={{ $('Render editor copy').item.json.docName + '.html' }}",
                               "={{ $('Render editor copy').item.json.pageHtml }}", "html")),
    ("Export JSON-LD", drive_text("={{ $('Render editor copy').item.json.docName + '.schema.json' }}",
                                  "={{ $('Render editor copy').item.json.jsonld }}", "json")),
    ("Notify webmasters", {"type": "n8n-nodes-base.emailSend", "typeVersion": 2.1,
                           "onError": "continueRegularOutput",
                           "parameters": {
                               "fromEmail": FROM_EMAIL, "toEmail": TO_EMAIL,
                               "subject": "={{ 'Lista para CMS: ' + $('Render editor copy').item.json.docName }}",
                               "emailFormat": "text",
                               "text": "={{ 'Hola,\\n\\nLa pagina \"' + $('Render editor copy').item.json.docName + "
                                       "'\" paso todas las etapas automaticas y esta lista para publicar en el CMS.\\n\\n"
                                       "En la carpeta 07 Polished for Editor encontrara tres archivos:\\n"
                                       "1. \"... — Editor Copy\" (Google Doc) — el contenido con las instrucciones. "
                                       "TODO lo resaltado en VERDE es instruccion interna y NO se publica.\\n"
                                       "2. \"....html\" — el HTML de produccion para el CMS.\\n"
                                       "3. \"....schema.json\" — el schema JSON-LD.\\n\\n"
                                       "Doc: ' + ($('Export editor Doc').item.json.id ? 'https://docs.google.com/document/d/' + "
                                       "$('Export editor Doc').item.json.id + '/edit' : '(ver carpeta)') + '\\n"
                                       "Carpeta: https://drive.google.com/drive/folders/" + FOLDER + "\\n\\n"
                                       "Los marcadores [H1], [H2] y [H3] indican el nivel de encabezado a usar.\\n"
                                       "La revision del experto en conversion esta en el Doc e indica donde colocar "
                                       "los llamados a la accion.\\n\\nGracias.' }}",
                               "options": {"ccEmail": CC_EMAIL}},
                           "credentials": {"smtp": SMTP_CRED}}),
]
for i, (nm, cfg) in enumerate(nodes):
    cfg["name"] = nm
    cfg["position"] = [x - 900 + i * 180, y - 200]
    wf["nodes"].append(cfg)

# Advance reads from Validate explicitly ($json is now the email node's output)
a = anchor["parameters"]
a["base"]["value"] = "={{ %s.baseId }}" % V
a["table"]["value"] = "={{ %s.tableId }}" % V
col = a["columns"]["value"]
col["id"] = "={{ %s.recordId }}" % V
col["Polished Content"] = "={{ %s.artifact }}" % V
col["Conversion Review"] = "={{ %s.conversion }}" % V
col["Polished Link"] = ("={{ $('Export editor Doc').item.json.id ? 'https://docs.google.com/document/d/' "
                        "+ $('Export editor Doc').item.json.id + '/edit' : 'airtable://Polished Content' }}")

chain = ["Render editor copy", "Export editor Doc", "Export HTML", "Export JSON-LD", "Notify webmasters", ADV]
wf["connections"]["Output OK?"]["main"][0] = [{"node": chain[0], "type": "main", "index": 0}]
for src, dst in zip(chain, chain[1:]):
    wf["connections"][src] = {"main": [[{"node": dst, "type": "main", "index": 0}]]}

open(p, "w").write(json.dumps(wf, indent=2))
print("%s -> editor Doc + .html + .schema.json in '07 Polished for Editor' + ES email  %s"
      % (FN, put(WID, wf)))

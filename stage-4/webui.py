"""Server-rendered browser screens for the dossier product.

All pages are rendered here as HTML with a shared visual system.  Interactive
behaviour (research, refresh, reload, and the read while a dossier is building)
lives in one small script embedded in the layout.
"""

from __future__ import annotations

import html
import json
from datetime import datetime, timezone

FIELD_ORDER = (
    "legal_name",
    "hq_city",
    "ceo",
    "founded_year",
    "headcount_range",
    "funding_total",
)

FIELD_LABELS = {
    "legal_name": "Legal name",
    "hq_city": "Headquarters",
    "ceo": "Chief executive",
    "founded_year": "Founded",
    "headcount_range": "Employees",
    "funding_total": "Funding raised",
}

FIELD_HINTS = {
    "legal_name": "Registered company name",
    "hq_city": "Headquarters city",
    "ceo": "Chief executive officer",
    "founded_year": "Year the company was founded",
    "headcount_range": "Employees on staff",
    "funding_total": "Total equity funding raised",
}

EXEC_LABELS = {"cfo": "Chief financial officer", "coo": "Chief operating officer", "cto": "Chief technology officer"}
EXEC_ORDER = ("cfo", "coo", "cto")

STATUS_LABELS = {"known": "Known", "contested": "Contested", "unknown": "Unknown"}
KIND_LABELS = {
    "own": "Own site",
    "filing": "Filing",
    "news": "News",
    "aggregator": "Aggregator",
    None: "Imported",
}
PROVIDER_LABELS = {
    "nimble": "Nimble",
    "tavily": "Tavily",
    "kernel": "Kernel",
    "browserbase": "Browserbase",
}

MONTHS = (
    "Jan",
    "Feb",
    "Mar",
    "Apr",
    "May",
    "Jun",
    "Jul",
    "Aug",
    "Sep",
    "Oct",
    "Nov",
    "Dec",
)


def esc(value: object) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def value_text(field: str, value: object) -> str:
    if value is None:
        return ""
    if field == "headcount_range" and isinstance(value, str):
        return value.replace("-", "\u2013")
    if field == "funding_total" and isinstance(value, int) and not isinstance(value, bool):
        return "$" + f"{value:,}"
    return str(value)


def data_value(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def formatted_time(value: object) -> str:
    if not isinstance(value, str) or not value:
        return ""
    text = value
    if text[-1] in "Zz":
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return value
    if parsed.tzinfo is None:
        return value
    parsed = parsed.astimezone(timezone.utc)
    return (
        f"{parsed.day} {MONTHS[parsed.month - 1]} {parsed.year}, "
        f"{parsed.hour:02d}:{parsed.minute:02d} UTC"
    )


def spent_text(units: object) -> str:
    if not isinstance(units, int):
        return ""
    return f"{units} unit" if units == 1 else f"{units} units"


STYLE = """
:root{
  --ink:#1c2521;--muted:#5b6a63;--line:#dde3df;--bg:#f6f7f5;--card:#ffffff;
  --accent:#1d6b58;--accent-ink:#0f4d3f;--accent-soft:#e4f1ec;
  --known:#1d6b58;--known-bg:#e4f1ec;--contested:#8a5a00;--contested-bg:#fbf0d9;
  --unknown:#5b6a63;--unknown-bg:#eef1ef;--danger:#a23434;--danger-bg:#fbe9e9;
  --amber:#9a6a12;--amber-bg:#fbf2dd;--focus:#0b5fff;
  --radius:14px;--shadow:0 1px 2px rgba(28,37,33,.06),0 8px 24px rgba(28,37,33,.05);
}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--bg);color:var(--ink);
 font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif;
 font-size:16px;line-height:1.55}
a{color:var(--accent-ink);text-decoration-thickness:1px;text-underline-offset:2px}
a:hover{color:var(--accent)}
:focus-visible{outline:3px solid var(--focus);outline-offset:2px;border-radius:6px}
.skip{position:absolute;left:-9999px;top:0;background:#fff;padding:.6rem 1rem;z-index:9}
.skip:focus{left:1rem;top:1rem}
.wrap{width:100%;max-width:1080px;margin:0 auto;padding:0 clamp(16px,4vw,32px)}
.site-header{background:#fff;border-bottom:1px solid var(--line);position:sticky;top:0;z-index:5}
.site-header .wrap{display:flex;align-items:center;gap:18px;min-height:62px;flex-wrap:wrap;padding-top:8px;padding-bottom:8px}
.brand{font-weight:700;font-size:1.12rem;letter-spacing:-.02em;color:var(--ink);text-decoration:none;display:inline-flex;align-items:center;gap:8px}
.brand .mark{width:22px;height:22px;border-radius:7px;background:var(--accent);display:inline-block;position:relative}
.brand .mark:after{content:"";position:absolute;inset:6px;border:2px solid #fff;border-radius:3px}
.site-nav{display:flex;gap:6px;flex-wrap:wrap}
.site-nav a{padding:6px 10px;border-radius:999px;text-decoration:none;color:var(--muted);font-weight:600;font-size:.92rem}
.site-nav a[aria-current="page"],.site-nav a:hover{background:var(--accent-soft);color:var(--accent-ink)}
.account{margin-left:auto;display:flex;align-items:center;gap:10px;flex-wrap:wrap}
.current-user{font-size:.9rem;color:var(--muted)}
.current-user strong{color:var(--ink)}
.linkish{background:none;border:0;color:var(--accent-ink);font:inherit;font-weight:600;cursor:pointer;padding:6px 2px;text-decoration:underline}
main.wrap{padding-top:clamp(20px,4vw,40px);padding-bottom:64px}
.eyebrow{text-transform:uppercase;letter-spacing:.12em;font-size:.74rem;font-weight:700;color:var(--muted);margin:0 0 6px}
h1{font-size:clamp(1.55rem,4vw,2.15rem);line-height:1.15;letter-spacing:-.02em;margin:0 0 .35rem}
h2{font-size:1.12rem;margin:0}
.lede{color:var(--muted);margin:.2rem 0 1.6rem;max-width:60ch}
.panel{background:var(--card);border:1px solid var(--line);border-radius:var(--radius);box-shadow:var(--shadow);padding:clamp(16px,3vw,24px)}
.stack{display:flex;flex-direction:column;gap:16px}
.grid-2{display:grid;grid-template-columns:1fr;gap:20px}
@media(min-width:820px){.grid-2{grid-template-columns:minmax(0,1.15fr) minmax(0,1fr)}}
label{display:block;font-weight:650;font-size:.9rem;margin-bottom:6px}
.hint{color:var(--muted);font-size:.85rem;margin:.35rem 0 0}
input[type=text],input[type=email],input[type=password],input:not([type]){width:100%;padding:.68rem .8rem;border:1px solid #c6d0ca;border-radius:10px;background:#fff;font:inherit;color:var(--ink);min-width:0}
input:hover{border-color:#a9b7af}
.inline-form{display:flex;gap:10px;flex-wrap:wrap;align-items:flex-end}
.inline-form .field{flex:1 1 220px;min-width:0}
button,.button{display:inline-flex;align-items:center;justify-content:center;gap:8px;border:1px solid transparent;border-radius:10px;padding:.62rem 1.05rem;font:inherit;font-weight:650;cursor:pointer;text-decoration:none;line-height:1.2}
button.primary,.button.primary{background:var(--accent);color:#fff}
button.primary:hover,.button.primary:hover{background:var(--accent-ink)}
button.secondary,.button.secondary{background:#fff;border-color:#c6d0ca;color:var(--ink)}
button.secondary:hover,.button.secondary:hover{border-color:var(--accent);color:var(--accent-ink)}
button[disabled]{opacity:.6;cursor:progress}
.actions{display:flex;gap:10px;flex-wrap:wrap;align-items:center}
.notice{margin:0 0 14px;padding:.7rem .9rem;border-radius:10px;font-size:.92rem;border:1px solid}
.notice.error,.error-text{background:var(--danger-bg);border-color:#e7bcbc;color:#7d2323}
.notice.uncertain{background:var(--amber-bg);border-color:#e6d29a;color:#6e4d0c}
.notice:empty{display:none}
.badge{display:inline-flex;align-items:center;gap:6px;border-radius:999px;padding:.2rem .62rem;font-size:.78rem;font-weight:700;letter-spacing:.01em;border:1px solid transparent;white-space:nowrap}
.badge:before{content:"";width:7px;height:7px;border-radius:50%;background:currentColor}
.status-known{background:var(--known-bg);color:var(--known)}
.status-contested{background:var(--contested-bg);color:var(--contested)}
.status-unknown{background:var(--unknown-bg);color:var(--unknown)}
.state-ready{background:var(--known-bg);color:var(--known)}
.state-building{background:var(--amber-bg);color:var(--amber)}
.state-failed{background:var(--danger-bg);color:var(--danger)}
.chip{display:inline-flex;align-items:center;gap:6px;background:#f1f4f2;border:1px solid var(--line);border-radius:999px;padding:.16rem .55rem;font-size:.76rem;color:var(--muted);font-weight:600;white-space:nowrap}
.list{list-style:none;margin:0;padding:0;display:flex;flex-direction:column;gap:10px}
.dossier-card{display:block;background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px 16px;text-decoration:none;color:inherit}
.dossier-card:hover{border-color:#b7c6be;box-shadow:var(--shadow)}
.dossier-card .row{display:flex;gap:10px;align-items:center;justify-content:space-between;flex-wrap:wrap}
.dossier-card .domain{font-weight:700}
.dossier-card .name{color:var(--muted);min-width:0;overflow-wrap:anywhere}
.dossier-head{display:flex;gap:18px;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;margin-bottom:18px}
.dossier-head .actions{flex:1 1 260px;justify-content:flex-end}
.meta{display:flex;gap:8px 14px;flex-wrap:wrap;align-items:center;color:var(--muted);font-size:.9rem;margin-top:.4rem}
.meta .spend,.meta .researched{display:inline-flex;align-items:center;gap:6px}
.fields{display:flex;flex-direction:column;gap:12px}
.field{background:var(--card);border:1px solid var(--line);border-left:4px solid var(--unknown);border-radius:12px;padding:16px 18px;box-shadow:var(--shadow);min-width:0}
.field[data-status=known]{border-left-color:var(--known)}
.field[data-status=contested]{border-left-color:var(--contested)}
.field[data-status=unknown]{border-left-color:#c3ccc6}
.field-head{display:flex;gap:10px;align-items:baseline;flex-wrap:wrap;margin-bottom:2px}
.field-head h2{font-size:1.02rem}
.field-hint{color:var(--muted);font-size:.82rem}
.field-value{font-size:1.32rem;font-weight:700;letter-spacing:-.01em;margin:.35rem 0 .1rem;overflow-wrap:anywhere}
.field-value.empty-value{font-size:1rem;font-weight:600;color:var(--muted)}
.contested-marker{font-size:.78rem;font-weight:700;color:var(--contested);background:var(--contested-bg);border-radius:999px;padding:.1rem .5rem}
.citations{display:flex;flex-direction:column;gap:8px;margin-top:10px}
.citation{margin:0;padding:10px 12px;background:#fafbfa;border:1px solid var(--line);border-radius:10px;min-width:0}
.citation blockquote{margin:0 0 6px;quotes:"\\201C" "\\201D";font-size:.93rem;overflow-wrap:anywhere}
.citation blockquote:before{content:open-quote}
.citation blockquote:after{content:close-quote}
.citation figcaption{display:flex;gap:8px;flex-wrap:wrap;align-items:center;font-size:.8rem;color:var(--muted);min-width:0}
.citation figcaption a{overflow-wrap:anywhere}
.no-citations{font-size:.86rem;color:var(--muted);margin:8px 0 0}
.kind{font-weight:700;color:var(--ink)}
.candidates{list-style:none;margin:0;padding:0;display:flex;flex-direction:column;gap:10px}
.candidate{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px 16px;min-width:0}
.candidate[data-selected=true]{border-color:#a9cdbf;box-shadow:0 0 0 1px #a9cdbf inset}
.candidate .cand-head{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-bottom:6px}
.candidate .cand-value{font-weight:700;font-size:1.05rem;margin:.1rem 0 .3rem;overflow-wrap:anywhere}
.candidate blockquote{margin:.2rem 0 .4rem;padding-left:10px;border-left:3px solid var(--line);color:#33423b;font-size:.92rem;overflow-wrap:anywhere}
.candidate .cand-foot{display:flex;gap:10px;flex-wrap:wrap;font-size:.8rem;color:var(--muted);min-width:0}
.evidence-group{margin-bottom:18px}
.evidence-group h2{display:flex;gap:10px;align-items:baseline;flex-wrap:wrap;margin-bottom:10px}
.empty-note{color:var(--muted);font-size:.9rem;margin:0;padding:10px 0}
.exec-list{list-style:none;margin:10px 0 0;padding:0;display:flex;flex-direction:column;gap:8px}
.exec-member{display:flex;gap:12px;align-items:baseline;flex-wrap:wrap;border-top:1px solid var(--line);padding-top:8px}
.exec-member:first-child{border-top:0;padding-top:0}
.exec-role{color:var(--muted);font-size:.86rem;font-weight:650;min-width:180px}
.exec-name{font-weight:700;font-size:1.05rem}
.history-entry{display:flex;gap:10px;align-items:baseline;flex-wrap:wrap;background:var(--card);border:1px solid var(--line);border-radius:10px;padding:10px 12px}
.history-value{font-weight:650}
.contested-list{list-style:none;margin:0;padding:0;display:flex;flex-direction:column;gap:10px}
.contested-item{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px 16px;min-width:0}
.contested-item .ci-head{display:flex;gap:8px;align-items:baseline;flex-wrap:wrap;margin-bottom:4px}
.contested-item .ci-field{font-weight:700}
.contested-item .ci-values{color:var(--muted);font-size:.9rem;margin:.2rem 0 .5rem;overflow-wrap:anywhere}
.auth-wrap{max-width:430px;margin:clamp(18px,6vh,60px) auto 0}
.auth-card{padding:clamp(20px,4vw,30px)}
.auth-card h1{font-size:1.55rem;margin-bottom:.2rem}
.form-row{margin-bottom:14px}
.auth-foot{margin:14px 0 0;font-size:.9rem;color:var(--muted)}
.empty-state{text-align:center;padding:34px 16px;color:var(--muted)}
.empty-state strong{display:block;color:var(--ink);font-size:1.05rem;margin-bottom:4px}
footer.site-footer{border-top:1px solid var(--line);color:var(--muted);font-size:.82rem;padding:18px 0 26px;background:transparent}
code{font-size:.85em;background:#eef1ef;padding:.1rem .3rem;border-radius:5px;overflow-wrap:anywhere}
@media(max-width:560px){
 .site-header .wrap{gap:10px}
 .account{width:100%;justify-content:space-between}
 .dossier-head .actions{justify-content:flex-start}
 .field-value{font-size:1.18rem}
}
"""


def _layout(
    title: str,
    body: str,
    *,
    user: dict | None = None,
    active: str | None = None,
    page_script: str = "",
) -> str:
    nav_items = [("/", "Dossiers", "dossiers"), ("/contested", "Contested", "contested")]
    nav = "".join(
        f'<a href="{href}"{" aria-current=\"page\"" if key == active else ""}>{label}</a>'
        for href, label, key in nav_items
    )
    if user is not None:
        account = (
            '<div class="account">'
            f'<span class="current-user" data-testid="current-user">Signed in as <strong>{esc(user.get("display_name"))}</strong></span>'
            '<form method="post" action="/logout">'
            '<button class="linkish" type="submit" data-testid="logout-button">Sign out</button>'
            "</form></div>"
        )
    else:
        account = (
            '<div class="account">'
            '<a href="/login">Log in</a>'
            '<a class="button primary" href="/signup">Create account</a>'
            "</div>"
        )
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>
<style>{STYLE}</style>
</head>
<body>
<a class="skip" href="#main">Skip to content</a>
<header class="site-header"><div class="wrap">
<a class="brand" href="/"><span class="mark" aria-hidden="true"></span>Dossier</a>
<nav class="site-nav" aria-label="Main">{nav}</nav>
{account}
</div></header>
<main class="wrap" id="main">
{body}
</main>
<footer class="site-footer"><div class="wrap">Evidence-first company research. Every value links to the text it came from.</div></footer>
<script>{SCRIPT}{page_script}</script>
</body>
</html>"""


SCRIPT = r"""
(function(){
  const qs=(s,r=document)=>r.querySelector(s);
  const qsa=(s,r=document)=>Array.from(r.querySelectorAll(s));
  function esc(v){return String(v==null?'':v).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}
  function newKey(){
    if(window.crypto&&crypto.randomUUID)return crypto.randomUUID();
    return 'k-'+Date.now().toString(36)+'-'+Math.random().toString(36).slice(2);
  }
  function showNotice(testid, text, kind){
    let node=qs('[data-testid="'+testid+'"]');
    if(!node){
      node=document.createElement('div');
      node.setAttribute('data-testid',testid);
      node.className='notice '+(kind||'error');
      node.setAttribute('role','alert');
      const host=qs('#page-notices')||qs('main');
      host.prepend(node);
    }
    node.textContent=text;
    node.hidden=false;
  }
  function clearNotice(testid){
    const node=qs('[data-testid="'+testid+'"]');
    if(node){node.remove();}
  }
  function fieldValue(field,value){
    if(value==null)return '';
    if(field==='headcount_range')return String(value).replace(/-/g,'\u2013');
    if(field==='funding_total')return '$'+Number(value).toLocaleString('en-US');
    return String(value);
  }
  window.__ui={qs,qsa,esc,newKey,showNotice,clearNotice,fieldValue};
})();
"""


DOSSIER_SCRIPT = r"""
(function(){
  const {qs,esc,showNotice,clearNotice,fieldValue,newKey}=window.__ui;
  const root=qs('[data-dossier]');
  if(!root)return;
  const domain=root.getAttribute('data-domain');
  const fieldsHost=qs('#dossier-fields');
  let readSeq=0, appliedSeq=0, pollTimer=null, pendingRefresh=null;

  const FIELD_ORDER=['legal_name','hq_city','ceo','founded_year','headcount_range','funding_total'];
  const LABELS={legal_name:'Legal name',hq_city:'Headquarters',ceo:'Chief executive',founded_year:'Founded',headcount_range:'Employees',funding_total:'Funding raised'};
  const HINTS={legal_name:'Registered company name',hq_city:'Headquarters city',ceo:'Chief executive officer',founded_year:'Year the company was founded',headcount_range:'Employees on staff',funding_total:'Total equity funding raised'};
  const STATUS={known:'Known',contested:'Contested',unknown:'Unknown'};
  const MONTHS=['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];

  function fmtTime(v){
    if(!v)return '';
    const d=new Date(v);
    if(isNaN(d.getTime()))return String(v);
    const p=n=>String(n).padStart(2,'0');
    return d.getUTCDate()+' '+MONTHS[d.getUTCMonth()]+' '+d.getUTCFullYear()+', '+p(d.getUTCHours())+':'+p(d.getUTCMinutes())+' UTC';
  }
  function spentText(n){return n===1?'1 unit':n+' units';}
  function hostOf(url){try{return new URL(url).host;}catch(e){return url;}}

  function fieldHtml(field,data){
    const status=data&&data.status?data.status:'unknown';
    const value=data?data.value:null;
    const citations=(data&&data.citations)||[];
    const parts=[];
    parts.push('<article class="field" data-testid="field-'+field+'" data-status="'+esc(status)+'">');
    parts.push('<div class="field-head"><h2>'+esc(LABELS[field])+'</h2>');
    parts.push('<span class="badge status-'+esc(status)+'">'+esc(STATUS[status]||status)+'</span>');
    parts.push('<span class="field-hint">'+esc(HINTS[field])+'</span>');
    if(status==='contested')parts.push('<span class="contested-marker" data-testid="field-contested-'+field+'">Sources disagree</span>');
    parts.push('</div>');
    if(value!==null&&value!==undefined){
      parts.push('<p class="field-value" data-testid="field-value-'+field+'" data-value="'+esc(value)+'">'+esc(fieldValue(field,value))+'</p>');
    }else{
      parts.push('<p class="field-value empty-value">Not found in the evidence yet</p>');
    }
    parts.push('<div class="citations" data-testid="field-citations-'+field+'">');
    if(citations.length){
      citations.forEach(function(c,i){
        parts.push('<figure class="citation" data-testid="citation-'+field+'-'+(i+1)+'" data-provider="'+esc(c.provider)+'">');
        parts.push('<blockquote>'+esc(c.excerpt)+'</blockquote>');
        parts.push('<figcaption><a href="'+esc(c.url)+'" rel="noreferrer noopener">'+esc(hostOf(c.url))+'</a><span class="chip">'+esc(c.provider)+'</span></figcaption>');
        parts.push('</figure>');
      });
    }else{
      parts.push('<p class="no-citations">No supporting citation.</p>');
    }
    parts.push('</div></article>');
    return parts.join('');
  }

  const EXEC_ORDER=['cfo','coo','cto'];
  const EXEC_LABELS={cfo:'Chief financial officer',coo:'Chief operating officer',cto:'Chief technology officer'};
  function execHtml(entry){
    entry=entry||{};
    const status=entry.status||'unknown';
    const members={};
    (entry.value||[]).forEach(function(m){if(m&&EXEC_ORDER.indexOf(m.title)>=0)members[m.title]=m.name;});
    const parts=['<section class="field executive-field" data-status="'+esc(status)+'">'];
    parts.push('<div class="field-head"><h2>Executive team</h2><span class="badge status-'+esc(status)+'">'+esc(STATUS[status]||status)+'</span><span class="field-hint">Chief financial, operating and technology officers</span></div>');
    const present=EXEC_ORDER.filter(function(t){return t in members;});
    if(present.length){
      parts.push('<ul class="exec-list">');
      present.forEach(function(t){parts.push('<li class="exec-member"><span class="exec-role">'+esc(EXEC_LABELS[t])+'</span><span class="exec-name">'+esc(members[t])+'</span></li>');});
      parts.push('</ul>');
    }else{
      parts.push('<p class="field-value empty-value">No named executives in the evidence yet</p>');
    }
    parts.push('</section>');
    return parts.join('');
  }

  function investorsHtml(entry){
    entry=entry||{};
    const status=entry.status||'unknown';
    const names=entry.value||[];
    const parts=['<section class="field executive-field" data-status="'+esc(status)+'">'];
    parts.push('<div class="field-head"><h2>Investors</h2><span class="badge status-'+esc(status)+'">'+esc(STATUS[status]||status)+'</span><span class="field-hint">Names supported by the evidence</span></div>');
    if(names.length){
      parts.push('<ul class="exec-list">');
      names.forEach(function(n){parts.push('<li class="exec-member"><span class="exec-name">'+esc(n)+'</span></li>');});
      parts.push('</ul>');
    }else{
      parts.push('<p class="field-value empty-value">No investors in the evidence yet</p>');
    }
    parts.push('</section>');
    return parts.join('');
  }

  function render(data){
    const stateEl=qs('[data-testid="dossier-state"]');
    if(stateEl){stateEl.textContent=data.state;stateEl.className='badge state-'+data.state;stateEl.setAttribute('data-state',data.state);}
    const spent=qs('[data-testid="dossier-spent"]');
    if(spent){spent.setAttribute('data-units',String(data.spent_units));spent.textContent=spentText(data.spent_units);}
    let ra=qs('[data-testid="dossier-researched-at"]');
    if(data.researched_at){
      if(!ra){ra=document.createElement('span');ra.setAttribute('data-testid','dossier-researched-at');ra.className='researched';qs('.meta').appendChild(ra);}
      ra.textContent='Researched '+fmtTime(data.researched_at);
    }else if(ra){ra.remove();}
    if(fieldsHost){
      fieldsHost.innerHTML=FIELD_ORDER.map(function(f){return fieldHtml(f,data.fields?data.fields[f]:null);}).join('');
    }
    const execHost=qs('#dossier-executives');
    if(execHost){execHost.innerHTML=execHtml(data.fields?data.fields.executives:null);}
    const invHost=qs('#dossier-investors');
    if(invHost){invHost.innerHTML=investorsHtml(data.fields?data.fields.investors:null);}
    schedulePoll(data.state);
  }

  function schedulePoll(state){
    if(state==='building'){
      if(!pollTimer){pollTimer=setInterval(function(){readDossier();},2000);}
    }else if(pollTimer){
      clearInterval(pollTimer);pollTimer=null;
    }
  }

  async function readDossier(){
    const my=++readSeq;
    try{
      const r=await fetch('/dossiers/'+encodeURIComponent(domain),{headers:{'Accept':'application/json'},cache:'no-store',credentials:'same-origin'});
      if(!r.ok)return;
      const data=await r.json();
      if(my<appliedSeq)return;
      appliedSeq=my;
      render(data);
    }catch(e){/* a lost read leaves the last shown state in place */}
  }

  async function doRefresh(){
    const btn=qs('[data-testid="dossier-refresh"]');
    let label='';
    if(btn){label=btn.textContent;btn.disabled=true;btn.setAttribute('aria-busy','true');btn.textContent='Refreshing\u2026';}
    clearNotice('refresh-error');clearNotice('refresh-uncertain');
    const key=pendingRefresh?pendingRefresh.key:newKey();
    try{
      const r=await fetch('/dossiers/'+encodeURIComponent(domain)+'/refresh',{
        method:'POST',
        headers:{'Accept':'application/json','Idempotency-Key':key},
        credentials:'same-origin'
      });
      if(r.status===202||r.status===200){
        pendingRefresh=null;
        await readDossier();
      }else{
        pendingRefresh=null;
        let message='Refresh was refused.';
        try{const j=await r.json();if(j&&j.error&&j.error.message)message=j.error.message;}catch(e){}
        showNotice('refresh-error',message,'error');
      }
    }catch(e){
      pendingRefresh={key:key};
      showNotice('refresh-uncertain','The refresh went through but its reply was lost. Retry to see the result.','uncertain');
    }finally{
      if(btn){btn.disabled=false;btn.removeAttribute('aria-busy');btn.textContent=label;}
    }
  }

  const reload=qs('[data-testid="dossier-reload"]');
  if(reload)reload.addEventListener('click',function(){readDossier();});
  const refresh=qs('[data-testid="dossier-refresh"]');
  if(refresh)refresh.addEventListener('click',doRefresh);
  schedulePoll(root.getAttribute('data-state')||'ready');
})();
"""


LIST_SCRIPT = r"""
(function(){
  const {qs,esc,showNotice,clearNotice,newKey}=window.__ui;
  const form=qs('[data-research-form]');
  const search=qs('[data-testid="dossier-search"]');
  const list=qs('[data-testid="dossier-list"]');
  const empty=qs('[data-testid="empty-dossiers"]');
  let pending=null;

  const allItems=list?Array.from(list.children).map(function(item){
    return {html:item.outerHTML,text:(item.getAttribute('data-search')||'').toLowerCase()};
  }):[];

  function filter(){
    if(!search||!list)return;
    const needle=(search.value||'').trim().toLowerCase();
    const matches=allItems.filter(function(entry){return !needle||entry.text.indexOf(needle)>=0;});
    list.innerHTML=matches.map(function(entry){return entry.html;}).join('');
    list.hidden=matches.length===0;
    if(empty)empty.hidden=matches.length!==0;
  }
  if(search){search.addEventListener('input',filter);filter();}

  if(form){
    form.addEventListener('submit',async function(ev){
      ev.preventDefault();
      clearNotice('research-error');clearNotice('research-uncertain');
      const input=qs('[data-testid="research-domain"]');
      const button=qs('[data-testid="research-submit"]');
      const key=pending?pending.key:newKey();
      const body=pending?pending.body:JSON.stringify({domain:input?input.value:''});
      let label='';
      if(button){label=button.textContent;button.disabled=true;button.setAttribute('aria-busy','true');button.textContent='Researching\u2026';}
      try{
        const r=await fetch('/dossiers',{
          method:'POST',
          headers:{'Content-Type':'application/json','Accept':'application/json','Idempotency-Key':key},
          body:body,
          credentials:'same-origin'
        });
        if(r.status===202||r.status===200){
          const data=await r.json();
          pending=null;
          window.location.assign('/dossiers/'+encodeURIComponent(data.domain));
          return;
        }
        pending=null;
        let message='Research was refused.';
        try{const j=await r.json();if(j&&j.error)message=j.error.message||j.error.code||message;}catch(e){}
        showNotice('research-error',message,'error');
      }catch(e){
        pending={key:key,body:body};
        showNotice('research-uncertain','The request may have gone through but its reply was lost. Submit again to retry safely.','uncertain');
      }finally{
        if(button){button.disabled=false;button.removeAttribute('aria-busy');button.textContent=label;}
      }
    });
  }
  filter();
})();
"""


AUTH_SCRIPT = r"""
(function(){
  const {qs}=window.__ui;
  const form=qs('[data-auth-form]');
  const error=qs('[data-testid="auth-error"]');
  if(form){
    form.addEventListener('submit',function(){
      if(error){error.hidden=true;error.textContent='';}
    });
  }
})();
"""


def auth_page(mode: str, *, error: str | None = None, user: dict | None = None) -> str:
    if mode == "signup":
        title = "Create your account"
        action = "/signup"
        fields = (
            '<div class="form-row"><label for="signup-email">Email</label>'
            '<input id="signup-email" name="email" type="email" autocomplete="email" required data-testid="signup-email"></div>'
            '<div class="form-row"><label for="signup-display-name">Display name</label>'
            '<input id="signup-display-name" name="display_name" type="text" autocomplete="name" required data-testid="signup-display-name"></div>'
            '<div class="form-row"><label for="signup-password">Password</label>'
            '<input id="signup-password" name="password" type="password" autocomplete="new-password" minlength="8" required data-testid="signup-password">'
            '<p class="hint">At least 8 characters.</p></div>'
            '<button class="primary" type="submit" data-testid="signup-submit" style="width:100%">Create account</button>'
        )
        foot = '<p class="auth-foot">Already have an account? <a href="/login">Log in</a></p>'
    else:
        title = "Welcome back"
        action = "/login"
        fields = (
            '<div class="form-row"><label for="login-email">Email</label>'
            '<input id="login-email" name="email" type="email" autocomplete="email" required data-testid="login-email"></div>'
            '<div class="form-row"><label for="login-password">Password</label>'
            '<input id="login-password" name="password" type="password" autocomplete="current-password" required data-testid="login-password"></div>'
            '<button class="primary" type="submit" data-testid="login-submit" style="width:100%">Log in</button>'
        )
        foot = '<p class="auth-foot">New here? <a href="/signup">Create an account</a></p>'
    error_html = (
        f'<p class="notice error" data-testid="auth-error" role="alert">{esc(error)}</p>'
        if error
        else ""
    )
    body = f"""<div class="auth-wrap"><div class="panel auth-card">
<p class="eyebrow">Dossier</p>
<h1>{esc(title)}</h1>
<p class="lede">Research companies from the evidence the web actually serves.</p>
{error_html}
<form method="post" action="{action}" data-auth-form>
{fields}
</form>
{foot}
</div></div>"""
    return _layout(title, body, user=user, page_script=AUTH_SCRIPT)


def message_page(title: str, message: str, *, user: dict | None = None) -> str:
    body = (
        f'<p class="eyebrow">Dossier</p><h1>{esc(title)}</h1>'
        f'<div class="panel"><p>{esc(message)}</p>'
        '<p><a href="/">Back to the dossier list</a></p></div>'
    )
    return _layout(title, body, user=user)


def list_page(
    dossiers: list[dict],
    q: str,
    *,
    user: dict | None = None,
    error: str | None = None,
    uncertain: str | None = None,
) -> str:
    items = []
    for dossier in dossiers:
        domain = dossier.get("domain") or ""
        legal_name = dossier.get("legal_name")
        state = dossier.get("state") or ""
        search_text = domain + " " + (legal_name or "")
        name_html = (
            f'<span class="name">{esc(legal_name)}</span>' if isinstance(legal_name, str) else ""
        )
        items.append(
            f'<li data-testid="dossier-item-{esc(domain)}" data-state="{esc(state)}" '
            f'data-search="{esc(search_text)}">'
            f'<a class="dossier-card" href="/dossiers/{esc(domain)}">'
            '<span class="row">'
            f'<span><span class="domain">{esc(domain)}</span> {name_html}</span>'
            f'<span class="badge state-{esc(state)}">{esc(state.title())}</span>'
            "</span></a></li>"
        )
    list_html = (
        '<ul class="list" data-testid="dossier-list">' + "".join(items) + "</ul>"
        if items
        else '<ul class="list" data-testid="dossier-list" hidden></ul>'
    )
    empty_html = (
        '<div class="empty-state" data-testid="empty-dossiers"'
        + ("" if not items else " hidden")
        + "><strong>No dossiers match.</strong>"
        "Research a domain to start a dossier, or clear the filter.</div>"
    )
    error_html = (
        f'<p class="notice error" data-testid="research-error" role="alert">{esc(error)}</p>'
        if error
        else ""
    )
    uncertain_html = (
        f'<p class="notice uncertain" data-testid="research-uncertain" role="status">{esc(uncertain)}</p>'
        if uncertain
        else ""
    )
    body = f"""<p class="eyebrow">Dossier library</p>
<h1>Company dossiers</h1>
<p class="lede">Ask the web who a company is. Every value keeps the passages it came from, and disagreements stay visible.</p>
<div class="grid-2">
<section class="panel" aria-labelledby="research-heading">
<h2 id="research-heading">Research a company</h2>
<p class="hint" style="margin-top:.2rem">Enter the company's web domain, such as <code>acme-robotics.test</code>.</p>
{error_html}
{uncertain_html}
<form class="inline-form" data-research-form novalidate>
<div class="field"><label for="research-domain">Company domain</label>
<input id="research-domain" name="domain" type="text" inputmode="url" autocomplete="off" placeholder="acme-robotics.test" data-testid="research-domain" required></div>
<button class="primary" type="submit" data-testid="research-submit">Research</button>
</form>
</section>
<section class="panel" aria-labelledby="search-heading">
<h2 id="search-heading">Find a dossier</h2>
<p class="hint" style="margin-top:.2rem">Filter by domain or company name.</p>
<div class="field" style="margin-top:12px"><label for="dossier-search">Search dossiers</label>
<input id="dossier-search" name="q" type="text" value="{esc(q)}" autocomplete="off" data-testid="dossier-search"></div>
</section>
</div>
<h2 style="margin:26px 0 12px">All dossiers</h2>
{list_html}
{empty_html}"""
    return _layout("Dossiers", body, user=user, active="dossiers", page_script=LIST_SCRIPT)


def _exec_members(fields: dict) -> dict:
    entry = fields.get("executives") or {}
    members = {}
    for member in entry.get("value") or []:
        if isinstance(member, dict) and member.get("title") in EXEC_ORDER:
            members[member["title"]] = member.get("name")
    return members


def executives_html(fields: dict) -> str:
    entry = fields.get("executives") or {}
    status = entry.get("status") or "unknown"
    members = _exec_members(fields)
    candidates = entry.get("candidates") or []
    parts = [
        '<section class="field executive-field" data-status="' + esc(status) + '">',
        '<div class="field-head"><h2>Executive team</h2>'
        '<span class="badge status-' + esc(status) + '">' + esc(STATUS_LABELS.get(status, status)) + '</span>'
        '<span class="field-hint">Chief financial, operating and technology officers</span></div>',
    ]
    if members:
        parts.append('<ul class="exec-list">')
        for title in EXEC_ORDER:
            if title in members:
                parts.append(
                    '<li class="exec-member"><span class="exec-role">' + esc(EXEC_LABELS[title]) + '</span>'
                    '<span class="exec-name">' + esc(members[title]) + '</span></li>'
                )
        parts.append('</ul>')
    else:
        parts.append('<p class="field-value empty-value">No named executives in the evidence yet</p>')
    if candidates:
        parts.append('<p class="hint" style="margin-top:10px">')
        parts.append(esc(str(len(candidates))) + ' named candidates across the three roles.</p>')
    parts.append('</section>')
    return "".join(parts)


def investors_html(fields: dict) -> str:
    entry = fields.get("investors") or {}
    status = entry.get("status") or "unknown"
    names = entry.get("value") or []
    candidates = entry.get("candidates") or []
    parts = [
        '<section class="field executive-field" data-status="' + esc(status) + '">',
        '<div class="field-head"><h2>Investors</h2>'
        '<span class="badge status-' + esc(status) + '">' + esc(STATUS_LABELS.get(status, status)) + '</span>'
        '<span class="field-hint">Names supported by the evidence</span></div>',
    ]
    if names:
        parts.append('<ul class="exec-list">')
        for name in names:
            parts.append('<li class="exec-member"><span class="exec-name">' + esc(str(name)) + '</span></li>')
        parts.append('</ul>')
    else:
        parts.append('<p class="field-value empty-value">No investors in the evidence yet</p>')
    if candidates:
        parts.append('<p class="hint" style="margin-top:10px">' + esc(str(len(candidates))) + ' named candidates.</p>')
    parts.append('</section>')
    return "".join(parts)


def _fields_html(fields: dict) -> str:
    parts = []
    for field in FIELD_ORDER:
        data = fields.get(field) or {}
        status = data.get("status") or "unknown"
        value = data.get("value")
        citations = data.get("citations") or []
        parts.append(
            f'<article class="field" data-testid="field-{field}" data-status="{esc(status)}">'
            '<div class="field-head">'
            f"<h2>{esc(FIELD_LABELS[field])}</h2>"
            f'<span class="badge status-{esc(status)}">{esc(STATUS_LABELS.get(status, status))}</span>'
            f'<span class="field-hint">{esc(FIELD_HINTS[field])}</span>'
        )
        if status == "contested":
            parts.append(
                f'<span class="contested-marker" data-testid="field-contested-{field}">Sources disagree</span>'
            )
        parts.append("</div>")
        if value is not None:
            parts.append(
                f'<p class="field-value" data-testid="field-value-{field}" '
                f'data-value="{esc(data_value(value))}">{esc(value_text(field, value))}</p>'
            )
        else:
            parts.append('<p class="field-value empty-value">Not found in the evidence yet</p>')
        parts.append(f'<div class="citations" data-testid="field-citations-{field}">')
        if citations:
            for index, citation in enumerate(citations, start=1):
                url = citation.get("url") or ""
                provider = citation.get("provider") or ""
                parts.append(
                    f'<figure class="citation" data-testid="citation-{field}-{index}" '
                    f'data-provider="{esc(provider)}">'
                    f"<blockquote>{esc(citation.get('excerpt') or '')}</blockquote>"
                    "<figcaption>"
                    f'<a href="{esc(url)}" rel="noreferrer noopener">{esc(url)}</a>'
                    f'<span class="chip">{esc(PROVIDER_LABELS.get(provider, provider))}</span>'
                    "</figcaption></figure>"
                )
        else:
            parts.append('<p class="no-citations">No supporting citation.</p>')
        parts.append("</div></article>")
    return "".join(parts)


def dossier_page(
    data: dict | None,
    domain: str,
    *,
    user: dict | None = None,
    not_found: bool = False,
) -> str:
    if not_found or data is None:
        meta = (
            f'<h1 data-testid="dossier-domain">{esc(domain)}</h1>'
            '<p class="lede">This domain has no dossier yet.</p>'
        )
        fields_html = (
            '<div class="panel empty-state" data-testid="dossier-not-found">'
            "<strong>No dossier for this domain</strong>"
            "Research it from the dossier list to start one.</div>"
        )
        state = "ready"
        spent = ""
        researched = ""
    else:
        state = data.get("state") or ""
        spent_value = data.get("spent_units", 0)
        spent = spent_text(spent_value)
        researched_at = data.get("researched_at")
        researched = (
            f'<span class="researched" data-testid="dossier-researched-at">Researched '
            f"{esc(formatted_time(researched_at))}</span>"
            if researched_at
            else ""
        )
        meta = (
            f'<h1 data-testid="dossier-domain">{esc(data.get("domain") or domain)}</h1>'
            '<div class="meta">'
            f'<span class="badge state-{esc(state)}" data-testid="dossier-state" data-state="{esc(state)}">{esc(state)}</span>'
            f'<span class="spend" data-testid="dossier-spent" data-units="{esc(data.get("spent_units", 0))}">{esc(spent)}</span>'
            f"{researched}"
            "</div>"
        )
        fields_html = (
            f'<div class="fields" id="dossier-fields">{_fields_html(data.get("fields") or {})}</div>'
            f'<div id="dossier-executives">{executives_html(data.get("fields") or {})}</div>'
            f'<div id="dossier-investors">{investors_html(data.get("fields") or {})}</div>'
        )

    body = f"""<div data-dossier data-domain="{esc(domain)}" data-state="{esc(state)}">
<div class="dossier-head">
<div>
<p class="eyebrow">Company dossier</p>
{meta}
</div>
<div class="actions">
<a class="button secondary" href="/dossiers/{esc(domain)}/evidence" data-testid="dossier-evidence-link">View evidence</a>
<a class="button secondary" href="/dossiers/{esc(domain)}/history">Change history</a>
<button class="secondary" type="button" data-testid="dossier-reload">Reload</button>
<button class="primary" type="button" data-testid="dossier-refresh">Refresh</button>
</div>
</div>
<div id="page-notices"></div>
{fields_html}
</div>"""
    return _layout(
        f"Dossier — {domain}", body, user=user, active="dossiers", page_script=DOSSIER_SCRIPT
    )


def evidence_page(data: dict, *, user: dict | None = None) -> str:
    domain = data.get("domain") or ""
    groups = []
    for field in FIELD_ORDER:
        entry = (data.get("fields") or {}).get(field) or {}
        candidates = entry.get("candidates") or []
        parts = [
            f'<section class="evidence-group" data-testid="evidence-{field}">'
            f"<h2>{esc(FIELD_LABELS[field])} "
            f'<span class="badge status-{esc(entry.get("status") or "unknown")}">'
            f'{esc(STATUS_LABELS.get(entry.get("status") or "unknown", ""))}</span></h2>'
        ]
        if candidates:
            parts.append('<ol class="candidates">')
            for index, candidate in enumerate(candidates, start=1):
                published = candidate.get("published_at")
                kind = candidate.get("kind")
                selected = bool(candidate.get("selected"))
                parts.append(
                    f'<li class="candidate" data-testid="candidate-{field}-{index}" '
                    f'data-value="{esc(data_value(candidate.get("value")))}" '
                    f'data-provider="{esc(candidate.get("provider") or "")}" '
                    f'data-kind="{esc(kind or "")}" '
                    f'data-url="{esc(candidate.get("url") or "")}" '
                    f'data-published-at="{esc(published or "")}" '
                    f'data-selected="{"true" if selected else "false"}">'
                    '<div class="cand-head">'
                    + (
                        '<span class="badge status-known">Selected value</span>'
                        if selected
                        else ""
                    )
                    + f'<span class="chip kind">{esc(KIND_LABELS.get(kind, kind or "Imported"))}</span>'
                    f'<span class="chip">{esc(PROVIDER_LABELS.get(candidate.get("provider"), candidate.get("provider") or ""))}</span>'
                    + (
                        f'<span class="chip">{esc(formatted_time(published))}</span>'
                        if published
                        else '<span class="chip">No publication date</span>'
                    )
                    + "</div>"
                    f'<p class="cand-value">{esc(value_text(field, candidate.get("value")))}</p>'
                    f"<blockquote>{esc(candidate.get('excerpt') or '')}</blockquote>"
                    '<div class="cand-foot">'
                    f'<a href="{esc(candidate.get("url") or "")}" rel="noreferrer noopener">{esc(candidate.get("url") or "")}</a>'
                    "</div></li>"
                )
            parts.append("</ol>")
        else:
            parts.append(
                f'<p class="empty-note" data-testid="evidence-empty-{field}">'
                "No candidate values for this field.</p>"
            )
        parts.append("</section>")
        groups.append("".join(parts))

    exec_entry = (data.get("fields") or {}).get("executives") or {}
    exec_candidates = exec_entry.get("candidates") or []
    exec_parts = ['<section class="evidence-group executive-field">']
    exec_parts.append(
        '<h2>Executive team '
        f'<span class="badge status-{esc(exec_entry.get("status") or "unknown")}">'
        f'{esc(STATUS_LABELS.get(exec_entry.get("status") or "unknown", ""))}</span></h2>'
    )
    if exec_candidates:
        exec_parts.append('<ol class="candidates">')
        for candidate in exec_candidates:
            title = candidate.get("title")
            exec_parts.append(
                '<li class="candidate" data-selected="' + ("true" if candidate.get("selected") else "false") + '">'
                '<div class="cand-head">'
                + ('<span class="badge status-known">Selected</span>' if candidate.get("selected") else "")
                + f'<span class="chip kind">{esc(EXEC_LABELS.get(title, title or ""))}</span>'
                + f'<span class="chip">{esc(PROVIDER_LABELS.get(candidate.get("provider"), candidate.get("provider") or ""))}</span>'
                + '</div>'
                + f'<p class="cand-value">{esc(candidate.get("value") or "")}</p>'
                + f"<blockquote>{esc(candidate.get('excerpt') or '')}</blockquote>"
                + '<div class="cand-foot">'
                + f'<a href="{esc(candidate.get("url") or "")}" rel="noreferrer noopener">{esc(candidate.get("url") or "")}</a>'
                + '</div></li>'
            )
        exec_parts.append('</ol>')
    else:
        exec_parts.append('<p class="empty-note">No named executives for this company.</p>')
    exec_parts.append('</section>')
    groups.append("".join(exec_parts))

    inv_entry = (data.get("fields") or {}).get("investors") or {}
    inv_candidates = inv_entry.get("candidates") or []
    inv_parts = ['<section class="evidence-group executive-field">']
    inv_parts.append(
        '<h2>Investors '
        f'<span class="badge status-{esc(inv_entry.get("status") or "unknown")}">'
        f'{esc(STATUS_LABELS.get(inv_entry.get("status") or "unknown", ""))}</span></h2>'
    )
    if inv_candidates:
        inv_parts.append('<ol class="candidates">')
        for candidate in inv_candidates:
            inv_parts.append(
                '<li class="candidate" data-selected="' + ("true" if candidate.get("selected") else "false") + '">'
                '<div class="cand-head">'
                + ('<span class="badge status-known">Selected</span>' if candidate.get("selected") else "")
                + f'<span class="chip">{esc(PROVIDER_LABELS.get(candidate.get("provider"), candidate.get("provider") or ""))}</span>'
                + '</div>'
                + f'<p class="cand-value">{esc(candidate.get("value") or "")}</p>'
                + f"<blockquote>{esc(candidate.get('excerpt') or '')}</blockquote>"
                + f'<a href="{esc(candidate.get("url") or "")}" rel="noreferrer noopener">{esc(candidate.get("url") or "")}</a>'
                + '</li>'
            )
        inv_parts.append('</ol>')
    else:
        inv_parts.append('<p class="empty-note">No named investors for this company.</p>')
    inv_parts.append('</section>')
    groups.append("".join(inv_parts))

    body = f"""<p class="eyebrow">Evidence</p>
<h1>Evidence for {esc(domain)}</h1>
<p class="lede">Every value the gathered pages support, in the order the selection rule ranks them. The selected value sits first.</p>
<div class="actions" style="margin-bottom:20px">
<a class="button secondary" href="/dossiers/{esc(domain)}">Back to dossier</a>
<a class="button secondary" href="/dossiers/{esc(domain)}/history">Change history</a>
</div>
{''.join(groups)}"""
    return _layout(
        f"Evidence — {domain}", body, user=user, active="dossiers"
    )


def contested_page(items: list[dict], *, user: dict | None = None) -> str:
    rows = []
    for item in items:
        domain = item["domain"]
        field = item["field"]
        entry = item["field_data"]
        value = entry.get("value")
        candidates = entry.get("candidates") or []
        distinct = []
        seen = set()
        for candidate in candidates:
            key = json.dumps(candidate.get("value"), sort_keys=True, ensure_ascii=False)
            if key in seen:
                continue
            seen.add(key)
            distinct.append(data_value(candidate.get("value")))
        rows.append(
            f'<li class="contested-item" data-testid="contested-item-{esc(domain)}-{field}" '
            f'data-value="{esc(data_value(value))}">'
            '<div class="ci-head">'
            f'<span class="ci-field">{esc(FIELD_LABELS[field])} <span class="hint">({esc(field)})</span></span>'
            f'<span class="badge status-contested">Contested</span>'
            "</div>"
            f'<p class="ci-values">Selected: <strong>{esc(value_text(field, value))}</strong> · '
            f"Values seen: {esc(', '.join(distinct))}</p>"
            f'<a href="/dossiers/{esc(domain)}/evidence">See the evidence for {esc(domain)}</a>'
            "</li>"
        )
    if rows:
        list_html = '<ul class="contested-list" data-testid="contested-list">' + "".join(rows) + "</ul>"
        empty_html = '<div class="empty-state" data-testid="empty-contested" hidden><strong>Nothing contested.</strong>Every field agrees so far.</div>'
    else:
        list_html = '<ul class="contested-list" data-testid="contested-list" hidden></ul>'
        empty_html = (
            '<div class="empty-state" data-testid="empty-contested"><strong>Nothing contested.</strong>'
            "Every field across all dossiers has a single agreed value.</div>"
        )
    body = f"""<p class="eyebrow">Disagreements</p>
<h1>Contested fields</h1>
<p class="lede">Fields where the evidence carries more than one value. The selected value is the highest-ranked source; the rest stay visible.</p>
{list_html}
{empty_html}"""
    return _layout("Contested fields", body, user=user, active="contested")


def history_page(domain: str, history: dict, *, user: dict | None = None) -> str:
    labels = dict(FIELD_LABELS)
    labels["executives"] = "Executive team"
    labels["investors"] = "Investors"
    order = list(FIELD_ORDER) + ["executives", "investors"]
    sections = []
    for field in order:
        entries = history.get(field) or []
        rows = []
        for entry in entries:
            value = entry.get("value")
            if field == "executives" and isinstance(value, list):
                shown = ", ".join(
                    f"{m.get('title', '').upper()} {m.get('name', '')}"
                    for m in value
                    if isinstance(m, dict)
                )
            elif field == "investors" and isinstance(value, list):
                shown = ", ".join(str(n) for n in value)
            else:
                shown = value_text(field, value) if field not in ("executives", "investors") else ("" if value is None else str(value))
            if value is None:
                shown = "Not found"
            rows.append(
                '<li class="history-entry">'
                f'<span class="badge status-{esc(entry.get("type")) if entry.get("type") in ("known", "contested", "unknown") else "known"}">{esc(entry.get("type"))}</span> '
                f'<span class="history-value">{esc(shown)}</span>'
                f'<span class="hint">true from {esc(entry.get("true_from") or "unknown")} · learned {esc(formatted_time(entry.get("learned_at")) or "unknown")}</span>'
                '</li>'
            )
        if rows:
            sections.append(
                f'<section class="evidence-group"><h2>{esc(labels.get(field, field))}</h2>'
                f'<ul class="list">{"".join(rows)}</ul></section>'
            )
        else:
            sections.append(
                f'<section class="evidence-group"><h2>{esc(labels.get(field, field))}</h2>'
                '<p class="empty-note">No recorded changes yet.</p></section>'
            )
    body = f"""<p class="eyebrow">History</p>
<h1>Change history for {esc(domain)}</h1>
<p class="lede">Every selected value the dossier has held, oldest first, with when the evidence says it took effect and when this service learned it.</p>
<div class="actions" style="margin-bottom:20px">
<a class="button secondary" href="/dossiers/{esc(domain)}">Back to dossier</a>
</div>
{''.join(sections)}"""
    return _layout(f"History — {domain}", body, user=user, active="dossiers")

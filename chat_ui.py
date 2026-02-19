"""
chat_ui.py  -  PGx GraphRAG  |  Drug-Gene Path Finder + Chatbot
Run:  python chat_ui.py
Open: http://localhost:7860
"""
from __future__ import annotations

import sys, os
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    os.environ.setdefault("PYTHONUTF8", "1")

import asyncio
import json
from contextlib import asynccontextmanager
from concurrent.futures import ThreadPoolExecutor
from typing import Any, List, Optional
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field, field_validator
import uvicorn

from GraphRag_PrimeKG import (
    get_driver, PGxRetriever, PGxLLM,
    search_drugs, path_drug_gene,
)
from cpic_scraper import get_most_recent_update

_state: dict = {}

# Seed pharmacogenes supported by the PGx subgraph
VALID_GENES: set[str] = {"CYP2D6", "CYP2C19", "CYP2C9", "SLCO1B1", "TPMT", "DPYD"}


# ── Pydantic request / response models ─────────────────────────────────────

class FindRequest(BaseModel):
    drug: str = Field(..., description="Drug name (case-sensitive, must exist in the graph)")
    gene: str = Field(..., description="Pharmacogene – one of CYP2D6, CYP2C19, CYP2C9, SLCO1B1, TPMT, DPYD")
    hops: int = Field(1, ge=1, le=3, description="Desired hop depth to start searching from (1-3)")
    max_hops: int = Field(3, ge=1, le=3, description="Maximum hop depth to escalate to if nothing found at `hops`")

    @field_validator("gene")
    @classmethod
    def gene_must_be_valid(cls, v: str) -> str:
        if v not in VALID_GENES:
            raise ValueError(f"gene must be one of {sorted(VALID_GENES)}")
        return v

    @field_validator("max_hops")
    @classmethod
    def max_must_gte_hops(cls, v: int, info) -> int:
        hops = info.data.get("hops", 1)
        if v < hops:
            raise ValueError("`max_hops` must be >= `hops`")
        return v


class FindResponse(BaseModel):
    drug: str
    gene: str
    requested_hop: int
    effective_hop: int
    escalated: bool              = Field(description="True when auto-escalation raised the hop level")
    found: bool
    paths: List[Any]             = Field(description="Path records at the effective hop level")
    shortest: List[Any]          = Field(description="Shortest-path records between drug and gene")
    message: str                 = Field(description="Human-readable summary")

@asynccontextmanager
async def lifespan(app: FastAPI):
    _state["driver"]    = get_driver()
    _state["retriever"] = PGxRetriever(_state["driver"], max_hops=3, limit=40)
    _state["llm"]       = PGxLLM()
    print("Neo4j connected | LLM ready")
    yield
    _state["driver"].close()

app = FastAPI(lifespan=lifespan)

# ─────────────────────────────────────────────────────────────────────────────
HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>PGx GraphRAG</title>
<style>
:root{
  --bg:#0d0d12;--surface:#16161f;--surface2:#1e1e2a;
  --border:#2a2a3c;--accent:#7c6cff;--accent2:#4ecdc4;
  --green:#22c55e;--orange:#f97316;--red:#ef4444;
  --text:#dde0f0;--muted:#5a5a7a;
  --hop1:#22c55e;--hop2:#a78bfa;--hop3:#f97316;
}
*{box-sizing:border-box;margin:0;padding:0;}
body{background:var(--bg);color:var(--text);font-family:'Segoe UI',system-ui,sans-serif;
     height:100vh;display:flex;flex-direction:column;overflow:hidden;}
header{padding:12px 24px;background:var(--surface);border-bottom:1px solid var(--border);
       display:flex;align-items:center;gap:12px;flex-shrink:0;}
.logo{font-size:1.1rem;font-weight:700;color:var(--accent);letter-spacing:.5px;}
.sub{font-size:.72rem;color:var(--muted);margin-top:2px;}
.tabs{margin-left:auto;display:flex;gap:4px;}
.tab{padding:6px 16px;border-radius:8px;border:1px solid var(--border);
     background:transparent;color:var(--muted);cursor:pointer;font-size:.82rem;transition:all .15s;}
.tab.active,.tab:hover{background:var(--accent);color:#fff;border-color:var(--accent);}
.panel{display:none;flex:1;overflow:hidden;}
.panel.active{display:flex;}
/* PATH FINDER */
#panel-path{flex-direction:column;}
.path-form{flex-shrink:0;padding:18px 32px 14px;background:var(--surface);
           border-bottom:1px solid var(--border);}
.form-row{display:flex;gap:12px;align-items:flex-end;flex-wrap:wrap;}
.field{display:flex;flex-direction:column;gap:5px;}
.field label{font-size:.73rem;color:var(--muted);font-weight:700;letter-spacing:.4px;text-transform:uppercase;}
.ac-wrap{position:relative;}
#drug-inp{width:280px;background:var(--bg);color:var(--text);border:1px solid var(--border);
          border-radius:8px;padding:9px 12px;font-size:.88rem;outline:none;transition:border .2s;}
#drug-inp:focus{border-color:var(--accent);}
.ac-list{position:absolute;top:calc(100% + 4px);left:0;width:100%;background:var(--surface2);
         border:1px solid var(--border);border-radius:8px;overflow:hidden;z-index:99;
         display:none;box-shadow:0 8px 24px #0007;}
.ac-item{padding:8px 12px;font-size:.85rem;cursor:pointer;transition:background .1s;}
.ac-item:hover,.ac-item.sel{background:var(--accent);color:#fff;}
#gene-sel{background:var(--bg);color:var(--text);border:1px solid var(--border);
          border-radius:8px;padding:9px 12px;font-size:.88rem;cursor:pointer;outline:none;min-width:160px;}
#gene-sel:focus{border-color:var(--accent);}
.hop-btns{display:flex;gap:4px;}
.hop-btn{width:36px;height:36px;border-radius:8px;border:1px solid var(--border);
         background:transparent;color:var(--muted);font-size:.82rem;cursor:pointer;
         font-weight:700;transition:all .15s;}
.hop-btn.active{background:var(--accent);color:#fff;border-color:var(--accent);}
#find-btn{padding:9px 24px;background:var(--accent);color:#fff;border:none;
          border-radius:8px;font-size:.88rem;font-weight:700;cursor:pointer;transition:opacity .2s;}
#find-btn:hover{opacity:.85;}
#find-btn:disabled{opacity:.4;cursor:default;}
.path-results{flex:1;overflow-y:auto;padding:24px 32px;}
.path-results::-webkit-scrollbar{width:4px;}
.path-results::-webkit-scrollbar-thumb{background:var(--border);border-radius:2px;}
.result-header{display:flex;align-items:center;gap:10px;margin-bottom:18px;}
.result-header h2{font-size:1rem;font-weight:700;}
.badge{display:inline-flex;align-items:center;gap:5px;padding:3px 10px;border-radius:20px;font-size:.72rem;font-weight:700;}
.badge.drug{background:#1a2a3a;color:#60a5fa;border:1px solid #60a5fa;}
.badge.gene{background:#1a2a1a;color:var(--accent2);border:1px solid var(--accent2);}
.badge.found{background:#1a2a1a;color:var(--green);border:1px solid var(--green);}
.badge.notfound{background:#2a1a1a;color:var(--red);border:1px solid var(--red);}
.hop-section{margin-bottom:20px;}
.hop-title{display:flex;align-items:center;gap:8px;margin-bottom:10px;}
.hop-dot{width:10px;height:10px;border-radius:50%;}
.hop-dot.h1{background:var(--hop1)}.hop-dot.h2{background:var(--hop2)}
.hop-dot.h3{background:var(--hop3)}.hop-dot.sp{background:var(--accent)}
.hop-label{font-size:.78rem;font-weight:700;text-transform:uppercase;letter-spacing:.5px;}
.hop-label.h1{color:var(--hop1)}.hop-label.h2{color:var(--hop2)}
.hop-label.h3{color:var(--hop3)}.hop-label.sp{color:var(--accent)}
.hop-count{font-size:.72rem;color:var(--muted);}
.path-card{background:var(--surface2);border:1px solid var(--border);border-radius:8px;
           padding:10px 14px;margin-bottom:6px;font-size:.82rem;line-height:1.8;font-family:monospace;}
.path-card .node{color:#60a5fa;font-weight:600;}
.path-card .rel{color:var(--muted);font-size:.75rem;padding:0 3px;}
.path-card .mid{color:#c4b5fd;}
.path-card .type{color:var(--muted);font-size:.72rem;}
.path-card .gene-name{color:var(--accent2);font-weight:700;}
.path-card .drug-name{color:#60a5fa;font-weight:700;}
.no-path{text-align:center;padding:48px;color:var(--muted);font-size:.9rem;}
.no-path .icon{font-size:2.5rem;margin-bottom:12px;}
/* CHATBOT */
#panel-chat{flex-direction:column;}
#chat-msgs{flex:1;overflow-y:auto;padding:20px 10vw;display:flex;flex-direction:column;gap:14px;}
#chat-msgs::-webkit-scrollbar{width:4px;}
#chat-msgs::-webkit-scrollbar-thumb{background:var(--border);border-radius:2px;}
.msg{display:flex;gap:10px;max-width:800px;animation:fadein .2s ease;}
.msg.user{align-self:flex-end;flex-direction:row-reverse;}
@keyframes fadein{from{opacity:0;transform:translateY(6px)}to{opacity:1}}
.av{width:30px;height:30px;border-radius:50%;display:flex;align-items:center;
    justify-content:center;font-size:.8rem;flex-shrink:0;margin-top:2px;}
.msg.user .av{background:var(--accent);}.msg.bot .av{background:#2a3a4a;}
.bubble{padding:11px 15px;border-radius:10px;line-height:1.65;font-size:.88rem;white-space:pre-wrap;}
.msg.user .bubble{background:var(--accent);color:#fff;border-bottom-right-radius:3px;}
.msg.bot  .bubble{background:var(--surface2);border:1px solid var(--border);border-bottom-left-radius:3px;}
.bubble code{background:#111;padding:1px 5px;border-radius:4px;font-family:monospace;font-size:.78rem;}
.hb{display:inline-block;padding:1px 7px;border-radius:10px;font-size:.7rem;font-weight:700;}
.hb1{background:#0d2010;color:var(--hop1);border:1px solid var(--hop1);}
.hb2{background:#150d2a;color:var(--hop2);border:1px solid var(--hop2);}
.hb3{background:#2a1205;color:var(--hop3);border:1px solid var(--hop3);}
.ctx-btn{font-size:.7rem;color:var(--muted);cursor:pointer;text-decoration:underline dotted;display:inline-block;margin-top:5px;}
.ctx-box{display:none;margin-top:8px;padding:8px 10px;background:#0a0a0f;border:1px solid var(--border);
         border-radius:6px;font-size:.72rem;font-family:monospace;color:#6678aa;white-space:pre-wrap;max-height:260px;overflow-y:auto;}
.thinking{display:flex;gap:4px;align-items:center;padding:11px 15px;}
.dot{width:6px;height:6px;border-radius:50%;background:var(--accent);animation:bop .9s infinite;}
.dot:nth-child(2){animation-delay:.15s;}.dot:nth-child(3){animation-delay:.3s;}
@keyframes bop{0%,80%,100%{transform:scale(.6)}40%{transform:scale(1)}}
.chat-bar{padding:14px 10vw;background:var(--surface);border-top:1px solid var(--border);}
.chat-row{display:flex;gap:8px;}
#chat-inp{flex:1;background:var(--bg);color:var(--text);border:1px solid var(--border);
          border-radius:8px;padding:10px 14px;font-size:.88rem;resize:none;
          outline:none;font-family:inherit;max-height:120px;transition:border .2s;}
#chat-inp:focus{border-color:var(--accent);}
#chat-send{background:var(--accent);color:#fff;border:none;border-radius:8px;
           padding:10px 20px;font-weight:700;font-size:.88rem;cursor:pointer;transition:opacity .2s;}
#chat-send:hover{opacity:.85;}#chat-send:disabled{opacity:.4;cursor:default;}
.chat-hint{font-size:.7rem;color:var(--muted);margin-top:6px;}
.chat-hops{display:flex;align-items:center;gap:6px;margin-bottom:8px;}
.chat-hops span{font-size:.72rem;color:var(--muted);}
</style>
</head>
<body>

<header>
  <div>
    <div class="logo">PGx GraphRAG</div>
    <div class="sub">PrimeKG &middot; CYP2D6 &middot; CYP2C19 &middot; CYP2C9 &middot; SLCO1B1 &middot; TPMT &middot; DPYD</div>
  </div>
  <div class="tabs">
    <button class="tab active" onclick="switchTab('path',this)">&#x2316; Path Finder</button>
    <button class="tab"        onclick="switchTab('chat',this)">&#x1F4AC; Chatbot</button>
  </div>
</header>

<!-- PATH FINDER -->
<div class="panel active" id="panel-path">
  <div class="path-form">
    <div class="form-row">
      <div class="field">
        <label>Drug</label>
        <div class="ac-wrap">
          <input id="drug-inp" placeholder="Search drug name..." autocomplete="off"/>
          <div class="ac-list" id="ac-list"></div>
        </div>
      </div>
      <div class="field">
        <label>Pharmacogene</label>
        <select id="gene-sel">
          <option value="">&#x2013; select gene &#x2013;</option>
          <option>CYP2D6</option><option>CYP2C19</option><option>CYP2C9</option>
          <option>SLCO1B1</option><option>TPMT</option><option>DPYD</option>
        </select>
      </div>
      <div class="field">
        <label>Max hops</label>
        <div class="hop-btns">
          <button class="hop-btn" data-h="1" onclick="setHop(1)">1</button>
          <button class="hop-btn" data-h="2" onclick="setHop(2)">2</button>
          <button class="hop-btn active" data-h="3" onclick="setHop(3)">3</button>
        </div>
      </div>
      <button id="find-btn" onclick="findPath()">Find Path</button>
    </div>
  </div>
  <div class="path-results" id="path-results">
    <div class="no-path">
      <div class="icon">&#x2B21;</div>
      <div>Search a drug and select a gene to explore their connections</div>
    </div>
  </div>
</div>

<!-- CHATBOT -->
<div class="panel" id="panel-chat">
  <div id="chat-msgs">
    <div class="msg bot">
      <div class="av">&#x2B21;</div>
      <div><div class="bubble">Hi! Ask me anything about drug-gene interactions, metabolic paths, or clinical risks.

Examples:
  - Which drugs interact with CYP2D6?
  - What are the 3-hop connections between CYP2C19 and Clopidogrel?
  - What phenotypes are associated with DPYD?</div></div>
    </div>
  </div>
  <div class="chat-bar">
    <div class="chat-hops">
      <span>Hop depth:</span>
      <button class="hop-btn" data-ch="1" onclick="setChatHop(1)">1</button>
      <button class="hop-btn" data-ch="2" onclick="setChatHop(2)">2</button>
      <button class="hop-btn active" data-ch="3" onclick="setChatHop(3)">3</button>
      <span style="margin-left:10px">
        <label style="font-size:.72rem;color:var(--muted);cursor:pointer;">
          <input type="checkbox" id="show-ctx" style="margin-right:4px"/>Show graph context
        </label>
      </span>
    </div>
    <div class="chat-row">
      <textarea id="chat-inp" rows="1" placeholder="Ask about genes, drugs, pathways..."></textarea>
      <button id="chat-send" onclick="sendChat()">Send</button>
    </div>
    <div class="chat-hint">Enter to send &nbsp;&middot;&nbsp; Shift+Enter for new line</div>
  </div>
</div>

<script>
// ── tabs ──────────────────────────────────────────────────────────────────────
function switchTab(tab,btn){
  document.querySelectorAll('.panel').forEach(p=>p.classList.remove('active'));
  document.querySelectorAll('.tab').forEach(t=>t.classList.remove('active'));
  document.getElementById('panel-'+tab).classList.add('active');
  btn.classList.add('active');
}

// ── PATH FINDER ───────────────────────────────────────────────────────────────
let selectedDrug='', selectedHop=3, acFocus=-1;
let acTimeout;
const drugInp=document.getElementById('drug-inp');
const acList =document.getElementById('ac-list');

drugInp.addEventListener('input',()=>{
  selectedDrug='';
  clearTimeout(acTimeout);
  const q=drugInp.value.trim();
  if(q.length<2){acList.style.display='none';return;}
  acTimeout=setTimeout(()=>fetchAC(q),180);
});
drugInp.addEventListener('keydown',e=>{
  const items=acList.querySelectorAll('.ac-item');
  if(e.key==='ArrowDown'){acFocus=Math.min(acFocus+1,items.length-1);hlAC(items);e.preventDefault();}
  else if(e.key==='ArrowUp'){acFocus=Math.max(acFocus-1,-1);hlAC(items);e.preventDefault();}
  else if(e.key==='Enter'&&acFocus>=0){selectDrug(items[acFocus].textContent);e.preventDefault();}
  else if(e.key==='Escape'){acList.style.display='none';}
});
document.addEventListener('click',e=>{if(!e.target.closest('.ac-wrap'))acList.style.display='none';});

async function fetchAC(q){
  const res=await fetch('/drugs?q='+encodeURIComponent(q));
  const data=await res.json();
  acFocus=-1;
  if(!data.length){acList.style.display='none';return;}
  acList.innerHTML=data.map(d=>`<div class="ac-item" onclick="selectDrug('${escJS(d)}')">${escHtml(d)}</div>`).join('');
  acList.style.display='block';
}
function hlAC(items){
  items.forEach((el,i)=>el.classList.toggle('sel',i===acFocus));
  if(acFocus>=0)items[acFocus].scrollIntoView({block:'nearest'});
}
function selectDrug(name){selectedDrug=name;drugInp.value=name;acList.style.display='none';}

function setHop(h){
  selectedHop=h;
  document.querySelectorAll('.hop-btn[data-h]').forEach(b=>b.classList.toggle('active',parseInt(b.dataset.h)===h));
}

async function findPath(){
  const drug=selectedDrug||drugInp.value.trim();
  const gene=document.getElementById('gene-sel').value;
  if(!drug){alert('Please select a drug from the autocomplete list.');return;}
  if(!gene){alert('Please select a gene.');return;}
  const btn=document.getElementById('find-btn');
  btn.disabled=true;btn.textContent='Finding...';
  const res=await fetch('/path',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({drug,gene,max_hops:selectedHop})});
  const data=await res.json();
  btn.disabled=false;btn.textContent='Find Path';
  renderPath(data);
}

function renderPath(d){
  const el=document.getElementById('path-results');
  if(!d.found){
    el.innerHTML=`<div class="result-header"><h2>No path found</h2>
      <span class="badge drug">${escHtml(d.drug)}</span><span style="color:var(--muted)">&rarr;</span>
      <span class="badge gene">${escHtml(d.gene)}</span>
      <span class="badge notfound">Not connected within ${selectedHop} hop${selectedHop!==1?'s':''}</span></div>
      <div class="no-path"><div class="icon">&#x2205;</div>
      <div>No pathway found between <strong>${escHtml(d.drug)}</strong> and <strong>${escHtml(d.gene)}</strong> within ${selectedHop} hops.</div></div>`;
    return;
  }
  let html=`<div class="result-header"><h2>Pathways found</h2>
    <span class="badge drug">${escHtml(d.drug)}</span>
    <span style="color:var(--muted)">&rarr;</span>
    <span class="badge gene">${escHtml(d.gene)}</span>
    <span class="badge found">Connected</span></div>`;

  if(d.shortest&&d.shortest.length){
    html+=section('sp','Shortest Path',d.shortest.map(r=>{
      const steps=r.path_nodes.map((n,i)=>{
        const rel=r.path_rels[i]?` <span class="rel">[${escHtml(r.path_rels[i])}]&rarr;</span> `:'';
        const cls=(n===d.drug)?'drug-name':(n===d.gene)?'gene-name':'mid';
        return `<span class="${cls}">${escHtml(n)}</span><span class="type">(${escHtml(r.path_types[i])})</span>${rel}`;
      }).join('');
      return `<div class="path-card">${steps}<span class="badge" style="background:#1a1a2a;color:var(--accent);border:1px solid var(--accent);margin-left:8px">${r.hops} hop${r.hops!==1?'s':''}</span></div>`;
    }));
  }
  if(d.hop1&&d.hop1.length){
    html+=section('h1','HOP 1 &nbsp;Direct [DRUG_PROTEIN]',d.hop1.map(r=>
      `<div class="path-card"><span class="gene-name">${escHtml(r.gene)}</span>
       <span class="rel"> --[${escHtml(r.rel)}]-- </span>
       <span class="drug-name">${escHtml(r.drug)}</span></div>`));
  }
  if(d.hop2&&d.hop2.length){
    html+=section('h2','HOP 2 &nbsp;Gene &rarr; Intermediate &rarr; Drug',d.hop2.map(r=>
      `<div class="path-card"><span class="gene-name">${escHtml(r.gene)}</span>
       <span class="rel"> --[${escHtml(r.rel1)}]--&gt; </span>
       <span class="mid">${escHtml(r.intermediate)}</span><span class="type">(${escHtml(r.mid_type)})</span>
       <span class="rel"> --[${escHtml(r.rel2)}]--&gt; </span>
       <span class="drug-name">${escHtml(r.drug)}</span></div>`));
  }
  if(d.hop3&&d.hop3.length){
    html+=section('h3','HOP 3 &nbsp;Gene &rarr; n1 &rarr; n2 &rarr; Drug',d.hop3.map(r=>
      `<div class="path-card"><span class="gene-name">${escHtml(r.gene)}</span>
       <span class="rel"> --[${escHtml(r.rel1)}]--&gt; </span>
       <span class="mid">${escHtml(r.hop1_node)}</span><span class="type">(${escHtml(r.hop1_type)})</span>
       <span class="rel"> --[${escHtml(r.rel2)}]--&gt; </span>
       <span class="mid">${escHtml(r.hop2_node)}</span><span class="type">(${escHtml(r.hop2_type)})</span>
       <span class="rel"> --[${escHtml(r.rel3)}]--&gt; </span>
       <span class="drug-name">${escHtml(r.drug)}</span></div>`));
  }
  el.innerHTML=html;
}

function section(cls,title,cards){
  return `<div class="hop-section">
    <div class="hop-title">
      <div class="hop-dot ${cls}"></div>
      <span class="hop-label ${cls}">${title}</span>
      <span class="hop-count">${cards.length} result${cards.length!==1?'s':''}</span>
    </div>${cards.join('')}</div>`;
}

// ── CHATBOT ───────────────────────────────────────────────────────────────────
let chatHop=3,chatBusy=false;
function setChatHop(h){
  chatHop=h;
  document.querySelectorAll('.hop-btn[data-ch]').forEach(b=>b.classList.toggle('active',parseInt(b.dataset.ch)===h));
}
const chatInp=document.getElementById('chat-inp');
const chatSend=document.getElementById('chat-send');
chatInp.addEventListener('input',()=>{chatInp.style.height='auto';chatInp.style.height=Math.min(chatInp.scrollHeight,120)+'px';});
chatInp.addEventListener('keydown',e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();sendChat();}});

function addMsg(role,text,ctx=''){
  const msgs=document.getElementById('chat-msgs');
  const div=document.createElement('div');div.className=`msg ${role}`;
  const av=role==='user'?'&#x1F9EC;':'&#x2B21;';
  let ctxHtml='';
  if(ctx){const id='c'+Date.now();
    ctxHtml=`<span class="ctx-btn" onclick="toggleCtx('${id}')">&#x25B6; graph context</span>
             <div class="ctx-box" id="${id}">${escHtml(ctx)}</div>`;}
  div.innerHTML=`<div class="av">${av}</div>
    <div><div class="bubble">${fmt(text)}</div>${ctxHtml}</div>`;
  msgs.appendChild(div);
  msgs.scrollTo({top:msgs.scrollHeight,behavior:'smooth'});
}
function addThinking(){
  const msgs=document.getElementById('chat-msgs');
  const div=document.createElement('div');div.className='msg bot';div.id='thinking';
  div.innerHTML=`<div class="av">&#x2B21;</div>
    <div><div class="bubble thinking"><div class="dot"></div><div class="dot"></div><div class="dot"></div></div></div>`;
  msgs.appendChild(div);msgs.scrollTo({top:msgs.scrollHeight,behavior:'smooth'});
}
function toggleCtx(id){
  const el=document.getElementById(id);const tog=el.previousElementSibling;
  const open=el.style.display==='block';el.style.display=open?'none':'block';
  tog.innerHTML=(open?'&#x25B6;':'&#x25BC;')+' graph context';
}
async function sendChat(){
  if(chatBusy)return;
  const q=chatInp.value.trim();if(!q)return;
  chatInp.value='';chatInp.style.height='auto';
  chatBusy=true;chatSend.disabled=true;
  addMsg('user',q);addThinking();
  try{
    const res=await fetch('/chat',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({question:q,hops:chatHop})});
    const data=await res.json();
    document.getElementById('thinking')?.remove();
    addMsg('bot',data.answer,document.getElementById('show-ctx').checked?data.context:'');
  }catch(e){document.getElementById('thinking')?.remove();addMsg('bot','Error: '+e.message);}
  chatBusy=false;chatSend.disabled=false;chatInp.focus();
}

// ── utils ─────────────────────────────────────────────────────────────────────
function escHtml(s){return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');}
function escJS(s){return s.replace(/\\/g,'\\\\').replace(/'/g,"\\'");}
function fmt(txt){
  return escHtml(txt)
    .replace(/\bHOP 1\b/g,'<span class="hb hb1">HOP 1</span>')
    .replace(/\bHOP 2\b/g,'<span class="hb hb2">HOP 2</span>')
    .replace(/\bHOP 3\b/g,'<span class="hb hb3">HOP 3</span>')
    .replace(/\b(CYP2D6|CYP2C19|CYP2C9|SLCO1B1|DPYD|TPMT)\b/g,'<code>$1</code>')
    .replace(/\[([A-Z_]+)\]/g,'<code>[$1]</code>');
}
</script>
</body>
</html>"""


# ─────────────────────────────────────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
async def index():
    return HTML


@app.get("/drugs")
async def drugs_ac(q: str = ""):
    if len(q) < 2:
        return []
    return search_drugs(_state["driver"], q)


@app.post("/path")
async def path_endpoint(req: Request):
    """Legacy endpoint kept for the UI tab. Calls the smart path finder."""
    body     = await req.json()
    drug     = body.get("drug", "").strip()
    gene     = body.get("gene", "").strip()
    hops     = int(body.get("hops",     1))
    max_hops = int(body.get("max_hops", 3))
    if not drug or not gene:
        return {"found": False, "drug": drug, "gene": gene,
                "paths": [], "shortest": [], "message": "drug and gene are required"}
    return path_drug_gene(_state["driver"], drug, gene, hops=hops, max_hops=max_hops)


@app.post("/find", response_model=FindResponse, summary="Smart drug-gene path finder")
async def find_endpoint(body: FindRequest) -> FindResponse:
    """
    Find the connection path between a drug and a pharmacogene.

    - Starts searching at `hops`.
    - If no paths are found, automatically escalates to `hops+1`, `hops+2`, …
      up to `max_hops` (max 3).
    - Returns the first hop level where paths exist, plus the shortest-path
      between the two nodes regardless of hop level.
    """
    result = path_drug_gene(
        _state["driver"],
        body.drug,
        body.gene,
        hops=body.hops,
        max_hops=body.max_hops,
    )

    if not result["found"]:
        msg = f"No connection found between '{body.drug}' and '{body.gene}' within {body.max_hops} hop(s)."
    elif result["escalated"]:
        msg = (
            f"No paths at hop {body.hops}. "
            f"Escalated to hop {result['effective_hop']}: "
            f"found {len(result['paths'])} path(s)."
        )
    else:
        msg = (
            f"Found {len(result['paths'])} path(s) between '{body.drug}' and "
            f"'{body.gene}' at hop {result['effective_hop']}."
        )

    return FindResponse(
        drug=result["drug"],
        gene=result["gene"],
        requested_hop=result["requested_hop"],
        effective_hop=result["effective_hop"],
        escalated=result["escalated"],
        found=result["found"],
        paths=result["paths"],
        shortest=result["shortest"],
        message=msg,
    )


@app.post("/pgx-updates", summary="Scrape most-recent CPIC update for every drug in a PGx result JSON")
async def pgx_updates_endpoint(req: Request):
    """
    Accepts the full PGx engine JSON (outputv2.json schema).
    For every result entry that has a `guideline_url`, scrapes the CPIC page
    and returns the most recent update block.

    Request body: the raw JSON object (results array).
    Response: list of { drug, guideline_url, label, text, pmids } objects.
    """
    body = await req.json()
    results = body.get("results", [])

    def _fetch(drug_name: str, url: str) -> dict:
        try:
            upd = get_most_recent_update(url)
            if upd:
                return {
                    "drug": drug_name,
                    "guideline_url": url,
                    "label": upd["label"],
                    "text": upd["text"],
                    "pmids": upd["pmids"],
                }
            return {
                "drug": drug_name,
                "guideline_url": url,
                "label": None,
                "text": "No updates found after 'Updates since publication:' on this page.",
                "pmids": [],
            }
        except Exception as exc:
            return {
                "drug": drug_name,
                "guideline_url": url,
                "label": None,
                "text": f"Error scraping page: {exc}",
                "pmids": [],
            }

    loop = asyncio.get_event_loop()
    tasks = []
    with ThreadPoolExecutor() as pool:
        for entry in results:
            drug_name = entry.get("drug", "unknown")
            url = (entry.get("cpic_metadata") or {}).get("guideline_url")
            if url:
                tasks.append(loop.run_in_executor(pool, _fetch, drug_name, url))

        updates = await asyncio.gather(*tasks)

    return {"updates": list(updates)}


@app.post("/chat")
async def chat_endpoint(req: Request):
    body     = await req.json()
    question = body.get("question", "").strip()
    hops     = int(body.get("hops", 3))
    if not question:
        return {"answer": "Please ask a question.", "context": ""}
    retriever: PGxRetriever = _state["retriever"]
    llm: PGxLLM             = _state["llm"]
    retriever.max_hops = hops
    ret = retriever.search(question)
    ctx = ret.items[0].content if ret.items else "(no context)"
    prompt = (
        f"GRAPH CONTEXT:\n{ctx}\n\n"
        f"QUESTION: {question}\n\n"
        "Answer using ONLY the graph context above. "
        "Reference gene names, drug names, hop distances (HOP 1 / HOP 2 / HOP 3), "
        "and relationship types like [DRUG_PROTEIN], [PROTEIN_PROTEIN]. "
        "Be concise and clinically precise."
    )
    answer = llm.invoke(prompt).content
    return {"answer": answer, "context": ctx}


if __name__ == "__main__":
    port = int(os.getenv("UI_PORT", 7860))
    print(f"\n  PGx GraphRAG UI  ->  http://localhost:{port}\n")
    uvicorn.run(app, host="0.0.0.0", port=port)
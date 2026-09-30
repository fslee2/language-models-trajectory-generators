#!/usr/bin/env python3
"""Render a self-contained local HTML dashboard from a JSON state file."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def read_state(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8-sig") as stream:
        state = json.load(stream)
    if not isinstance(state, dict):
        raise ValueError("The JSON root must be an object.")
    for key in ("tasks", "questions", "outputs", "blockers", "memory"):
        value = state.get(key, [])
        if not isinstance(value, list):
            raise ValueError(f"'{key}' must be a JSON array.")
        if not all(isinstance(item, dict) for item in value):
            raise ValueError(f"Every item in '{key}' must be an object.")
        state[key] = value
    for key in ("title", "summary", "status"):
        value = state.get(key, "")
        if not isinstance(value, str):
            raise ValueError(f"'{key}' must be a string.")
        state[key] = value
    return state


def render(state: dict[str, Any]) -> str:
    # Escaping '<' prevents user text from terminating the embedded script tag.
    data = json.dumps(state, ensure_ascii=False).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    return TEMPLATE.replace("__STATE_JSON__", data)


TEMPLATE = r'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="dark">
<title>Research task dashboard</title>
<style>
:root{color-scheme:dark;--bg:#080d17;--panel:#101827;--panel2:#0c1421;--line:#202d40;--text:#e8eef7;--muted:#8c9ab0;--accent:#9c8cff;--green:#57d6aa;--amber:#f1bd68;--red:#ff7b83;--blue:#7dc7ff}
*{box-sizing:border-box}body{margin:0;background:radial-gradient(ellipse at 50% -25%,#203755 0,#0b1220 50%,var(--bg) 90%);color:var(--text);font:14px/1.5 Inter,ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif;min-height:100vh;padding:26px 20px 44px}
main{max-width:1180px;margin:auto}.top{display:flex;justify-content:space-between;align-items:flex-start;gap:24px;margin:4px 0 22px}.eyebrow{color:var(--blue);font-size:11px;letter-spacing:.16em;text-transform:uppercase;font-weight:700}.title{margin:6px 0 5px;font-size:clamp(22px,3.2vw,34px);line-height:1.15;letter-spacing:-.035em}.summary{margin:0;color:#aab7ca;max-width:760px}.live{white-space:nowrap;text-align:right;color:var(--muted);font-size:12px}.live strong{display:block;color:var(--text);font-size:20px;font-variant-numeric:tabular-nums}.badge{display:inline-flex;align-items:center;gap:7px;padding:6px 10px;border:1px solid var(--line);border-radius:99px;background:#101a2a;color:var(--green);font-size:12px;font-weight:700}.dot{width:7px;height:7px;border-radius:50%;background:currentColor;box-shadow:0 0 12px currentColor}
.metrics{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px;margin:18px 0}.metric,.panel{background:linear-gradient(150deg,rgba(18,28,44,.96),rgba(11,18,30,.96));border:1px solid var(--line);border-radius:13px}.metric{padding:13px 15px}.label{font-size:10px;color:var(--muted);text-transform:uppercase;letter-spacing:.12em;font-weight:700}.value{font-size:21px;font-weight:700;margin-top:3px}.sub{font-size:11px;color:var(--muted)}.layout{display:grid;grid-template-columns:minmax(0,1.35fr) minmax(290px,.85fr);gap:12px}.stack{display:grid;gap:12px;align-content:start}.panel{padding:16px}.panelhead{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:12px}.panel h2{font-size:14px;margin:0;letter-spacing:.01em}.count{color:var(--muted);font-size:11px}.progress{height:5px;background:#202c3d;border-radius:8px;overflow:hidden;margin:3px 0 13px}.progress span{height:100%;display:block;background:linear-gradient(90deg,#59d6ac,#a18cff);border-radius:inherit}.rows{display:grid;gap:7px}.row{display:grid;grid-template-columns:18px minmax(0,1fr) auto;align-items:start;gap:9px;padding:9px 10px;background:rgba(5,10,18,.38);border:1px solid rgba(37,52,73,.55);border-radius:9px}.rowtext{min-width:0}.rowtitle{font-weight:600}.detail{color:var(--muted);font-size:12px;margin-top:2px;overflow-wrap:anywhere}.check{color:var(--green);font-weight:bold}.state{font-size:10px;text-transform:uppercase;letter-spacing:.05em;color:var(--muted);white-space:nowrap;padding:2px 6px;border-radius:6px;background:#172235}.state.done{color:var(--green)}.state.in-progress{color:var(--blue)}.state.blocked{color:var(--red)}.state.to-do,.state.todo{color:#aab7ca}.question{border-left:2px solid var(--amber);padding-left:10px}.question .default{color:var(--amber);font-size:11px;margin-top:5px}.itemmeta{font-size:10px;color:#74839a;margin-top:4px}.empty{padding:14px;text-align:center;color:#74839a;background:rgba(5,10,18,.25);border-radius:8px;font-size:12px}.blocker{border-left:2px solid var(--red);padding-left:10px}.output{border-left:2px solid var(--green);padding-left:10px}.foot{color:#65738a;font-size:10px;text-align:right;margin-top:12px}
.stack .row{grid-template-columns:minmax(0,1fr)}
.memory-panel{margin-top:12px}.memory-tools{display:flex;flex-wrap:wrap;gap:8px;align-items:center}.memory-tools button,.memory-actions button{border:1px solid var(--line);border-radius:7px;background:#152237;color:var(--text);padding:5px 9px;font:inherit;cursor:pointer}.memory-tools button.active,.memory-actions button.active{border-color:var(--blue);background:#17344d;color:#bce7ff}.memory-tools button:hover,.memory-actions button:hover{border-color:var(--accent)}.memory-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:9px}.memory-card{min-width:0;background:rgba(5,10,18,.38);border:1px solid var(--line);border-radius:9px;padding:12px}.memory-card[data-choice="keep"]{border-left:3px solid var(--green)}.memory-card[data-choice="skip"]{border-left:3px solid var(--muted)}.memory-title{font-weight:700}.memory-source{font-size:10px;color:var(--muted);margin-top:3px;overflow-wrap:anywhere}.memory-body{font-size:12px;color:#bcc9da;margin:8px 0;overflow-wrap:anywhere}.memory-actions{display:flex;gap:6px;flex-wrap:wrap}.memory-note{color:var(--muted);font-size:11px;margin:8px 0 12px}
@media(max-width:760px){body{padding:18px 12px 30px}.top{align-items:flex-start}.live{font-size:10px}.live strong{font-size:16px}.metrics{grid-template-columns:repeat(2,minmax(0,1fr))}.layout{grid-template-columns:1fr}.panel{padding:13px}}
@media(max-width:760px){.memory-grid{grid-template-columns:1fr}}
</style>
</head>
<body><main>
<header class="top"><div><div class="eyebrow">Research workspace · Live status</div><h1 class="title" id="title"></h1><p class="summary" id="summary"></p></div><div class="live"><span class="badge"><i class="dot"></i><span id="overall"></span></span><strong id="clock">--:--:--</strong><span id="date"></span></div></header>
<section class="metrics" id="metrics"></section>
<div class="layout"><section class="panel"><div class="panelhead"><h2>Tasks</h2><span class="count" id="task-count"></span></div><div class="progress"><span id="progress"></span></div><div class="rows" id="tasks"></div></section><div class="stack"><section class="panel"><div class="panelhead"><h2>Questions and defaults</h2><span class="count" id="question-count"></span></div><div class="rows" id="questions"></div></section><section class="panel"><div class="panelhead"><h2>Recent outputs</h2><span class="count" id="output-count"></span></div><div class="rows" id="outputs"></div></section><section class="panel"><div class="panelhead"><h2>Blockers</h2><span class="count" id="blocker-count"></span></div><div class="rows" id="blockers"></div></section></div></div>
<section class="panel memory-panel"><div class="panelhead"><h2>Memory · 当前上下文</h2><span class="count" id="memory-count"></span></div><p class="memory-note">摘要来自项目 memory；“记住 / 暂不使用”只筛选此页面的工作上下文，选择保存在本机浏览器中，不会改写原文件。</p><div class="memory-tools"><button type="button" data-filter="all" class="active">全部</button><button type="button" data-filter="keep">记住</button><button type="button" data-filter="skip">暂不使用</button><button type="button" data-filter="undecided">未决定</button><button type="button" id="memory-export">导出选择</button></div><div class="memory-grid" id="memory-cards"></div></section>
<div class="foot">Local dashboard · refreshes every 10 seconds</div>
</main><script>
const state=__STATE_JSON__;
const el=(id)=>document.getElementById(id);
const text=(node,value)=>{node.textContent=value||''};
const item=(tag,cls)=>{const n=document.createElement(tag);n.className=cls;return n};
const escState=(s)=>String(s||'to do').toLowerCase().replace(/\s+/g,'-');
function empty(container,message){const n=item('div','empty');n.textContent=message;container.append(n)}
function renderList(id,items,kind){const host=el(id);host.replaceChildren();if(!items.length){empty(host,kind==='tasks'?'No tasks added yet.':'Nothing to show.');return}
for(const x of items){const row=item('div','row');if(kind==='tasks'){const mark=item('div','check');mark.textContent=/^(done|complete|completed)$/i.test(x.status||'')?'✓':'○';row.append(mark);const body=item('div','rowtext');const name=item('div','rowtitle');name.textContent=x.name||x.title||'Untitled task';body.append(name);if(x.detail||x.description){const d=item('div','detail');d.textContent=x.detail||x.description;body.append(d)}row.append(body);const badge=item('span','state '+escState(x.status));badge.textContent=x.status||'To do';row.append(badge)}
else {const body=item('div','rowtext '+(kind==='questions'?'question':kind==='outputs'?'output':'blocker'));const name=item('div','rowtitle');name.textContent=x.prompt||x.name||x.title||x.text||'Item';body.append(name);const secondary=x.default||x.summary||x.detail||x.path||x.answer;if(secondary){const d=item(kind==='questions'?'div':'div',kind==='questions'?'default':'detail');d.textContent=(kind==='questions'?'Working default: ':'')+secondary;body.append(d)}if(x.time||x.status){const m=item('div','itemmeta');m.textContent=[x.time,x.status].filter(Boolean).join(' · ');body.append(m)}row.append(body)}host.append(row)}}
text(el('title'),state.title||'Long task dashboard');text(el('summary'),state.summary||'Progress, decisions, outputs, and open blockers.');text(el('overall'),state.status||'In progress');
const tasks=state.tasks||[],done=tasks.filter(x=>/^(done|complete|completed)$/i.test(x.status||'')).length, pct=tasks.length?Math.round(done*100/tasks.length):0;
el('progress').style.width=pct+'%';text(el('task-count'),`${done} of ${tasks.length} complete · ${pct}%`);text(el('question-count'),`${(state.questions||[]).length} open`);text(el('output-count'),`${(state.outputs||[]).length} recent`);text(el('blocker-count'),`${(state.blockers||[]).length} active`);
const metrics=[['Tasks',`${done}/${tasks.length}`,`${pct}% complete`],['Questions',(state.questions||[]).length,'awaiting a decision'],['Recent outputs',(state.outputs||[]).length,'recorded artifacts'],['Blockers',(state.blockers||[]).length,'active impediments']];
for(const [a,b,c] of metrics){const card=item('div','metric');const l=item('div','label');l.textContent=a;const v=item('div','value');v.textContent=b;const s=item('div','sub');s.textContent=c;card.append(l,v,s);el('metrics').append(card)}
renderList('tasks',tasks,'tasks');renderList('questions',state.questions||[],'questions');renderList('outputs',state.outputs||[],'outputs');renderList('blockers',state.blockers||[],'blockers');
const memoryItems=state.memory||[],memoryKey='geniesim-memory-choices-v1';let memoryChoices={};let memoryFilter='all';
try{memoryChoices=JSON.parse(localStorage.getItem(memoryKey)||'{}')}catch(e){memoryChoices={}}
try{if(location.hash.startsWith('#memory='))memoryChoices=JSON.parse(decodeURIComponent(location.hash.slice(8)))}catch(e){}
function memoryChoice(x){return memoryChoices[x.id]||x.recommendation||'undecided'}
function saveMemory(){const saved=JSON.stringify(memoryChoices);try{localStorage.setItem(memoryKey,saved)}catch(e){}try{history.replaceState(null,'','#memory='+encodeURIComponent(saved))}catch(e){}}
function renderMemory(){const host=el('memory-cards');host.replaceChildren();const keep=memoryItems.filter(x=>memoryChoice(x)==='keep').length;const skip=memoryItems.filter(x=>memoryChoice(x)==='skip').length;text(el('memory-count'),`${keep} 记住 · ${skip} 暂不使用 · ${memoryItems.length-keep-skip} 未决定`);for(const x of memoryItems){const choice=memoryChoice(x);if(memoryFilter!=='all'&&choice!==memoryFilter)continue;const card=item('article','memory-card');card.dataset.choice=choice;const title=item('div','memory-title');title.textContent=x.title||x.id;const source=item('div','memory-source');source.textContent=x.source||'';const body=item('p','memory-body');body.textContent=x.summary||'';const actions=item('div','memory-actions');for(const [value,label] of [['keep','记住'],['skip','暂不使用'],['undecided','未决定']]){const button=item('button',choice===value?'active':'');button.type='button';button.textContent=label;button.addEventListener('click',()=>{memoryChoices[x.id]=value;saveMemory();renderMemory()});actions.append(button)}card.append(title,source,body,actions);host.append(card)}if(!host.children.length)empty(host,'此筛选下没有条目。')}
document.querySelectorAll('[data-filter]').forEach(button=>button.addEventListener('click',()=>{memoryFilter=button.dataset.filter;document.querySelectorAll('[data-filter]').forEach(b=>b.classList.toggle('active',b===button));renderMemory()}));
el('memory-export').addEventListener('click',()=>{const records=memoryItems.map(x=>({id:x.id,title:x.title,choice:memoryChoice(x),source:x.source}));const blob=new Blob([JSON.stringify({exported_at:new Date().toISOString(),records},null,2)],{type:'application/json'});const url=URL.createObjectURL(blob);const link=document.createElement('a');link.href=url;link.download='geniesim-memory-choices.json';link.click();setTimeout(()=>URL.revokeObjectURL(url),1000)});renderMemory();
function tick(){const d=new Date();text(el('clock'),new Intl.DateTimeFormat(undefined,{hour:'2-digit',minute:'2-digit',second:'2-digit'}).format(d));text(el('date'),new Intl.DateTimeFormat(undefined,{weekday:'short',year:'numeric',month:'short',day:'numeric'}).format(d))}tick();setInterval(tick,1000);setTimeout(()=>location.reload(),10000);
</script></body></html>'''


def main() -> int:
    parser = argparse.ArgumentParser(description="Render a self-contained task dashboard from JSON.")
    parser.add_argument("state", type=Path, help="JSON state file")
    parser.add_argument("output", type=Path, help="destination .html file")
    args = parser.parse_args()
    try:
        html = render(read_state(args.state))
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(html, encoding="utf-8")
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        parser.error(str(exc))
    print(f"Dashboard written to {args.output.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

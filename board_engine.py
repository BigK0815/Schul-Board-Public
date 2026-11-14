import os
import re
from datetime import date, datetime, time, timedelta
from pathlib import Path
import hashlib
import fitz
from threading import Lock

from schuldaten import SchoolData

from flask import Flask, jsonify, render_template_string, Response, abort, send_file

SETTINGS = {'switch_seconds':15,'course_seconds':4,'cutoff_hour':15,'start_grade':5,'display_rows':2,'info_width':33,'visible_periods':list(range(1, 9)),'pdf_folder':'','pdf_seconds':12,'group_mappings':{},'group_name_display':None,'group_custom_names':{},'hidden_groups':[],'hidden_grades':[],'school_name':'Musterschule','school_logo':'','automatic_group_mapping':False}

app = Flask(__name__)
cache = {'key': None, 'data': None}
lock = Lock()
school_data = None


def source_for(token=None):
    global school_data
    token = token or os.environ.get('BESTE_TOKEN', '').strip()
    if not token:
        raise RuntimeError('Bitte zuerst einen API-Token eingeben.')
    if school_data is None or school_data.token != token:
        if school_data is not None:
            school_data.session.close()
        school_data = SchoolData(token)
        cache.update(key=None, data=None)
    return school_data


def update_groups(token):
    with lock:
        updated, mapping = source_for(token).group_snapshot(datetime.now(), force=True)
        cache.update(key=None, data=None)
        return updated, mapping


HTML = '''<!doctype html><html lang="de"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>__SCHOOL_NAME__ · Stundenplan</title>
<style>
*{box-sizing:border-box}html,body{width:100%;height:100%;margin:0;overflow:hidden}body{font-family:Arial,'Segoe UI',sans-serif;color:#14263a;background:#eaf3fc}
:root{--navy:#103d61;--ink:#123651;--grid:#b4cce0;--soft:#e8f3fc;--board-gap:clamp(12px,1.5vw,28px);--font:clamp(9px,.86vw,17px);--small:clamp(7px,.7vw,14px)}
header{height:clamp(54px,8.4vh,90px);background:linear-gradient(110deg,#073c60,#0c3455);display:flex;align-items:center;padding:5px clamp(10px,1.4vw,25px);gap:clamp(9px,1.2vw,22px);color:white}
header img{height:clamp(44px,7.6vh,80px);width:auto;max-width:8vw;object-fit:contain;background:#fff;border-radius:8px;padding:3px}
header h1{font-size:clamp(17px,2.35vw,43px);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;margin:0;font-weight:700;letter-spacing:.1px}
#clock{margin-left:auto;white-space:nowrap;font-size:clamp(12px,1.45vw,27px);font-weight:600}
main{height:calc(100dvh - clamp(54px,8.4vh,90px));display:grid;grid-template-columns:minmax(0,1fr) var(--info-width,33vw);gap:var(--board-gap);padding:clamp(6px,.8vw,14px)}
#left{display:flex;flex-direction:column;min-width:0;min-height:0;gap:clamp(5px,.65vh,10px)}
.date-head{display:flex;align-items:center;justify-content:center;background:var(--navy);color:#fff;border-radius:7px;font-weight:700;font-size:clamp(12px,1.35vw,25px);white-space:nowrap;overflow:hidden;writing-mode:vertical-rl;rotate:180deg}
#daynotes{display:none;grid-template-columns:repeat(2,minmax(0,1fr));gap:var(--day-gap);flex:0 0 auto;min-width:0}
#daynotes.visible{display:grid}
.day-note{height:clamp(25px,3.5vh,38px);display:flex;align-items:center;gap:7px;padding:2px 9px;background:#dcecff;color:#123d64;border:1px solid #bbd7f5;border-radius:6px;min-width:0;font-size:clamp(10px,.9vw,17px);font-weight:600}
.day-note.empty{visibility:hidden}
.day-note .info-symbol{font-weight:800;border-radius:50%;background:#2876c5;color:white;width:18px;height:18px;display:inline-flex;align-items:center;justify-content:center;flex:none;font-size:12px}
.day-note .note-text{white-space:nowrap;overflow:hidden;text-overflow:ellipsis;min-width:0}
#board{display:grid;grid-template-rows:repeat(2,minmax(0,1fr));gap:clamp(10px,1.6vh,22px);flex:1;min-height:0;--day-gap:clamp(14px,1.4vw,30px)}
#left{--day-gap:clamp(14px,1.4vw,30px)}
.day-panel{display:grid;grid-template-columns:clamp(28px,3vw,50px) var(--hour-column-width) minmax(0,1fr);min-width:0;min-height:0;overflow:hidden}
.grade-groups{display:grid;gap:var(--day-gap);min-width:0;min-height:0}
.hour-column{display:grid;grid-template-rows:clamp(24px,4.3vh,41px) repeat(var(--period-count,8),minmax(0,1fr));min-height:0}
.hour-column .hour{background:#fff;border:1px solid var(--grid);display:flex;align-items:center;justify-content:center;font-size:var(--font);font-weight:700;min-height:0}
.class-grid{display:grid;grid-template-columns:repeat(var(--class-count),minmax(0,1fr));gap:clamp(2px,.25vw,5px);min-height:0;min-width:0}
.class-col{display:grid;grid-template-rows:clamp(24px,4.3vh,41px) repeat(var(--period-count,8),minmax(0,1fr));min-width:0;min-height:0;overflow:hidden}
.class-name{background:var(--navy);color:white;text-align:center;font-size:clamp(11px,1.22vw,23px);font-weight:700;display:flex;align-items:center;justify-content:center;min-width:0;border-radius:5px 5px 0 0}
.slot{border:1px solid var(--grid);border-top:0;display:flex;align-items:center;justify-content:center;min-width:0;min-height:0;overflow:hidden;background:#fff;text-align:center}
/* Jede Stunde bekommt über beide Tage und die Stundennummer dieselbe Zeilenfarbe. */
.hour-column .hour:nth-child(odd){background:#fff}.hour-column .hour:nth-child(even){background:#e8f5ff}
.slot.row-even,.slot.empty.row-even{background:#fff}
.slot.row-odd,.slot.empty.row-odd{background:#e8f5ff}
/* Fach stets am gleichen linken Rand, Lehrer/Raum rechts daneben. */
.slot{text-align:left;justify-content:flex-start;padding:0 2px}
.mini{justify-content:flex-start;gap:clamp(3px,.35vw,7px);padding:0 2px}
.subject{flex:0 0 auto;max-width:47%}
.detail{flex:1 1 auto;min-width:0;text-align:left}
.compact{align-items:flex-start;text-align:left;padding-left:4px}
/* Gekoppelte Kurse erkennbar, ohne die Zeilenstreifen zu überdecken. */
.slot.coupled:not(.changed):not(.canceled){background:#cdebf8}

.mini,.compact{height:100%;width:100%;min-width:0;min-height:0;display:flex;align-items:center;justify-content:space-evenly;gap:2px;padding:0 2px;overflow:hidden}
.subject,.compact strong{font-size:var(--font);font-weight:700;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;flex:0 1 auto;line-height:1.05}
.detail,.compact small{font-size:var(--small);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;line-height:1.05}
.compact{flex-direction:column;justify-content:center}.compact strong,.compact small{max-width:100%}
.changed{background:#ffedbf!important}.canceled{background:#ffd6dc!important}.slot.canceled{position:relative}.cancel-cross{position:absolute;inset:0;width:100%;height:100%;pointer-events:none;z-index:2}
#infoboard{display:flex;flex-direction:column;min-width:0;min-height:0;background:white;border-radius:10px;overflow:hidden;box-shadow:0 1px 6px #a4bfd144}
#infohead{height:clamp(30px,5vh,50px);flex:0 0 auto;display:flex;align-items:center;justify-content:center;background:var(--navy);color:white;border-radius:7px;font-weight:700;font-size:clamp(12px,1.35vw,25px)}
#infonote{display:none;width:100%;height:100%;padding:clamp(12px,1.5vw,28px);flex-direction:column;align-items:stretch;justify-content:flex-start;text-align:left;gap:clamp(12px,2vh,26px);background:#f2f8ff;color:#123d64;overflow:hidden;box-sizing:border-box}
#infonote .note-date{font-size:clamp(18px,1.7vw,34px);font-weight:800;margin-bottom:clamp(5px,.7vh,10px)}
#infonote .note-day{flex:0 0 auto;min-width:0}
#infonote .note-day + .note-day{border-top:2px solid #c9dff3;padding-top:clamp(10px,1.4vh,20px)}
#infonote .note-message{font-size:clamp(12px,1.35vw,25px);font-weight:600;line-height:1.35;overflow-wrap:anywhere;white-space:pre-wrap}
#infonote .note-message + .note-message{margin-top:1.35em}
#infocontent{flex:1;min-height:0;display:flex;align-items:center;justify-content:center;background:#fff;overflow:hidden}
#infoimage{display:none;width:100%;height:100%;object-fit:contain}
#infoempty{padding:20px;text-align:center;color:#52657a;font-size:clamp(13px,1.2vw,20px)}
#infocaption{height:clamp(19px,2.5vh,27px);display:flex;align-items:center;justify-content:center;color:#5b7184;font-size:clamp(9px,.72vw,13px);overflow:hidden;text-overflow:ellipsis;white-space:nowrap;background:#f1f5fa}
#copyright{position:fixed;right:12px;bottom:3px;z-index:10;font-size:clamp(11px,.75vw,15px);color:#718397;opacity:.78;pointer-events:none;white-space:nowrap;text-shadow:0 1px 2px #fff;background:rgba(255,255,255,.72);padding:1px 4px;border-radius:3px}
.error{background:#ffdde2;color:#8a1423;padding:12px}
@media(max-width:1000px){:root{--font:clamp(7px,.78vw,12px);--small:clamp(6px,.6vw,9px)}.mini{flex-direction:row;justify-content:flex-start;gap:2px}.grade-label{font-size:10px}header h1{font-size:clamp(15px,2vw,22px)}}
@media(max-height:700px){.class-col,.hour-column{grid-template-rows:22px repeat(var(--period-count,8),minmax(0,1fr))}.mini{flex-direction:row;gap:2px;justify-content:flex-start}}

#left{--hour-column-width:clamp(17px,1.55vw,29px)}
.slot{justify-content:flex-start;text-align:left;padding:0 2px}
.slot .mini{display:flex;flex-direction:row;justify-content:flex-start;align-items:center;gap:3px;padding:0 1px;min-width:0;width:100%;height:100%}
.slot .subject{font-weight:700;flex:0 0 auto;max-width:none;overflow:visible;text-overflow:clip;white-space:nowrap}
.slot .detail{font-weight:400;flex:0 0 auto;min-width:0;max-width:none;overflow:visible;text-overflow:clip;white-space:nowrap}
.slot .mini.wrap{flex-direction:column;align-items:flex-start;justify-content:center;gap:0}
.slot .mini.wrap .subject,.slot .mini.wrap .detail{max-width:100%;overflow:hidden;text-overflow:ellipsis}
.slot.coupled:not(.changed):not(.canceled){background:#cdebf8}
.slot.changed{background:#ffedbf!important}.slot.canceled{background:#ffd6dc!important}
.slot.current-period:not(.canceled),.hour-column .hour.current-period{background:#79e64e!important}
</style></head><body>
<header><img src="/assets/schullogo.png" alt="Schullogo"><h1>__SCHOOL_NAME__</h1><div id="clock"></div></header>
<main><div id="left"><div id="board"></div></div><aside id="infoboard"><div id="infohead">Infos &amp; Termine</div><div id="infocontent"><div id="infonote"></div><img id="infoimage" alt="Informationen aus PDF"><div id="infoempty">Keine PDF-Dateien im Info-Ordner</div></div></aside></main><div id="copyright">(c) 2026 Robert Kettmann</div>
<script>
const BOARD_SETTINGS=__BOARD_SETTINGS_JSON__;
let data=null,index=0,lastChange=Date.now(),coursePhase=0,notePhase=0;
let levels=[];
function gradeOf(name){return data.class_grades[name] ?? 0;}
const weekdays=['Sonntag','Montag','Dienstag','Mittwoch','Donnerstag','Freitag','Samstag'];
function dateLabel(iso){let d=new Date(iso+'T12:00:00');return weekdays[d.getDay()]+', '+iso.slice(8,10)+'.'+iso.slice(5,7)+'.';}
function dayHeading(iso, now){
 const day=new Date(iso+'T12:00:00');
 const tomorrow=new Date(now.getFullYear(),now.getMonth(),now.getDate()+1);
 const sameDay=(a,b)=>a.getFullYear()===b.getFullYear()&&a.getMonth()===b.getMonth()&&a.getDate()===b.getDate();
 const prefix=sameDay(day,now)?'Heute – ':sameDay(day,tomorrow)?'Morgen – ':'';
 return prefix+dateLabel(iso);
}
function escapeHtml(s){return String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}
function cell(lessons,day,n){
 const rowClass=n%2===0?'row-odd':'row-even';
 if(!lessons||!lessons.length)return `<div class="slot empty ${rowClass}"></div>`;
 // Bei parallelen Kursen direkt die Kurse rotieren, niemals eine Zusammenfassung anzeigen.
 const l=lessons[coursePhase%lessons.length];
 const cls=l.status==='canceled'?'canceled':l.changed?'changed':lessons.length>1?'coupled':'';
 const subject=l.display_label ?? l.subject;
 const detail=[l.teacher,l.room].filter(Boolean).join('/');
 const full=[subject,detail].filter(Boolean).join(' ');
 const cross=cls==='canceled'
  ? '<svg class="cancel-cross" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true"><path d="M0 0L100 100M0 100L100 0" fill="none" stroke="#ba2536" stroke-width="2" vector-effect="non-scaling-stroke"/></svg>'
  : '';
 return `<div class="slot ${rowClass} ${cls}" title="${escapeHtml(full)}"><div class="mini"><span class="subject">${escapeHtml(subject)}</span><span class="detail">${escapeHtml(detail)}</span></div>${cross}</div>`;
}
// Passt die Schrift nur dann an, wenn der gesamte Eintrag sonst nicht in die Zelle passt.
function fitCells(){
 const ctx=document.createElement('canvas').getContext('2d');
 document.querySelectorAll('.slot .mini').forEach(el=>{
  const a=el.querySelector('.subject'),b=el.querySelector('.detail');if(!a||!b)return;
  const width=el.clientWidth-4;if(width<=0)return;
  const styles=getComputedStyle(a),detailStyles=getComputedStyle(b);
  const maxSubject=parseFloat(styles.fontSize),maxDetail=parseFloat(detailStyles.fontSize);
  const minFont=7, gap=3;
  const measure=(node,font,weight)=>{ctx.font=`${weight} ${font}px Arial`;return ctx.measureText(node.textContent).width};
  let sf=maxSubject,df=maxDetail;
  // Erst die weniger wichtige Lehrer/Raum-Angabe verkleinern.
  while(df>minFont && measure(a,sf,'700')+measure(b,df,'400')+gap>width)df-=.5;
  while(sf>minFont && measure(a,sf,'700')+measure(b,df,'400')+gap>width)sf-=.5;
  a.style.fontSize=sf+'px';b.style.fontSize=df+'px';
  // Bei extrem langen Bezeichnungen auf zwei Zeilen umbrechen, statt zu überlaufen.
  if(measure(a,sf,'700')+measure(b,df,'400')+gap>width){el.classList.add('wrap');}
 });
}

function renderDay(groups,dayIndex,periods,now){
 const iso=data.days[dayIndex];
 const hours=periods.map(n=>`<div class="hour" data-period="${n}">${n}</div>`).join('');
 const grids=groups.map(names=>{
  const columns=names.map(name=>{
   const byNr={};
   for(const lesson of data.classes[name])if(lesson.day===iso)(byNr[lesson.nr]??=[]).push(lesson);
   const slots=periods.map(n=>cell(byNr[n],dayIndex,n)).join('');
   return `<div class="class-col"><div class="class-name">${escapeHtml(name)}</div>${slots}</div>`;
  }).join('');
  return `<div class="class-grid" style="--class-count:${names.length}">${columns}</div>`;
 }).join('');
 const widths=groups.map(names=>`minmax(0,${names.length}fr)`).join(' ');
 return `<section class="day-panel" data-date="${iso}"><div class="date-head">${escapeHtml(dayHeading(iso,now))}</div><div class="hour-column"><div></div>${hours}</div><div class="grade-groups" style="grid-template-columns:${widths}">${grids}</div></section>`;
}
function collectInfoNotes(){
 if(!data)return [];
 const notes=data.day_notes||{};
 return data.days.map(day=>({date:day,messages:(notes[day]||[])
  .filter(x=>typeof x==='string'&&x.trim()).map(x=>x.trim())}))
  .filter(day=>day.messages.length);
}
function noteMarkup(groups){return groups.map(group=>`<section class="note-day"><div class="note-date">${escapeHtml(dateLabel(group.date))}</div>${group.messages.map(message=>`<div class="note-message">${escapeHtml(message)}</div>`).join('')}</section>`).join('');}
function notePages(){
 const days=collectInfoNotes();if(!days.length)return [];
 const note=document.getElementById('infonote');
 // Measure using exactly the same width, typography and padding as the visible panel.
 const probe=note.cloneNode(false);probe.removeAttribute('id');probe.style.cssText='display:flex;position:absolute;visibility:hidden;pointer-events:none;left:0;top:0;z-index:-1;width:'+note.parentElement.clientWidth+'px;height:'+note.parentElement.clientHeight+'px';
 note.parentElement.appendChild(probe);
 const pages=[];let current=[];
 function fits(groups){probe.innerHTML=noteMarkup(groups);return probe.scrollHeight<=probe.clientHeight+1;}
 function push(){if(current.length){pages.push({kind:'note',groups:current});current=[];}}
 for(const day of days){
  for(const message of day.messages){
   const last=current.length&&current[current.length-1].date===day.date;
   const candidate=current.map(g=>({date:g.date,messages:[...g.messages]}));
   if(last)candidate[candidate.length-1].messages.push(message);
   else candidate.push({date:day.date,messages:[message]});
   if(current.length&&!fits(candidate))push();
   if(current.length&&current[current.length-1].date===day.date)current[current.length-1].messages.push(message);
   else current.push({date:day.date,messages:[message]});
  }
 }
 push();probe.remove();return pages;
}
function render(){if(!data)return;
 const rows=Math.max(1,Math.min(3,Number(BOARD_SETTINGS.display_rows)||2));
 const board=document.getElementById('board');
 const now=new Date();
 const periods=BOARD_SETTINGS.visible_periods;
 refreshInfoDisplay();
 board.style.setProperty('--period-count',periods.length);
 if(!levels.length){board.innerHTML='';return;}
 const selected=Array.from({length:Math.min(rows,levels.length)},(_,i)=>levels[(index+i)%levels.length]);
 const groups=selected.map(level=>Object.keys(data.classes).filter(k=>gradeOf(k)===level)
  .sort((a,b)=>a.localeCompare(b,'de',{numeric:true})));
 board.innerHTML=data.days.map((_,i)=>renderDay(groups,i,periods,now)).join('');
 markCurrentPeriod(now);
 requestAnimationFrame(fitCells);
}
function next(){if(!levels.length)return;const rows=Math.max(1,Math.min(3,Number(BOARD_SETTINGS.display_rows)||2));index=(index+rows)%levels.length;lastChange=Date.now();render()}
async function load(){try{const r=await fetch('/api/week',{cache:'no-store'});const j=await r.json();if(!r.ok)throw Error(j.error||'HTTP '+r.status);const newLevels=[...new Set(Object.values(j.class_grades).map(grade=>grade??0))].sort((a,b)=>a-b);
if(newLevels.join(',')!==levels.join(',')){
 const start=newLevels.findIndex(grade=>grade>=BOARD_SETTINGS.start_grade);
 const rows=BOARD_SETTINGS.display_rows;
 index=Math.floor(Math.max(0,start)/rows)*rows;
 levels=newLevels;
}
data=j;render();}catch(e){document.getElementById('board').innerHTML='<div class="error">'+escapeHtml(e.message)+'</div>';}}
function currentPeriod(times, time){
 const periods=Object.keys(times);
 if(!periods.length || time<times[periods[0]].start)return null;
 const current=periods.find(n=>time<times[n].end);
 return current===undefined?null:Number(current);
}
function markCurrentPeriod(now){
 const pad=n=>String(n).padStart(2,'0');
 const today=`${now.getFullYear()}-${pad(now.getMonth()+1)}-${pad(now.getDate())}`;
 const period=currentPeriod((data?.lesson_times ?? {}),`${pad(now.getHours())}:${pad(now.getMinutes())}`);
 document.querySelectorAll('#board .day-panel').forEach(panel=>{
  const active=panel.dataset.date===today?period:null;
  panel.querySelectorAll('.class-col,.hour-column').forEach(column=>{
   for(let n=1;n<column.children.length;n++)
    column.children[n].classList.toggle('current-period',BOARD_SETTINGS.visible_periods[n-1]===active);
  });
 });
}
function updateClock(){const now=new Date();document.getElementById('clock').textContent=new Intl.DateTimeFormat('de-DE',{weekday:'short',day:'2-digit',month:'2-digit',year:'numeric',hour:'2-digit',minute:'2-digit'}).format(now);markCurrentPeriod(now);}
let infoSlides=[],infoIndex=0,infoSignature='',currentInfoKey='';
function allInfoSlides(){return [...notePages(),...infoSlides.map(slide=>({kind:'pdf',...slide}))];}
function refreshInfoDisplay(){
 const slides=allInfoSlides();
 const img=document.getElementById('infoimage'),empty=document.getElementById('infoempty'),note=document.getElementById('infonote');
 if(!slides.length){img.style.display='none';img.removeAttribute('src');note.style.display='none';empty.style.display='block';currentInfoKey='';return;}
 infoIndex%=slides.length;
 const slide=slides[infoIndex];
 if(slide.kind==='note'){
  img.style.display='none';img.removeAttribute('src');empty.style.display='none';note.style.display='flex';
  note.innerHTML=noteMarkup(slide.groups);currentInfoKey='note:'+infoIndex;
 }else{
  note.style.display='none';empty.style.display='none';img.style.display='block';
  if(currentInfoKey!==slide.url)img.src=slide.url;
  currentInfoKey=slide.url;
 }
}
async function refreshInfo(){try{const r=await fetch('/api/info/list',{cache:'no-store'});if(!r.ok)throw Error('PDF-Liste nicht erreichbar');const j=await r.json();const signature=JSON.stringify(j.slides);if(signature!==infoSignature){infoSignature=signature;infoSlides=j.slides;infoIndex=0;refreshInfoDisplay();}}catch(e){document.getElementById('infoempty').textContent='Info-Board: '+e.message;}}
setInterval(()=>{const slides=allInfoSlides();if(slides.length>1){infoIndex=(infoIndex+1)%slides.length;refreshInfoDisplay();}},Math.max(2,Number(BOARD_SETTINGS.pdf_seconds)||12)*1000);
document.getElementById('infoimage').addEventListener('error',()=>{currentInfoKey='';refreshInfo();});
setInterval(refreshInfo,5000);refreshInfo();
setInterval(()=>{const sec=BOARD_SETTINGS.switch_seconds;if(sec&&Date.now()-lastChange>=sec*1000)next()},1000);
setInterval(()=>{coursePhase++;if(data)render()},Math.max(1,BOARD_SETTINGS.course_seconds)*1000);

setInterval(load,15000);setInterval(updateClock,1000);updateClock();load();
</script></body></html>'''

def ident(obj):
    return str((obj or {}).get('local_id') or (obj or {}).get('name') or '') if isinstance(obj, dict) else ''

def details(item):
    return {'weekday': int(item.get('weekday') or 0), 'nr': int(item.get('nr') if item.get('nr') is not None else -1), 'subject': ident(item.get('subject')), 'teacher': ', '.join(filter(None, [ident(x) for x in (item.get('teachers') or [])])), 'room': ', '.join(filter(None, [ident(x) for x in (item.get('rooms') or [])])), 'status': item.get('status', 'initial'), 'changed': False, 'note': ''}

def group_display_name(group, settings):
    names = settings['group_custom_names']
    if group in names:
        return names[group].strip()
    legacy = settings.get('group_name_display')
    if legacy is not None and legacy.get(group, group.upper().startswith('NGS')):
        return group
    return ''


def split_labels(value):
    return [v.strip() for v in (value or '').split(',') if v.strip()]


def resolve_current_assignment(lesson, originals, moved_originals=None):
    """Keep teacher information untouched; only resolve an unambiguous old room."""
    if lesson['status'] != 'planned':
        return lesson
    values = split_labels(lesson['room'])
    if len(values) < 2:
        return lesson
    baseline = moved_originals if moved_originals is not None else originals
    if not baseline:
        return lesson
    old_rooms = {room for old in baseline for room in split_labels(old['room'])}
    new_rooms = [room for room in values if room not in old_rooms]
    if len(new_rooms) == 1 and any(room in old_rooms for room in values):
        lesson['room'] = new_rooms[0]
    return lesson


def resolve_replacement_teacher(lesson, originals):
    """Remove a superseded teacher from a planned slot, if unambiguous.

    Compare with the *regular* timetable at the destination slot, never
    with another substituted entry. A different subject is allowed (GE->KU).
    Do not guess when several originals or several remaining teachers exist.
    """
    if lesson['status'] != 'planned' or len(originals) != 1:
        return lesson
    teachers = split_labels(lesson['teacher'])
    if len(teachers) < 2:
        return lesson
    old_teachers = split_labels(originals[0]['teacher'])
    if not old_teachers or not all(t in teachers for t in old_teachers):
        return lesson
    replacements = [t for t in teachers if t not in old_teachers]
    if len(replacements) == 1:
        lesson['teacher'] = replacements[0]
    return lesson


def resolve_moved_room(lesson, group, destination, regular_by_date):
    """Resolve mixed room lists on moved lessons, even across weekdays.

    The source is the published *regular* timetable, not a modified
    substitution slot. Only delete a room if exactly one candidate remains.
    The teacher field is never changed.
    """
    if lesson['status'] != 'planned':
        return lesson
    rooms = split_labels(lesson['room'])
    if len(rooms) < 2:
        return lesson
    teachers = set(split_labels(lesson['teacher']))
    if not teachers:
        return lesson
    day = date.fromisoformat(destination)
    # Identify original teacher(s) through same class and subject in the
    # regular plan. A move may cross weekdays (e.g. Friday -> Thursday).
    sources = []
    for day_iso, slots in regular_by_date.items():
        if abs((date.fromisoformat(day_iso) - day).days) > 7:
            continue
        for (old_group, old_weekday, old_nr), lessons in slots.items():
            if old_group != group or (day_iso == destination and old_nr == lesson['nr']):
                continue
            for old in lessons:
                old_teachers = set(split_labels(old['teacher']))
                if old['subject'] == lesson['subject'] and old_teachers and old_teachers.issubset(teachers):
                    sources.append(old)
    # Multiple identical weekly lessons are fine when they agree on room
    # and teacher. Different source assignments are ambiguous.
    source_signatures = {(old['teacher'], old['room']) for old in sources}
    if len(source_signatures) != 1:
        return lesson
    source_teacher, source_room = next(iter(source_signatures))
    old_rooms = set(split_labels(source_room))
    remaining = [room for room in rooms if room not in old_rooms]
    if len(remaining) == 1 and len(remaining) < len(rooms):
        lesson['room'] = remaining[0]
        return lesson

    # The original room is not listed (10/3 KU: K2 -> Deu3).
    # A second teacher in the substitution may contribute their own
    # unrelated room (e.g. Rih/Geo2 or Wei/Geo2). Confirm this room
    # against the regular plan, not against an assumed room order.
    ancillary = teachers - set(split_labels(source_teacher))
    if not ancillary:
        return lesson
    ancillary_rooms = set()
    for day_iso, slots in regular_by_date.items():
        if day_iso != destination:
            continue
        for (_, _, _), lessons in slots.items():
            for old in lessons:
                if set(split_labels(old['teacher'])) & ancillary:
                    ancillary_rooms.update(split_labels(old['room']))
    extra = [room for room in rooms if room in ancillary_rooms]
    kept = [room for room in rooms if room not in ancillary_rooms]
    if len(extra) == 1 and len(kept) == 1:
        lesson['room'] = kept[0]
    return lesson


def visible_days(now=None, timetable=None, lesson_times=None):
    """Two school days, advancing at configured cutoff."""
    now = now or datetime.now()  # local clock of the school computer
    cursor = now.date()
    # Keep today's plan visible through the last configured lesson.
    cutoff = max([time(int(SETTINGS['cutoff_hour']), 0)] + [
        time.fromisoformat(period['end']) for period in (lesson_times or {}).values()
    ])
    if now.time() >= cutoff and cursor.weekday() < 5:
        cursor += timedelta(days=1)
    # The API may encode its list of calendar dates as a string.
    closed = set(re.findall(r'\b\d{4}-\d{2}-\d{2}\b',
                            str((timetable or {}).get('no_school_dates') or '')))
    result = []
    while len(result) < 2:
        if cursor.weekday() < 5 and cursor.isoformat() not in closed:
            result.append(cursor)
        cursor += timedelta(days=1)
    return result


def target_classes(group, class_names, automatic_mapping=None):
    """Use API membership when available, with manual assignments as a fallback."""
    if automatic_mapping is not None:
        return automatic_mapping.get(group, ())
    mapping = SETTINGS.get('group_mappings') or {}
    if group in mapping and mapping[group]:
        targets = mapping[group]
        if isinstance(targets, str):
            targets = [x.strip() for x in targets.split(',')]
        return [x for x in targets if x in class_names]
    if not SETTINGS.get('automatic_group_mapping', True):
        return [group] if group in class_names else []
    # NGS groups are always in grades 5/6; only infer a grade if it is
    # unambiguous in the identifier. Otherwise require a manual assignment.
    if 'NGS' in group.upper():
        grades = set(re.findall(r'(?<!\d)[56](?!\d)', group))
        if len(grades) == 1:
            grade = next(iter(grades))
            return [c for c in class_names if c.startswith(grade + '/')]
        return []

    if group in class_names:
        return [group]
    # Cross-year religion groups: 56RE/k and 78RE/k.
    if group.startswith('56RE/'):
        return [c for c in class_names if c.split('/')[0] in ('5', '6')]
    if group.startswith('78RE/'):
        return [c for c in class_names if c.split('/')[0] in ('7', '8')]
    match = re.match(r'^(10|[5-9])(.+)$', group)
    if not match:
        return []
    year, course = match.groups()
    same_year = [c for c in class_names if c.startswith(year + '/')]
    # Profiles: digits designate profile/course variants, not home classes.
    if re.match(r'^P(?:kü\d+|nw|spo|\d+)$', course, re.IGNORECASE):
        return same_year
    # Split groups: INF3-2 -> 3; TC12a -> 1,2; FÖlrs34 -> 3,4.
    # Other subject suffix digits designate participating home classes.
    digits = re.search(r'(\d+)(?:-[12]|[ab])?$', course, re.IGNORECASE)
    if digits:
        participants = set(digits.group(1))
        return [c for c in same_year if c.split('/')[1] in participants]
    # No class number: group can contain pupils from all classes in year.
    return same_year


def class_grade(name, grades=None):
    if grades and name in grades:
        return grades[name]
    match = re.match(r'^(?:Jg\.?\s*)?(1[0-3]|[1-9])(?=\D|$)', name, re.IGNORECASE)
    return int(match[1]) if match else None


def build_week(days, timetable, substitutions, automatic_mapping, grades=None):
    mapping = automatic_mapping
    if mapping is None:
        mapping = SETTINGS.get('group_mappings') or {}
    configured = set()
    for targets in mapping.values():
        if isinstance(targets, str):
            targets = [v.strip() for v in re.split('[,;]', targets) if v.strip()]
        configured.update(str(v).strip() for v in targets if str(v).strip())
    classes = {name: {} for name in configured}
    if automatic_mapping is None and not classes:
        for item in timetable['lessons']:
            name = ident(item.get('group'))
            if re.fullmatch(r'(?:10|[5-9])/\d+', name):
                classes.setdefault(name, {})

    hidden = set(SETTINGS['hidden_groups'])
    excluded_grades = set(SETTINGS['hidden_grades'])
    classes = {name: slots for name, slots in classes.items()
               if name not in hidden and class_grade(name, grades) not in excluded_grades}
    if automatic_mapping is not None:
        automatic_mapping = {group: [name for name in targets if name in classes]
                             for group, targets in automatic_mapping.items() if group not in hidden}

    # The published timetable explicitly maps ISO calendar weeks to A/B types.
    # Never infer the week type from the parity of the week number: holidays
    # and timetable changes can break that assumption.
    week_types = {}
    for record in timetable.get('weeks', []):
        try:
            key = (int(record['year']), int(record['nr']))
        except (KeyError, TypeError, ValueError):
            continue
        week_types[key] = set(record.get('types') or [])

    def applicable(item, school_day):
        iso_year, iso_week, _ = school_day.isocalendar()
        active = week_types.get((iso_year, iso_week))
        # Unknown week is not silently assumed to be A or B.
        if not active:
            return False
        return bool(active.intersection(item.get('weeks') or ['A', 'B']))

    # Keep lessons by their original group first. Only afterwards expand
    # each course group into every participating home class.
    regular = {}
    # Also index nearby regular days to find cross-day moves.
    reference_days = [min(days) + timedelta(days=i) for i in range(-7, (max(days)-min(days)).days + 8)]
    regular_by_date = {d.isoformat(): {} for d in reference_days}
    for item in timetable.get('lessons', []):
        group = ident(item.get('group'))
        if group in hidden or not target_classes(group, classes, automatic_mapping):
            continue
        lesson = details(item)
        if 1 <= lesson['weekday'] <= 5 and 0 <= lesson['nr'] <= 10:
            regular.setdefault((group, lesson['weekday'], lesson['nr']), []).append(lesson)
            for d in reference_days:
                if d.isoweekday() == lesson['weekday'] and applicable(item, d):
                    regular_by_date[d.isoformat()].setdefault((group, lesson['weekday'], lesson['nr']), []).append(lesson)

    # A published substitution day replaces the regular lessons for that day.
    # Retain multiple entries, including parallel courses and split groups.
    daily_by_date = {}
    published = set()
    # Slots explicitly mentioned by the API (including cancellations and moves).
    # These must never be refilled from the regular timetable.
    published_slots = {}
    day_notes = {d.isoformat(): [] for d in days}
    for day in substitutions:
        day_iso = str(day['date'])[:10]
        published.add(day_iso)
        # Day-level notes belong to the date, not individual lessons.
        # Preserve their API order; ignore empty strings and duplicates.
        notes = day.get('notes') or []
        for note in ([notes] if isinstance(notes, str) else notes):
            if isinstance(note, str) and note.strip() and note.strip() not in day_notes[day_iso]:
                day_notes[day_iso].append(note.strip())
        weekday = date.fromisoformat(day_iso).isoweekday()
        entries = daily_by_date.setdefault(day_iso, [])
        # A moved lesson is published twice: a new planned slot and a
        # canceled slot at its old time. The canceled half is irrelevant
        # on the pupil-facing board. Match within the same original group
        # and subject, on different periods; ordinary cancellations stay.
        raw_lessons = [item for item in day.get('lessons') or []
                       if (group := ident(item.get('group'))) not in hidden
                       and target_classes(group, classes, automatic_mapping)]
        mentioned = published_slots.setdefault(day_iso, set())
        for raw in raw_lessons:
            raw_group = ident(raw.get('group'))
            try:
                raw_nr = int(raw.get('nr') if raw.get('nr') is not None else -1)
            except (ValueError, TypeError):
                continue
            if raw_group and 0 <= raw_nr <= 10:
                mentioned.add((raw_group, weekday, raw_nr))
        moved_from = set()
        planned_by_course = {}
        for raw in raw_lessons:
            if raw.get('status') == 'planned':
                key = (ident(raw.get('group')), ident(raw.get('subject')))
                planned_by_course.setdefault(key, set()).add(raw.get('nr'))
        for idx, raw in enumerate(raw_lessons):
            if raw.get('status') != 'canceled':
                continue
            key = (ident(raw.get('group')), ident(raw.get('subject')))
            if any(nr != raw.get('nr') for nr in planned_by_course.get(key, ())):
                moved_from.add(idx)
        canceled_by_course = {}
        for idx in moved_from:
            old_raw = raw_lessons[idx]
            key = (ident(old_raw.get('group')), ident(old_raw.get('subject')))
            canceled_by_course.setdefault(key, []).append(details(old_raw))
        for idx, item in enumerate(raw_lessons):
            if idx in moved_from:
                continue
            group = ident(item.get('group'))
            if group in hidden or not target_classes(group, classes, automatic_mapping):
                continue
            lesson = details(item)
            lesson['weekday'] = weekday
            if not 0 <= lesson['nr'] <= 10:
                continue
            originals = regular_by_date[day_iso].get((group, weekday, lesson['nr']), [])
            if lesson['status'] == 'canceled' and originals:
                # Ausfall zeigt den ursprünglichen Stundenplaneintrag, nicht
                # die leeren/abweichenden Werte der Vertretungsmeldung.
                original = next((old for old in originals
                                 if old['subject'] == lesson['subject']), originals[0])
                for field in ('subject', 'teacher', 'room'):
                    lesson[field] = original[field]
            else:
                course_key = (group, lesson['subject'])
                moved_candidates = [old for old in canceled_by_course.get(course_key, [])
                                    if old['nr'] != lesson['nr']]
                # Only infer a move when there is a unique canceled source.
                moved_originals = moved_candidates if (lesson['status'] == 'planned'
                                                      and len(moved_candidates) == 1) else None
                # Resolve teacher replacement against the original slot,
                # independently of the subject and of teacher ordering.
                lesson = resolve_replacement_teacher(lesson, originals)
                # Resolve rooms from the original (unmodified) timetable.
                lesson = resolve_moved_room(lesson, group, day_iso, regular_by_date)
                # A same-day canceled source is an additional safe fallback.
                lesson = resolve_current_assignment(lesson, originals, moved_originals)
            exact = any(all(lesson[k] == old[k] for k in ('subject', 'teacher', 'room')) for old in originals)
            lesson['changed'] = lesson['status'] == 'planned' or (bool(originals) and not exact and lesson['status'] != 'canceled')
            if originals and lesson['changed']:
                lesson['note'] = ''  # Keine ehemalige Lehrkraft im Schüler-Board
            entries.append((group, lesson))

    for ddate in days:
        day_iso = ddate.isoformat()
        if day_iso in published:
            # The published V-plan is the primary source. Only fill a genuinely
            # unmentioned regular slot. A canceled or moved slot is *mentioned*
            # even if its canceled half was intentionally suppressed above.
            source = list(daily_by_date.get(day_iso, []))
            mentioned = published_slots.get(day_iso, set())
            for slot, lessons in regular_by_date[day_iso].items():
                if slot not in mentioned:
                    source.extend((slot[0], dict(old)) for old in lessons)
        else:
            # No published day: retain the regular timetable as fallback.
            source = [(group, dict(lesson)) for (group, weekday, nr), lessons in regular_by_date[day_iso].items()
                      for lesson in lessons]
        for group, lesson in source:
            for name in target_classes(group, classes, automatic_mapping):
                entry = dict(lesson, day=day_iso)
                custom_name = group_display_name(group, SETTINGS)
                if custom_name:
                    entry['display_label'] = custom_name
                classes[name].setdefault((day_iso, entry['nr']), []).append(entry)

    return {'days': [d.isoformat() for d in days], 'day_notes': day_notes,
            'class_grades': {name: class_grade(name, grades) for name in classes}, 'classes': {
        name: [entry for parallel in slots.values() for entry in parallel]
        for name, slots in sorted(classes.items()) if name not in hidden}}

@app.get('/')
def home():
    import json
    client_settings = {
        'switch_seconds': int(SETTINGS['switch_seconds']),
        'course_seconds': int(SETTINGS['course_seconds']),
        'display_rows': int(SETTINGS['display_rows']),
        'visible_periods': SETTINGS['visible_periods'],
        'start_grade': int(SETTINGS['start_grade']),
        'pdf_seconds': int(SETTINGS['pdf_seconds']),
    }
    from markupsafe import escape
    html = HTML.replace('__BOARD_SETTINGS_JSON__', json.dumps(client_settings))
    html = html.replace('__SCHOOL_NAME__', str(escape(SETTINGS.get('school_name') or 'Musterschule')))
    html = html.replace('<main>', f'<main style="--info-width:{int(SETTINGS['info_width'])}vw">', 1)
    return render_template_string(html)

@app.get('/assets/schullogo.png')
def school_logo():
    custom = str(SETTINGS.get('school_logo') or '').strip()
    logo = Path(custom).expanduser() if custom else Path(__file__).with_name('schullogo.png')
    if not logo.is_file():
        logo = Path(__file__).with_name('schullogo.png')
    return send_file(logo, mimetype='image/png', max_age=0)

def refresh_board():
    with lock:
        source = source_for()
        now = datetime.now()
        timetable = source.timetable(now)
        lesson_times = source.lesson_times(now)
        days = visible_days(now, timetable, lesson_times)
        updated, mapping = source.group_snapshot(now)
        substitutions = source.substitution_days(days)
        key = (now.date(), tuple(days), updated, tuple(stamp for stamp, _ in substitutions))
        if cache['key'] != key:
            published = [day for _, day in substitutions if day is not None]
            data = build_week(days, timetable, published, mapping, source.read('jahrgaenge-cache')[1])
            data['lesson_times'] = lesson_times
            cache.update(data=data, key=key)
        return cache['data']


@app.get('/api/week')
def week():
    try:
        return jsonify(refresh_board())
    except Exception as error:
        return jsonify({'error': str(error)}), 502


def info_directory():
    if not SETTINGS['pdf_folder']:
        return None
    folder = Path(SETTINGS['pdf_folder']).expanduser().resolve()
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def info_files():
    # Date-range filenames are inclusive: DDMMYYYY-DDMMYYYY.pdf.
    # Other filenames have no expiry and remain until removed.
    today = date.today()
    files = []
    directory = info_directory()
    if directory is None:
        return []
    for p in directory.iterdir():
        if not p.is_file() or p.suffix.lower() != '.pdf':
            continue
        match = re.fullmatch(r'(\d{8})-(\d{8})', p.stem)
        if match:
            try:
                start = datetime.strptime(match.group(1), '%d%m%Y').date()
                end = datetime.strptime(match.group(2), '%d%m%Y').date()
            except ValueError:
                # Invalid date format: treat as an ordinary, undated filename.
                pass
            else:
                if not start <= today <= end:
                    continue
        files.append(p)
    return sorted(files, key=lambda p: p.name.casefold())


@app.get('/api/info/list')
def info_list():
    slides = []
    for file in info_files():
        try:
            with fitz.open(file) as doc:
                count = len(doc)
            version = f'{file.stat().st_mtime_ns}-{file.stat().st_size}'
            fid = hashlib.sha256(file.name.encode('utf-8')).hexdigest()[:20]
            for n in range(count):
                slides.append({'name': file.name, 'page': n + 1, 'pages': count,
                               'url': f'/api/info/page/{fid}/{n}?v={version}'})
        except Exception:
            continue  # Invalid PDFs do not interrupt the board.
    return jsonify({'slides': slides}), 200, {'Cache-Control': 'no-store, max-age=0'}


@app.get('/api/info/page/<fid>/<int:page>')
def info_page(fid, page):
    for file in info_files():
        if hashlib.sha256(file.name.encode('utf-8')).hexdigest()[:20] != fid:
            continue
        try:
            with fitz.open(file) as doc:
                if page < 0 or page >= len(doc):
                    abort(404)
                # Limit raster resolution to avoid excessive memory usage.
                pix = doc[page].get_pixmap(matrix=fitz.Matrix(1.5, 1.5), alpha=False)
                result = pix.tobytes('png')
            return Response(result, mimetype='image/png', headers={'Cache-Control': 'no-store, max-age=0'})
        except Exception:
            abort(422)
    abort(404)

"use strict";

const LOADING='<div class="loading"><span class="spinner-border spinner-border-sm"></span>加载中...</div>';
const EMPTY='<div class="empty"><i class="bi bi-inbox"></i>暂无数据';

function esc(s){return String(s==null?"":s).replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]))}
function colorOf(v){
  if(typeof v==="string"){v=v.replace(/[%,]/g,"");if(!/^-?[\d.]+$/.test(v))return"flat"}
  if(v==null||isNaN(v))return"flat";
  if(v>0)return"up";if(v<0)return"down";return"flat";
}
function amt(v){if(v==null||v===""||v==="-")return"-";v=Number(v);if(isNaN(v))return String(v);
  if(Math.abs(v)>=1e8)return (v/1e8).toFixed(2)+"亿";if(Math.abs(v)>=1e4)return (v/1e4).toFixed(0)+"万";
  return v.toFixed(0)}

async function api(name,params={}){
  const qs=new URLSearchParams(params).toString();
  const r=await fetch("/api/"+name+(qs?"?"+qs:""));
  const j=await r.json();
  if(!r.ok||j.error)throw new Error(j.error||("HTTP "+r.status));
  return j;
}

/* 从各种格式的代码中提取6位股票代码 */
function stockCode(c){
  if(c==null)return null;
  c=String(c).toLowerCase();
  const m=c.match(/(\d{6})/);
  return m?m[1]:null;
}

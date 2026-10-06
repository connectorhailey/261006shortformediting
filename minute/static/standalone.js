const el=id=>document.getElementById(id);let turns=[],controller=null,version=0;
function payload(){return {mode:el('quickMode').value,transcript:el('quickTranscript').value.trim(),before:el('quickBefore').value.trim(),after:el('quickAfter').value.trim(),start:Number(el('quickStart').value),end:Number(el('quickEnd').value),question:el('quickQuestion').value.trim()||'문장 끊김과 맥락 누락을 점검하고 수정 방향을 제안해주세요.'}}
function reset(){version++;controller?.abort();controller=null;turns=[];el('quickHistory').replaceChildren();el('quickResult').replaceChildren();el('quickStatus').textContent='';el('quickAsk').disabled=false}
el('quickMode').onchange=()=>{reset();const timed=el('quickMode').value==='srt';el('quickTimes').hidden=!timed;el('quickContext').hidden=timed;el('quickTranscriptLabel').textContent=timed?'시간이 포함된 SRT 자막 (앞뒤 내용도 포함해 붙여넣기)':'선택한 숏폼의 자막';el('quickTranscript').placeholder=timed?'1\n00:00:00,000 --> 00:00:05,000\n첫 번째 문장입니다.\n\n2\n00:00:05,000 --> 00:00:10,000\n다음 문장입니다.':'만들고 싶은 숏폼 구간의 자막을 붙여넣으세요.'};
el('quickForget').onclick=()=>{el('quickKey').value='';el('quickConsent').checked=false;reset();el('quickStatus').textContent='키를 지웠습니다.'};
el('quickClear').onclick=()=>{reset();el('quickQuestion').value=''};
window.addEventListener('pagehide',()=>{el('quickKey').value='';controller?.abort()});
el('quickAsk').onclick=async()=>{
 const key=el('quickKey').value.trim(),input=payload();
 if(!key){el('quickStatus').textContent='내 Gemini API 키를 입력해주세요.';el('quickKey').focus();return}
 if(!input.transcript){el('quickStatus').textContent='상담할 자막을 붙여넣어주세요.';el('quickTranscript').focus();return}
 if(!el('quickConsent').checked){el('quickStatus').textContent='데이터 전송·비용 안내를 확인해주세요.';el('quickConsent').focus();return}
 const snapshot=JSON.stringify({...input,question:''}),thisVersion=version;controller=new AbortController();el('quickAsk').disabled=true;el('quickResult').replaceChildren();el('quickStatus').textContent='Gemini가 자막을 검토하고 있습니다…';
 try{
  const response=await fetch('/api/consult',{method:'POST',headers:{'Content-Type':'application/json','X-Gemini-Key':key},signal:controller.signal,body:JSON.stringify({...input,history:turns})});
  let result;try{result=await response.json()}catch{throw Error('상담 API가 연결되지 않았습니다. 최신 코드로 Vercel 또는 Netlify를 재배포해주세요.')}
  if(!response.ok)throw Error(result.detail||'상담에 실패했습니다. 다시 시도해주세요.');
  if(thisVersion!==version)return;
  turns.push({role:'user',text:input.question},{role:'assistant',text:JSON.stringify(result).slice(0,4000)});turns=turns.slice(-8);
  for(const [label,text]of [['나',input.question],['상담원',result.summary]]){const p=document.createElement('p'),b=document.createElement('b');b.textContent=label+' · ';p.append(b,document.createTextNode(text));el('quickHistory').append(p)}while(el('quickHistory').children.length>8)el('quickHistory').firstChild.remove();
  for(const issue of result.issues){const p=document.createElement('p');p.textContent=issue.kind+' · '+issue.detail;el('quickResult').append(p)}
  const limit=document.createElement('p');limit.className='muted';limit.textContent='확인 범위: '+result.limitations;el('quickResult').append(limit);
  if(result.suggestion){const s=result.suggestion,p=document.createElement('p');p.textContent=`제안: ${s.start.toFixed(1)}초 ~ ${s.end.toFixed(1)}초 · ${s.reason}`;const button=document.createElement('button');button.textContent='상담 구간에 적용';button.onclick=()=>{if(JSON.stringify({...payload(),question:''})!==snapshot){el('quickStatus').textContent='자막이나 구간이 바뀌었습니다. 다시 상담해주세요.';return}el('quickStart').value=s.start;el('quickEnd').value=s.end;button.disabled=true;el('quickStatus').textContent='다음 상담의 구간에 적용했습니다. 영상 파일은 변경하지 않았습니다.'};el('quickResult').append(p,button)}
  el('quickQuestion').value='';el('quickStatus').textContent='상담 완료 · 후속 질문을 이어서 입력할 수 있습니다.';
 }catch(e){if(thisVersion===version)el('quickStatus').textContent=e.name==='AbortError'?'요청을 취소했습니다. 이미 전송된 요청에는 비용이 발생할 수 있습니다.':e.message}
 finally{if(thisVersion===version){el('quickAsk').disabled=false;controller=null}}
};

import os, sqlite3, json, time, secrets, hashlib, hmac, subprocess, shutil, re
from pathlib import Path
from contextlib import contextmanager
from urllib.parse import urlparse
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from advisor import consult, Turn

ROOT=Path(__file__).parent
DATA=Path(os.environ.get('MINUTE_DATA',str(ROOT/'data'))).resolve(); DATA.mkdir(parents=True,exist_ok=True)
MAX_BYTES=5*1024**3
ORIGIN=os.environ.get('PUBLIC_ORIGIN','http://localhost:8000')
@contextmanager
def db():
 c=sqlite3.connect(DATA/'minute.db',timeout=30); c.row_factory=sqlite3.Row
 try: yield c; c.commit()
 except: c.rollback(); raise
 finally: c.close()
with db() as c:
 c.executescript('''PRAGMA journal_mode=WAL;
 CREATE TABLE IF NOT EXISTS users(id TEXT PRIMARY KEY,email TEXT UNIQUE,password TEXT);
 CREATE TABLE IF NOT EXISTS sessions(token TEXT PRIMARY KEY,user TEXT,expires REAL);
 CREATE TABLE IF NOT EXISTS projects(id TEXT PRIMARY KEY,user TEXT,name TEXT,state TEXT,created REAL,duration REAL DEFAULT 0,edit TEXT DEFAULT '{}',recommendations TEXT DEFAULT '[]',error TEXT DEFAULT '');
 CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY,project TEXT,kind TEXT,state TEXT,created REAL,updated REAL,payload TEXT);
 CREATE TABLE IF NOT EXISTS rates(key TEXT,stamp REAL);
 CREATE INDEX IF NOT EXISTS rates_key ON rates(key,stamp);
 ''')
app=FastAPI()
app.add_middleware(CORSMiddleware,allow_origins=[ORIGIN],allow_credentials=True,allow_methods=['GET','POST','PUT','DELETE'],allow_headers=['Content-Type','X-Filename','X-Seconds','Range','X-Gemini-Key'],expose_headers=['Content-Length','Content-Range','Accept-Ranges'])
@app.middleware('http')
async def guard(request,call_next):
 if request.method not in ('GET','HEAD','OPTIONS') and request.headers.get('origin') not in (None,ORIGIN): return JSONResponse({'detail':'허용되지 않은 요청입니다.'},403)
 if request.url.path.startswith('/api'):
  try: limit('requests:'+request.client.host,300,60)
  except HTTPException as e: return JSONResponse({'detail':e.detail},e.status_code)
 response=await call_next(request)
 response.headers.update({'X-Content-Type-Options':'nosniff','Referrer-Policy':'same-origin','X-Frame-Options':'DENY','Cache-Control':'no-store' if request.url.path.startswith('/api') else 'no-cache'})
 return response

def limit(key,n,period=3600):
 with db() as c:
  c.execute('BEGIN IMMEDIATE'); c.execute('DELETE FROM rates WHERE stamp<?',(time.time()-86400,))
  if c.execute('SELECT count(*) FROM rates WHERE key=? AND stamp>?',(key,time.time()-period)).fetchone()[0]>=n: raise HTTPException(429,'이용 한도를 초과했습니다. 잠시 후 다시 시도하세요.')
  c.execute('INSERT INTO rates VALUES (?,?)',(key,time.time()))
def user(request):
 token=hashlib.sha256(request.cookies.get('minute_session','').encode()).hexdigest()
 with db() as c: row=c.execute('SELECT user FROM sessions WHERE token=? AND expires>?',(token,time.time())).fetchone()
 if not row: raise HTTPException(401,'로그인이 필요합니다.')
 return row[0]
def project(pid,uid):
 with db() as c: p=c.execute('SELECT * FROM projects WHERE id=? AND user=?',(pid,uid)).fetchone()
 if not p: raise HTTPException(404,'프로젝트를 찾을 수 없습니다.')
 return dict(p)
def view(p):
 p=dict(p); p.pop('user',None)
 for k in ('edit','recommendations'): p[k]=json.loads(p[k])
 p['expires']=p['created']+7*86400
 return p
class Auth(BaseModel):
 email:str=Field(max_length=254)
 password:str=Field(min_length=12,max_length=128)
def password(value,salt): return hashlib.scrypt(value.encode(),salt=salt.encode(),n=16384,r=8,p=1).hex()
@app.post('/api/auth/{action}')
def auth(action:str,body:Auth,request:Request):
 if action not in ('login','register'): raise HTTPException(404)
 limit('auth:'+request.client.host,15)
 email=body.email.strip().lower()
 if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',email): raise HTTPException(400,'이메일을 확인하세요.')
 with db() as c:
  if action=='register':
   salt=secrets.token_hex(16)
   try: c.execute('INSERT INTO users VALUES (?,?,?)',(secrets.token_hex(16),email,salt+':'+password(body.password,salt)))
   except sqlite3.IntegrityError: raise HTTPException(400,'가입할 수 없습니다. 로그인 정보를 확인하세요.')
  u=c.execute('SELECT * FROM users WHERE email=?',(email,)).fetchone()
  salt,expected=u['password'].split(':') if u else ('none','none')
  if not hmac.compare_digest(password(body.password,salt),expected): raise HTTPException(401,'이메일 또는 비밀번호를 확인하세요.')
  token=secrets.token_urlsafe(32); c.execute('INSERT INTO sessions VALUES (?,?,?)',(hashlib.sha256(token.encode()).hexdigest(),u['id'],time.time()+7*86400))
 response=JSONResponse({'email':email}); response.set_cookie('minute_session',token,httponly=True,secure=ORIGIN.startswith('https:'),samesite='strict',max_age=604800); return response
@app.post('/api/logout')
def logout(request:Request):
 with db() as c: c.execute('DELETE FROM sessions WHERE token=?',(hashlib.sha256(request.cookies.get('minute_session','').encode()).hexdigest(),))
 r=JSONResponse({'ok':True}); r.delete_cookie('minute_session'); return r
@app.get('/api/me')
def me(request:Request):
 uid=user(request)
 with db() as c: return dict(c.execute('SELECT email FROM users WHERE id=?',(uid,)).fetchone())
@app.get('/api/capabilities')
def capabilities(): return {'analysis':bool(os.environ.get('OPENAI_API_KEY')),'maxBytes':MAX_BYTES,'maxSeconds':1200,'retentionDays':7,'dailyJobs':10,'youtubeImport':False}
@app.get('/api/projects')
def projects(request:Request):
 uid=user(request)
 with db() as c: return [view(x) for x in c.execute('SELECT * FROM projects WHERE user=? ORDER BY created DESC',(uid,))]
@app.post('/api/projects')
async def upload(request:Request):
 uid=user(request); limit('upload:'+uid,5,86400)
 if shutil.disk_usage(DATA).free<MAX_BYTES+2*1024**3: raise HTTPException(503,'저장 공간이 부족합니다. 나중에 다시 시도하세요.')
 name=request.headers.get('x-filename','video.mp4'); name=__import__('urllib.parse',fromlist=['unquote']).unquote(name)
 if Path(name).suffix.lower() not in ('.mp4','.mov','.webm'): raise HTTPException(415,'MP4, MOV, WebM 파일만 지원합니다.')
 with db() as c:
  c.execute('BEGIN IMMEDIATE')
  if c.execute('SELECT count(*) FROM projects WHERE user=?',(uid,)).fetchone()[0]>=5: raise HTTPException(429,'프로젝트는 최대 5개 보관할 수 있습니다. 기존 프로젝트를 삭제하세요.')
  pid=secrets.token_hex(16); c.execute('INSERT INTO projects(id,user,name,state,created) VALUES (?,?,?,?,?)',(pid,uid,Path(name).name[:180],'uploading',time.time()))
 folder=DATA/pid; folder.mkdir(); size=0
 try:
  with (folder/'source').open('wb') as f:
   async for chunk in request.stream():
    size+=len(chunk)
    if size>MAX_BYTES: raise HTTPException(413,'최대 용량은 5GB입니다.')
    f.write(chunk)
  seconds_text=request.headers.get('x-seconds','60')
  seconds=int(seconds_text) if seconds_text in ('30','60','90') else 60
  if seconds not in (30,60,90): seconds=60
  enqueue(pid,'probe',{'seconds':seconds},'analyzing')
 except BaseException:
  shutil.rmtree(folder,ignore_errors=True)
  with db() as c: c.execute('DELETE FROM projects WHERE id=?',(pid,))
  raise
 return {'id':pid}
def enqueue(pid,kind,payload,state):
 with db() as c:
  c.execute('BEGIN IMMEDIATE')
  if c.execute("SELECT 1 FROM jobs WHERE project=? AND state IN ('queued','running')",(pid,)).fetchone(): raise HTTPException(409,'진행 중인 작업이 있습니다.')
  c.execute('INSERT INTO jobs VALUES (?,?,?,?,?,?,?)',(secrets.token_hex(16),pid,kind,'queued',time.time(),time.time(),json.dumps(payload)))
  c.execute('UPDATE projects SET state=?,error=? WHERE id=?',(state,'',pid))
class Caption(BaseModel):
 start:float=Field(ge=0,le=1200); end:float=Field(gt=0,le=1200); text:str=Field(max_length=160)
class Edit(BaseModel):
 start:float=Field(ge=0); end:float=Field(gt=0)
 fit:str='cover'; x:float=Field(default=.5,ge=0,le=1); y:float=Field(default=.5,ge=0,le=1)
 title:str=Field(default='',max_length=60)
 size:int=Field(default=56,ge=24,le=100); color:str='#FFFFFF'; background:bool=True; position:int=Field(default=82,ge=15,le=90)
 captions:list[Caption]=Field(default_factory=list,max_length=600)
def validate_edit(e,p):
 if e.end>p['duration']+.01 or not 1<=e.end-e.start<=95: raise HTTPException(400,'구간은 원본 안에서 1~95초로 지정하세요.')
 if e.fit not in ('cover','contain') or not re.fullmatch('#[0-9a-fA-F]{6}',e.color): raise HTTPException(400,'편집 설정이 올바르지 않습니다.')
 if any(s.end<=s.start for s in e.captions): raise HTTPException(400,'자막 종료 시간은 시작 시간보다 커야 합니다.')
@app.get('/api/projects/{pid}')
def getproject(pid:str,request:Request): return view(project(pid,user(request)))
@app.put('/api/projects/{pid}/edit')
def edit(pid:str,e:Edit,request:Request):
 p=project(pid,user(request)); validate_edit(e,p)
 if p['state'] in ('analyzing','rendering','previewing','uploading'): raise HTTPException(409,'처리 완료 후 수정하세요.')
 with db() as c: c.execute("UPDATE projects SET edit=?,state='editable' WHERE id=?",(e.model_dump_json(),pid))
 return {'ok':True}
@app.post('/api/projects/{pid}/render')
def render(pid:str,e:Edit,request:Request):
 uid=user(request); p=project(pid,uid); validate_edit(e,p); limit('jobs:'+uid,10,86400)
 enqueue(pid,'render',e.model_dump(),'rendering'); return {'ok':True}
@app.post('/api/projects/{pid}/preview')
def preview(pid:str,e:Edit,request:Request):
 uid=user(request); p=project(pid,uid); validate_edit(e,p); limit('preview:'+uid,30)
 enqueue(pid,'preview',e.model_dump(),'previewing'); return {'ok':True}
@app.post('/api/projects/{pid}/analyze')
def analyze(pid:str,request:Request,seconds:int=60):
 uid=user(request); project(pid,uid)
 if seconds not in (30,60,90): raise HTTPException(400)
 if not os.environ.get('OPENAI_API_KEY'): raise HTTPException(503,'자동 분석이 연결되지 않았습니다. 직접 구간을 지정하세요.')
 limit('jobs:'+uid,10,86400); enqueue(pid,'analyze',{'seconds':seconds},'analyzing'); return {'ok':True}
@app.delete('/api/projects/{pid}')
def delete(pid:str,request:Request):
 project(pid,user(request))
 with db() as c:
  c.execute('BEGIN IMMEDIATE')
  if c.execute("SELECT 1 FROM jobs WHERE project=? AND state='running'",(pid,)).fetchone(): raise HTTPException(409,'현재 처리 중입니다. 완료 후 삭제하세요.')
  c.execute('DELETE FROM jobs WHERE project=?',(pid,)); c.execute('DELETE FROM projects WHERE id=?',(pid,))
 shutil.rmtree(DATA/pid,ignore_errors=True); return {'ok':True}
@app.get('/api/projects/{pid}/media/{kind}')
def media(pid:str,kind:str,request:Request,download:bool=False):
 p=project(pid,user(request))
 if kind not in ('source','result','preview'): raise HTTPException(404)
 path=DATA/pid/('result.mp4' if kind=='result' else 'preview.png' if kind=='preview' else 'source')
 if not path.exists() or (kind=='result' and p['state']!='complete'): raise HTTPException(404)
 return FileResponse(path,filename='minute.mp4' if download else None,media_type='video/mp4' if kind=='result' else 'image/png' if kind=='preview' else 'video/webm' if p['name'].lower().endswith('.webm') else 'video/mp4')
class Consultation(BaseModel):
 edit:Edit
 question:str=Field(default='문장이 중간에 끊기는지, 맥락이 부족한지 확인하고 구간 수정을 제안해주세요.',min_length=1,max_length=1500)
 history:list[Turn]=Field(default_factory=list,max_length=8)
@app.post('/api/projects/{pid}/consult')
async def consultation(pid:str,body:Consultation,request:Request):
 uid=user(request); p=project(pid,uid); validate_edit(body.edit,p)
 key=request.headers.get('x-gemini-key','').strip()
 if not key or len(key)>200 or not re.fullmatch(r'[A-Za-z0-9_-]+',key):
  raise HTTPException(400,'Gemini API 키를 입력하세요.')
 limit('consult:'+uid,20)
 return await consult(key,body.edit.model_dump(),p['duration'],body.question,body.history)
app.mount('/',StaticFiles(directory=ROOT/'static',html=True),name='static')

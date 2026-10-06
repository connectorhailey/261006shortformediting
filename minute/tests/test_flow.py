"""Real FFmpeg integration test; synthesized fixture is NOT speech-quality acceptance."""
import os,tempfile,sys,json,subprocess,time
from pathlib import Path
os.environ['MINUTE_DATA']=tempfile.mkdtemp(prefix='minute-test-')
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from fastapi.testclient import TestClient
from app import app,db,DATA
from worker import process,cleanup

def drain():
 with db() as c:
  row=c.execute("SELECT * FROM jobs WHERE state='queued' ORDER BY created LIMIT 1").fetchone()
  assert row
  c.execute("UPDATE jobs SET state='running' WHERE id=?",(row['id'],))
 try:
  process(dict(row))
  with db() as c: c.execute("UPDATE jobs SET state='done' WHERE id=?",(row['id'],))
 except Exception:
  with db() as c:
   c.execute("UPDATE jobs SET state='failed' WHERE id=?",(row['id'],))
   c.execute("UPDATE projects SET state='failed' WHERE id=?",(row['project'],))
  raise

def test_full_flow():
 source=DATA/'fixture.mp4'
 subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i','testsrc2=size=320x180:rate=12','-f','lavfi','-i','sine=frequency=440:sample_rate=48000','-t','600','-c:v','libx264','-preset','ultrafast','-threads','2','-c:a','aac','-shortest',str(source)],check=True)
 print('fixture ready',flush=True)
 a,b=TestClient(app),TestClient(app)
 assert a.post('/api/projects',content=b'x',headers={'x-filename':'x.mp4'}).status_code==401
 assert a.post('/api/auth/register',json={'email':'one@example.com','password':'test-password-123'}).status_code==200
 assert b.post('/api/auth/register',json={'email':'two@example.com','password':'test-password-123'}).status_code==200
 assert a.post('/api/projects',content=b'x',headers={'x-filename':'bad.exe'}).status_code==415
 r=a.post('/api/projects',content=source.read_bytes(),headers={'x-filename':'ten-minute.mp4'}); assert r.status_code==200,r.text
 pid=r.json()['id']; base='/api/projects/'+pid
 assert b.get(base).status_code==404
 assert b.get(base+'/media/source').status_code==404
 assert b.delete(base).status_code==404
 drain(); p=a.get(base).json(); assert p['state']=='editable' and p['duration']>=600
 e=p['edit']; e.update(start=120,end=180,title='나만의 일 분',captions=[{'start':120,'end':125,'text':'한국어 자막 테스트입니다.'},{'start':125,'end':130,'text':'영상과 소리를 함께 확인합니다.'}])
 assert a.put(base+'/edit',json=e).status_code==200
 # A new browser connection with the same session restores edits from the database.
 refreshed=TestClient(app);refreshed.cookies.update(a.cookies)
 assert refreshed.get(base).json()['edit']['start']==120
 assert a.post(base+'/preview',json=e).status_code==200
 drain(); assert a.get(base+'/media/preview').status_code==200
 assert a.post(base+'/render',json=e).status_code==200
 assert a.post(base+'/render',json=e).status_code==409
 assert a.get(base).json()['state']=='rendering'
 drain(); assert a.get(base).json()['state']=='complete'
 result=a.get(base+'/media/result?download=true');assert result.status_code==200 and 'attachment' in result.headers['content-disposition']
 assert b.get(base+'/media/result').status_code==404
 artifacts=Path(__file__).resolve().parents[1]/'artifacts'; artifacts.mkdir(exist_ok=True)
 (artifacts/'render-test.mp4').write_bytes(result.content)
 (artifacts/'render-test.png').write_bytes((DATA/pid/'preview.png').read_bytes())
 info=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_format','-show_streams','-of','json',str(DATA/pid/'result.mp4')]))
 v=next(x for x in info['streams'] if x['codec_type']=='video');audio=next(x for x in info['streams'] if x['codec_type']=='audio')
 assert (v['width'],v['height'],v['codec_name'])==(1080,1920,'h264')
 assert audio['codec_name']=='aac'
 assert abs(float(v['duration'])-60)<.1
 assert abs(float(v['start_time'])-float(audio['start_time']))<.1
 assert abs(float(v['duration'])-float(audio['duration']))<.1
 assert a.post('/api/projects',content=b'not a video',headers={'x-filename':'broken.mp4'}).status_code==200
 try:drain();raise AssertionError('invalid media accepted')
 except (RuntimeError,ValueError):pass
 assert a.post(base+'/render',json={**e,'end':1500}).status_code==400
 assert a.post(base+'/render',json=e,headers={'Origin':'https://evil.example'}).status_code==403
 assert a.delete(base).status_code==200
 assert not (DATA/pid).exists()
 with db() as c: c.execute('UPDATE projects SET created=?',(time.time()-8*86400,))
 cleanup(); assert a.get('/api/projects').json()==[]
 print(json.dumps({'fixture_seconds':600,'output_seconds':float(v['duration']),'dimensions':[1080,1920],'video':v['codec_name'],'audio':audio['codec_name'],'av_start_delta':abs(float(v['start_time'])-float(audio['start_time'])),'download_bytes':len(result.content),'data_directory':str(DATA)}))
if __name__=='__main__':test_full_flow()

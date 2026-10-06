import os,tempfile,sys,json,unittest
from pathlib import Path
from unittest.mock import patch,AsyncMock
os.environ['MINUTE_DATA']=tempfile.mkdtemp(prefix='minute-advisor-')
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from fastapi.testclient import TestClient
import httpx
from app import app,db
from advisor import MODEL

class ConsultationTests(unittest.TestCase):
 def setUp(self):
  self.a=TestClient(app);self.b=TestClient(app)
  self.a.post('/api/auth/register',json={'email':'a@example.com','password':'strong-test-password'})
  self.b.post('/api/auth/register',json={'email':'b@example.com','password':'strong-test-password'})
  self.a.post('/api/auth/login',json={'email':'a@example.com','password':'strong-test-password'})
  self.b.post('/api/auth/login',json={'email':'b@example.com','password':'strong-test-password'})
  with db() as c:
   uid=c.execute("SELECT id FROM users WHERE email='a@example.com'").fetchone()[0]
   c.execute("INSERT OR REPLACE INTO projects(id,user,name,state,created,duration) VALUES ('p',?,'test','editable',0,200)",(uid,))
   c.execute('DELETE FROM rates')
  self.e={'start':20,'end':80,'captions':[{'start':10,'end':20,'text':'이야기의 배경입니다.'},{'start':20,'end':70,'text':'이것은 본문입니다.'},{'start':70,'end':85,'text':'이것이 결론입니다.'}]}
  self.answer={'summary':'끝 문장이 잘립니다.','issues':[{'kind':'문장 끊김','detail':'끝 자막이 85초까지 이어집니다.'}],'suggestion':{'start':10,'end':85,'reason':'배경과 결론 포함'},'limitations':'자막만 검토했습니다.'}
 def call(self,response):
  mock=AsyncMock(return_value=response)
  with patch('advisor.httpx.AsyncClient.post',mock):
   r=self.a.post('/api/projects/p/consult',headers={'X-Gemini-Key':'test-private-key'},json={'edit':self.e})
  return r,mock
 def good(self):return httpx.Response(200,json={'candidates':[{'finishReason':'STOP','content':{'parts':[{'text':json.dumps(self.answer)}]}}]})
 def test_success_and_no_key_persistence(self):
  r,m=self.call(self.good());self.assertEqual(r.status_code,200,r.text);self.assertEqual(r.json()['suggestion']['end'],85)
  self.assertIn(MODEL,m.call_args.args[0]);self.assertNotIn('key=',m.call_args.args[0]);self.assertEqual(m.call_args.kwargs['headers']['x-goog-api-key'],'test-private-key')
  self.assertNotIn('test-private-key',r.text)
  with db() as c:self.assertNotIn('test-private-key',''.join(c.iterdump()))
 def test_auth_and_ownership(self):
  self.assertEqual(TestClient(app).post('/api/projects/p/consult',json={'edit':self.e}).status_code,401)
  self.assertEqual(self.b.post('/api/projects/p/consult',json={'edit':self.e}).status_code,404)
  self.assertEqual(self.a.post('/api/projects/p/consult',json={'edit':self.e}).status_code,400)
 def test_no_captions_no_api_call(self):
  self.e['captions']=[];r,m=self.call(self.good());self.assertEqual(r.status_code,400);m.assert_not_called()
 def test_invalid_model_and_quota(self):
  for status in (403,404,429):
   r,_=self.call(httpx.Response(status,json={'error':{'message':'test-private-key'}}));self.assertEqual(r.status_code,status);self.assertNotIn('test-private-key',r.text)
 def test_invalid_suggestion(self):
  self.answer['suggestion']['end']=199;r,_=self.call(self.good());self.assertEqual(r.status_code,200);self.assertIsNone(r.json()['suggestion'])
 def test_malformed_response(self):
  r,_=self.call(httpx.Response(200,json={'candidates':[]}));self.assertEqual(r.status_code,502)
 def test_timeout(self):
  with patch('advisor.httpx.AsyncClient.post',AsyncMock(side_effect=httpx.ReadTimeout('private'))):
   r=self.a.post('/api/projects/p/consult',headers={'X-Gemini-Key':'test-private-key'},json={'edit':self.e})
  self.assertEqual(r.status_code,504);self.assertNotIn('private',r.text)
if __name__=='__main__':unittest.main()

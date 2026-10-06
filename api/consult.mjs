import {handleConsult} from '../server/consult.mjs';
export default async function handler(req,res){
 const headers=new Headers();for(const [k,v] of Object.entries(req.headers))if(v!==undefined)headers.set(k,Array.isArray(v)?v.join(','):v);
 const host=req.headers.host;
 const origin=`${req.headers['x-forwarded-proto']==='http'?'http':'https'}://${host}`;
 const body=req.method==='POST'?(typeof req.body==='string'?req.body:JSON.stringify(req.body||{})):undefined;
 const response=await handleConsult(new Request(origin+'/api/consult',{method:req.method,headers,body}));
 for(const [k,v] of response.headers)res.setHeader(k,v);res.statusCode=response.status;res.end(await response.text());
}

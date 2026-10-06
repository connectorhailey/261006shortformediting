import {cp,mkdir,writeFile,rm} from 'node:fs/promises';
const origin=(process.env.MINUTE_API_ORIGIN||'').replace(/\/$/,'');
if(origin){const url=new URL(origin);if(url.protocol!=='https:'||url.pathname!=='/'||url.search||url.hash||url.username||url.password)throw Error('MINUTE_API_ORIGIN must be an HTTPS origin, e.g. https://api.example.com');}
await rm('dist',{recursive:true,force:true});await mkdir('dist',{recursive:true});
await cp('minute/static','dist',{recursive:true});
await writeFile('dist/config.js','window.MINUTE_CONFIG = '+JSON.stringify({apiOrigin:origin,backendConfigured:!!origin})+';\n');
console.log(origin?'Frontend built with external video server configured.':'Frontend built. Video server is not configured; processing stays unavailable.');

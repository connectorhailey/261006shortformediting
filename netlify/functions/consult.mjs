import {handleConsult} from '../../server/consult.mjs';
export default request=>handleConsult(request);
export const config={path:'/api/consult'};

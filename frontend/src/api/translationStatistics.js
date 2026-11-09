import api from './index'
export const getTranslationStatistics=(params,config={})=>api.get('/projects/translation/statistics',{...config,params})

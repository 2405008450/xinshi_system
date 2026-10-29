export const sampleAudioExtensions = ['mp3','mp2','wav','m4a','aac','ogg','oga','opus','flac','aif','aiff','wma','amr','ape','mid','midi','caf','au','snd','mka','ac3','dts','wv']
export const sampleVideoExtensions = ['mp4','mov','m4v','webm','mkv','avi','wmv','mpeg','mpg','3gp','3g2','ts','mts','m2ts','vob','flv','ogv','rm','rmvb','asf','f4v','divx','m2v']
export const sampleAccept = [...sampleAudioExtensions,...sampleVideoExtensions].map(value=>'.'+value).join(',')
export const sampleCategories = ['interpretation_sample','annotation_sample']
export const maxSampleBytes = 200*1024*1024
export const sampleExtension = name => String(name||'').split('.').at(-1).toLowerCase()
export const sampleIsVideo = name => sampleVideoExtensions.includes(sampleExtension(name))
export const validSample = file => [...sampleAudioExtensions,...sampleVideoExtensions].includes(sampleExtension(file.name)) && file.size>0 && file.size<=maxSampleBytes

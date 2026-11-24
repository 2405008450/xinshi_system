import io,json,re,base64
from urllib.request import urlopen
from uuid import uuid4
from PIL import Image
from playwright.sync_api import sync_playwright,expect
BASE='http://127.0.0.1:3000'
compiled=urlopen(BASE+'/src/views/project/ProjectWorkspace.vue',timeout=10).read().decode()
vue=re.search(r'from ["\x27]([^"\x27]*/vue\.js[^"\x27]*)',compiled).group(1)
html=f'''<meta charset="utf-8"><div id="app"></div><script type="module">
import {{createApp,h,ref}} from {json.dumps(vue)};
import Editor from '/src/components/common/MailBodyEditor.vue';
createApp({{setup(){{const images=ref([]),text=ref('正文'),html=ref('');return()=>h(Editor,{{images:images.value,modelValue:text.value,htmlValue:html.value,'onUpdate:images':v=>images.value=v,'onUpdate:modelValue':v=>text.value=v,'onUpdate:htmlValue':v=>html.value=v}})}}}}).mount('#app');
</script>'''
buffer=io.BytesIO();Image.new('RGB',(4,4),'white').save(buffer,format='PNG');png=buffer.getvalue()
with sync_playwright() as p:
 browser=p.chromium.launch(channel='msedge')
 page=browser.new_page();page.set_default_timeout(10000);posts=[];errors=[]
 page.on('pageerror',lambda e:errors.append(str(e)))
 def api(route):
  if route.request.method=='POST':
   posts.append(route.request.url);route.fulfill(json={'id':str(uuid4()),'original_name':'截图.png','content_type':'image/png','file_size':100,'width':4,'height':4})
  else:route.fulfill(json={})
 page.route(BASE+'/api/**',api)
 page.route(BASE+'/mail-images-check',lambda r:r.fulfill(content_type='text/html',body=html))
 page.goto(BASE+'/mail-images-check')
 page.locator('input[type=file]').set_input_files([{'name':f'{i}.png','mimeType':'image/png','buffer':png} for i in range(6)])
 expect(page.locator('.mail-body-editor__prose img')).to_have_count(6)
 expect(page.locator('.el-upload button')).to_be_enabled()
 encoded=base64.b64encode(png).decode()
 for event,count in [('paste',12),('drop',18)]:
  page.evaluate("""({event,encoded})=>{
   const data=new DataTransfer(),bytes=Uint8Array.from(atob(encoded),c=>c.charCodeAt(0));
   for(let i=0;i<6;i++)data.items.add(new File([bytes],i+'.png',{type:'image/png'}));
   const target=document.querySelector(event==='paste'?'.mail-body-editor__content':'.mail-body-editor');
   target.dispatchEvent(event==='paste'?new ClipboardEvent('paste',{clipboardData:data,bubbles:true,cancelable:true}):new DragEvent('drop',{dataTransfer:data,bubbles:true,cancelable:true}));
  }""",{'event':event,'encoded':encoded})
  expect(page.locator('.mail-body-editor__prose img')).to_have_count(count)
 expect(page.locator('.mail-body-editor__toolbar strong')).to_contain_text('18 张')
 expect(page.locator('.el-upload button')).to_be_enabled()
 assert len(posts)==18 and not errors,(posts,errors)
 browser.close()
print('PASS selected 6, pasted 6 and dropped 6 images; all 18 retained and upload remains available')

"""开发笔记入口、富文本、截图附件、版本、草稿与权限；拦截所有业务接口。"""
import base64
from copy import deepcopy
from io import BytesIO
import json
import re
from urllib.parse import urlparse
from urllib.request import urlopen
from uuid import uuid4
from PIL import Image
from playwright.sync_api import sync_playwright, expect

BASE='http://localhost:3000'


def run():
    source=urlopen(BASE+'/src/main.js').read().decode()
    vue=re.search(r'from ["\']([^"\']*/vue\.js[^"\']*)',source).group(1)
    source=urlopen(BASE+'/src/router/index.js').read().decode()
    router=re.search(r'from ["\']([^"\']*/vue-router\.js[^"\']*)',source).group(1)
    html='''<!doctype html><meta charset="UTF-8"><link rel="stylesheet" href="/node_modules/element-plus/dist/index.css"><div id="app" style="height:95vh"></div><script type="module">
    import {createApp,h} from VUE;import {createRouter,createWebHistory} from ROUTER;
    import Workspace from '/src/components/chat/ChatWorkspace.vue';import AppForm from '/src/components/common/AppForm.vue';import Dialog from '/src/components/common/DraggableFormDialog.vue';
    const router=createRouter({history:createWebHistory(),routes:[{path:'/development-notes-test',component:{render:()=>null}}]});const app=createApp({render:()=>h(Workspace,{maximized:true,title:'消息',sessions:[]})});app.component('AppForm',AppForm);app.component('DraggableFormDialog',Dialog);app.use(router);app.mount('#app');</script>'''.replace('from VUE','from '+json.dumps(vue)).replace('from ROUTER','from '+json.dumps(router))
    owners=[dict(id='a',name='赵震锋',can_edit=True,blocks=[]),dict(id='b',name='黄运坚',can_edit=False,blocks=[])]
    other_id=str(uuid4())
    owners[1]['blocks']=[dict(id=other_id,owner_id='b',title='运坚的笔记',document={'type':'doc','content':[{'type':'paragraph','content':[{'type':'text','text':'另一人的只读区域'}]}]},files=[],attachment_ids=[],revision=1,saved_at='2026-11-27T10:00:00+08:00')]
    histories={};writes=[];files={};errors=[];authorized=True
    stream=BytesIO();Image.new('RGB',(8,8),'blue').save(stream,format='PNG');png=stream.getvalue()
    def api(route):
        path=urlparse(route.request.url).path;method=route.request.method
        data={'items':[],'groups':[],'folders':[],'people':[],'users':[],'departments':[],'count':0,'ready':True,'hasMore':False}
        if path=='/api/development-notes/access':data={'allowed':authorized}
        elif path=='/api/development-notes':data={'owners':deepcopy(owners)}
        elif path=='/api/development-notes/blocks' and method=='POST':
            data=dict(id=route.request.post_data_json['request_id'],owner_id='a',title='开发笔记',document={'type':'doc','content':[{'type':'paragraph'}]},files=[],attachment_ids=[],revision=0,saved_at=None)
            owners[0]['blocks'].append(deepcopy(data))
        elif path.endswith('/files') and method=='POST':
            raw=route.request.post_data_buffer
            assert b'multipart/form-data' not in raw[:50] and b'filename=' in raw
            kind='image/png' if b'image/png' in raw else 'application/octet-stream'
            uid=str(uuid4());name='截图.png' if kind=='image/png' else 'notes.txt'
            data=dict(id=uid,filename=name,size=len(png) if kind=='image/png' else 5,content_type=kind,src='/api/development-notes/files/'+uid)
            files[uid]=data
        elif '/api/development-notes/files/' in path:
            return route.fulfill(content_type=files[path.rsplit('/',1)[-1]]['content_type'],body=png)
        elif path.endswith('/history'):
            uid=path.split('/')[-2];rows=histories.get(uid,[]);data={'items':deepcopy(rows),'total':len(rows)}
        elif path.startswith('/api/development-notes/blocks/') and method=='PUT':
            uid=path.rsplit('/',1)[-1];payload=route.request.post_data_json;writes.append(payload)
            row=next(row for row in owners[0]['blocks'] if row['id']==uid)
            assert payload['revision']==row['revision']
            row.update({key:payload[key] for key in ['title','document','attachment_ids']})
            row.update(revision=row['revision']+1,saved_at='2026-11-27T11:22:33+08:00',files=[files[id] for id in payload['attachment_ids']])
            histories.setdefault(uid,[]).insert(0,dict(revision=row['revision'],saved_at=row['saved_at'],saved_by='赵震锋',title=row['title'],document=deepcopy(row['document']),attachment_ids=list(row['attachment_ids'])))
            data=deepcopy(row)
        elif path=='/api/editor-drafts':data={'payload':None,'revision':0}
        elif path=='/api/editor-drafts/batch':data=[{**entry,'revision':1} for entry in route.request.post_data_json['drafts']]
        route.fulfill(content_type='application/json',body=json.dumps(data,ensure_ascii=False))
    with sync_playwright() as pw:
        browser=pw.chromium.launch(channel='msedge',headless=True)
        context=browser.new_context(viewport={'width':1600,'height':1050},service_workers='block')
        context.add_init_script("localStorage.setItem('user_id','a');localStorage.setItem('user_name','williamzhao')")
        context.route(re.compile(r'^http://localhost:3000/api/'),api)
        context.route(BASE+'/development-notes-test',lambda r:r.fulfill(content_type='text/html',body=html))
        page=context.new_page();page.on('pageerror',lambda e:errors.append(str(e)));page.goto(BASE+'/development-notes-test')
        entry=page.get_by_role('button',name='开发笔记',exact=True);expect(entry).to_be_visible();entry.click()
        dialog=page.get_by_role('dialog',name='开发笔记',exact=True)
        expect(dialog).to_be_visible()
        mine=dialog.get_by_role('region',name='赵震锋的开发笔记')
        # section具有aria-label时映射为region。
        theirs=dialog.get_by_role('region',name='黄运坚的开发笔记')
        expect(theirs).to_contain_text('另一人的只读区域');expect(theirs.get_by_role('button',name='增加编辑框')).to_have_count(0)
        mine.get_by_role('button',name='增加编辑框').click()
        note=mine.locator('.development-note-editor').first
        note.get_by_label('开发笔记标题').fill('本次开发事项')
        editor=note.locator('.tiptap');editor.fill('截图一对应说明');editor.press('Control+a')
        for label in ['加粗','红字','黄色高亮','黑色下划线']:note.get_by_role('button',name=label,exact=True).click()
        editor.press('End');editor.press('Enter')
        note.locator('input[accept]').set_input_files({'name':'shot.png','mimeType':'image/png','buffer':png})
        expect(note.locator('.rich-text-image img')).to_have_count(1)
        expect(note.locator('.rich-text-image img')).to_have_attribute('src',re.compile('^blob:'))
        editor.press('Control+End');editor.press('Enter');editor.press('ArrowDown');editor.type('截图二对应说明')
        encoded=base64.b64encode(png).decode()
        editor.evaluate("(el,b64)=>{const dt=new DataTransfer();dt.items.add(new File([Uint8Array.from(atob(b64),c=>c.charCodeAt(0))],'paste.png',{type:'image/png'}));el.dispatchEvent(new ClipboardEvent('paste',{clipboardData:dt,bubbles:true,cancelable:true}))}",encoded)
        expect(note.locator('.rich-text-image img')).to_have_count(2)
        note.locator('input[type=file]:not([accept])').set_input_files({'name':'notes.txt','mimeType':'text/plain','buffer':b'hello'})
        expect(note.locator('.development-note-files')).to_contain_text('notes.txt')
        note.get_by_role('button',name='保存笔记',exact=True).click()
        expect(note).to_contain_text('第1版')
        document=json.dumps(writes[0]['document'],ensure_ascii=False)
        assert all(mark in document for mark in ['bold','textColor','underline','highlight']),document
        assert document.count('"type": "image"')==2 and len(writes[0]['attachment_ids'])==1
        note.get_by_role('button',name='保存笔记',exact=True).click();expect(note).to_contain_text('第2版')
        note.get_by_role('button',name='保存历史').click()
        history=page.get_by_role('dialog',name='开发笔记 · 保存历史',exact=True)
        expect(history).to_contain_text('第1版');expect(history).to_contain_text('第2版');expect(history).to_contain_text('2026')
        history.get_by_role('button',name='关闭',exact=True).click()
        mine.get_by_role('button',name='增加编辑框').click();expect(mine.locator('.development-note-editor')).to_have_count(2)
        last=mine.locator('.development-note-editor').last;last.locator('.tiptap').fill('关闭后应恢复的草稿')
        dialog.get_by_role('button',name='关闭',exact=True).click();expect(dialog).not_to_be_visible();entry.click()
        expect(dialog.get_by_role('region',name='赵震锋的开发笔记').locator('.development-note-editor').last.locator('.tiptap')).to_contain_text('关闭后应恢复的草稿')
        page.set_viewport_size({'width':390,'height':844})
        bounds=dialog.bounding_box();assert bounds['x']>=0 and bounds['x']+bounds['width']<=391
        assert not errors,errors
        authorized=False;page.reload();expect(page.get_by_role('button',name='开发笔记',exact=True)).to_have_count(0)
        browser.close()
    print('PASS: 双人专属入口、两人分区、多编辑框、富文本格式、双截图、文件上传、保存历史、草稿恢复、小屏与无权限隐藏')


if __name__=='__main__':run()

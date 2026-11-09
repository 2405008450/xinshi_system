"""真实管理弹窗：少于10条可打开、四级路径、Excel粘贴及统计保存，全部接口模拟。"""
import json,re
from urllib.parse import urlparse
from urllib.request import urlopen
from playwright.sync_api import sync_playwright,expect
BASE='http://localhost:3000'

def run():
    compiled=urlopen(BASE+'/src/views/project/ProjectWorkspace.vue',timeout=30).read().decode()
    dep=lambda name:re.search(r'from ["\']([^"\']*/'+name+r'\.js[^"\']*)',compiled).group(1)
    html='''<!doctype html><meta charset="UTF-8"><link rel="stylesheet" href="/node_modules/element-plus/dist/index.css"><link rel="stylesheet" href="/src/styles/common.css"><div id="app"></div><script type="module">
import {createApp,h} from VUE;import {createRouter,createWebHistory} from ROUTER;import Projects from '/src/views/project/translation/ProjectDetails.vue';import AppForm from '/src/components/common/AppForm.vue';import Dialog from '/src/components/common/DraggableFormDialog.vue';const app=createApp({render:()=>h(Projects)});app.component('AppForm',AppForm);app.component('DraggableFormDialog',Dialog);app.use(createRouter({history:createWebHistory(),routes:[{path:'/five-level-test',component:{render:()=>null}}]}));app.mount('#app');</script>'''.replace('from VUE','from '+json.dumps(dep('vue'))).replace('from ROUTER','from '+json.dumps(dep('vue-router')))
    number='TP-261107-971'
    rows=[]
    for i,(suffix,name,folder) in enumerate([('.001','一级资料',True),('.001.001','二级资料',True),('.001.001.001','三级资料',True),('.001.001.001.001','末级文件.xlsx',False),('.002','根文件.pdf',False)]):
        rows.append({'id':'s'+str(i),'parent_project_id':'p1','sub_order_no':number+suffix,'sub_project_name':name,'status':'pending_confirmation','folder_info':{'files':[]} if folder else None,'network_file_path':'D:\\客户项目\\'+('很长的共享资料路径\\'*18)+name,'word_count_matrix':{'company':{'words':None},'customer':{'words':None}},'word_count_matrix_source':'suborder_aggregate' if folder else 'suborder'})
    root={'id':'p1','order_no':number,'project_name':'客户项目','source_file_name':'客户项目','project_status':'confirmed','network_file_path':r'D:\客户项目','sub_orders':rows,'word_count_matrix':{'company':{'words':None}},'word_count_sub_order_count':2}
    patches=[]
    def api(route):
        path=urlparse(route.request.url).path
        if path=='/api/projects/translation/page':data={'items':[root],'total':1}
        elif path=='/api/projects/translation/p1':data=root
        elif path=='/api/sub-orders/project/p1':data=rows
        elif path.endswith('/folder-import-records'):data={'items':[{'id':'log1','actor_name':'测试人员','created_at':'2026-11-07T22:00:00+08:00','root_path':r'D:\客户项目','empty_folders':['客户项目/空目录'],'created_count':5,'empty_detection_complete':True}]}
        elif path.startswith('/api/word-count-matrices/suborder/') and route.request.method=='PATCH':
            ident=path.rsplit('/',1)[1];payload=route.request.post_data_json;patches.append((ident,payload))
            row=next(row for row in rows if row['id']==ident)
            for change in payload['changes']:row['word_count_matrix'].setdefault(change['dimension'],{})[change['metric_type']]=change['value']
            data={}
        elif path.endswith('/export'):route.fulfill(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',body=b'mocked-xlsx');return
        elif path.endswith('/editor-drafts'):data={'payload':None,'revision':0}
        elif path.endswith('/page'):data={'items':[],'total':0}
        else:data=[]
        route.fulfill(content_type='application/json',body=json.dumps(data,ensure_ascii=False))
    with sync_playwright() as p:
        browser=p.chromium.launch(channel='msedge');page=browser.new_page(viewport={'width':1280,'height':850})
        page.add_init_script("localStorage.setItem('user_id','qa');localStorage.setItem('user_roles','[\"admin\"]');localStorage.setItem('user_permissions','[\"projects:read\",\"projects:write\"]')")
        page.route(re.compile(r'^http://localhost:3000/api/'),api);page.route(BASE+'/five-level-test',lambda route:route.fulfill(content_type='text/html',body=html))
        errors=[];page.on('pageerror',lambda err:errors.append(str(err)));page.goto(BASE+'/five-level-test')
        page.get_by_role('button',name='展开子订单',exact=True).first.click()
        page.get_by_role('button',name='进入子订单管理页',exact=True).click()
        dialog=page.locator('.project-suborder-manager-dialog:visible');expect(dialog).to_be_visible()
        initial=dialog.bounding_box()
        header=dialog.locator('.el-dialog__header').first.bounding_box()
        page.mouse.move(header['x']+450,header['y']+16);page.mouse.down();page.mouse.move(header['x']+440,header['y']+36,steps=5);page.mouse.up()
        moved=dialog.bounding_box()
        assert abs(moved['y']-initial['y'])>5 and moved['x']>=0 and moved['y']>=0
        table=dialog.locator('.suborder-management-table')
        body=table.locator('.el-scrollbar__wrap')
        sizes=body.evaluate('(el)=>({height:el.clientHeight,scrollHeight:el.scrollHeight,width:el.clientWidth,scrollWidth:el.scrollWidth})')
        assert sizes['scrollHeight']>sizes['height'] and sizes['scrollWidth']>sizes['width'],sizes
        heading=table.locator('.el-table__header-wrapper')
        initial_heading=heading.bounding_box()
        body.evaluate('(el)=>{el.scrollTop=400;el.scrollLeft=120}')
        assert abs(heading.bounding_box()['y']-initial_heading['y'])<1
        horizontal=table.locator('.el-scrollbar__bar.is-horizontal')
        vertical=table.locator('.el-scrollbar__bar.is-vertical')
        expect(horizontal).to_be_visible();expect(vertical).to_be_visible()
        bottom=horizontal.bounding_box()['y']+horizontal.bounding_box()['height']
        card=dialog.locator('.suborder-management').bounding_box()
        assert abs(card['y']+card['height']-bottom)<5,(card,horizontal.bounding_box())
        assert bottom<=850 and heading.bounding_box()['y']>=0
        page.set_viewport_size({'width':1024,'height':700})
        expect(horizontal).to_be_visible();expect(vertical).to_be_visible()
        resized=dialog.bounding_box()
        assert horizontal.bounding_box()['y']+horizontal.bounding_box()['height']<=700
        page.set_viewport_size({'width':1280,'height':850})
        grid=dialog.locator('.suborder-statistics-grid')
        expect(grid.locator('thead th').first).to_have_text('序号')
        expect(grid.locator('thead th').nth(3)).to_have_text('相对路径')
        expect(grid.locator('tbody tr').nth(3).locator('td').nth(3)).to_have_text('客户项目'+chr(92)+('很长的共享资料路径'+chr(92))*18+'末级文件.xlsx')
        expect(grid.locator('tbody tr').nth(0).locator('td').first).to_have_text('1')
        expect(grid.locator('tbody tr').nth(4).locator('td').first).to_have_text('5')
        splitter=dialog.get_by_role('separator',name='调整统计填写区与子订单列表高度',exact=True)
        top=dialog.locator('.vertical-split-top');bottom_panel=dialog.locator('.vertical-split-bottom')
        before_top=top.bounding_box()['height'];before_bottom=bottom_panel.bounding_box()['height']
        handle=splitter.bounding_box();x=handle['x']+handle['width']/2;y=handle['y']+handle['height']/2
        page.mouse.move(x,y);page.mouse.down();page.mouse.move(x,y+60,steps=8);page.mouse.up()
        assert top.bounding_box()['height']>before_top+40
        assert bottom_panel.bounding_box()['height']<before_bottom-40
        splitter.focus();splitter.press('ArrowUp')
        grid.locator('input[data-row="3"][data-col="0"]').fill('50')
        top_toggle=dialog.get_by_title('折叠统计填写区',exact=True)
        top_toggle.click();expect(grid).not_to_be_visible();expect(dialog.locator('.suborder-list-region')).to_be_visible()
        dialog.get_by_title('展开统计填写区',exact=True).click();expect(grid).to_be_visible()
        expect(grid.locator('input[data-row="3"][data-col="0"]')).to_have_value('50')
        dialog.get_by_title('折叠子订单列表',exact=True).click()
        expect(dialog.locator('.suborder-list-region')).not_to_be_visible();expect(grid).to_be_visible()
        dialog.get_by_title('展开子订单列表',exact=True).click()
        expect(dialog.locator('.suborder-list-region')).to_be_visible()

        expect(grid.locator('input[data-row="0"][data-col="0"]')).to_have_attribute('readonly','')
        cell=grid.locator('input[data-row="3"][data-col="0"]')
        cell.focus()
        cell.press('ArrowRight')
        expect(grid.locator('input[data-row="3"][data-col="1"]')).to_be_focused()
        page.keyboard.press('ArrowDown')
        expect(grid.locator('input[data-row="4"][data-col="1"]')).to_be_focused()
        page.keyboard.press('ArrowLeft')
        expect(grid.locator('input[data-row="4"][data-col="0"]')).to_be_focused()
        page.keyboard.press('ArrowUp')
        expect(cell).to_be_focused()
        cell.press('ArrowLeft')
        expect(cell).to_be_focused()

        cell.evaluate("el=>{const data=new DataTransfer();data.setData('text/plain','100\\t90\\t80\\t70\\n200\\t190\\t180\\t170');el.dispatchEvent(new ClipboardEvent('paste',{clipboardData:data,bubbles:true,cancelable:true}))}")
        expect(cell).to_have_value('100');expect(grid.locator('input[data-row="4"][data-col="1"]')).to_have_value('190')
        cell.press('Enter');expect(grid.locator('input[data-row="4"][data-col="0"]')).to_be_focused()
        grid.get_by_role('button',name='保存统计（2 单）',exact=True).click()
        expect(grid.get_by_role('button',name='保存统计（0 单）',exact=True)).to_be_disabled()
        assert len(patches)==2,patches
        assert next(change['value'] for change in patches[0][1]['changes'] if change['dimension']=='customer' and change['metric_type']=='words')==90
        expect(dialog).to_contain_text(r'D:\客户项目')
        dialog.get_by_role('button',name='目录导入记录',exact=True).click()
        expect(page.locator('.folder-import-records:visible')).to_contain_text(r'D:\客户项目\空目录')
        expect(page.locator('.folder-import-records:visible')).to_contain_text('测试人员')
        dialog.get_by_role('button',name='目录导入记录',exact=True).click()
        with page.expect_download() as download:dialog.get_by_role('button',name='导出层级Excel',exact=True).click()
        assert download.value.suggested_filename.endswith('.xlsx')
        dialog.get_by_role('button',name='关闭窗口',exact=True).first.click();expect(dialog).not_to_be_visible()
        page.get_by_role('button',name='进入子订单管理页',exact=True).click();expect(dialog).to_be_visible()

        dialog.locator('.suborder-management-table').get_by_role('button',name='编辑',exact=True).first.click()
        editor=page.locator('.suborder-editor-dialog:visible')
        progress=editor.locator('.suborder-progress-collapse')
        expect(progress.locator('.el-collapse-item__wrap')).not_to_be_visible()
        progress.get_by_role('button',name='进度跟踪',exact=True).click()
        expect(progress.locator('.el-collapse-item__wrap')).to_be_visible()
        progress.locator('input').first.fill('30')
        expect(editor.locator('.el-form-item').filter(has_text='网络文件路径').locator('input')).to_be_visible()
        editor.get_by_role('button',name='取消',exact=True).click()
        expect(editor).not_to_be_visible()
        dialog.locator('.suborder-management-table').get_by_role('button',name='编辑',exact=True).first.click()
        editor=page.locator('.suborder-editor-dialog:visible')
        expect(editor.locator('.suborder-progress-collapse .el-collapse-item__wrap')).not_to_be_visible()
        editor.get_by_role('button',name='取消',exact=True).click()

        assert not errors,errors;browser.close()
    print('sequence numbers / splitter drag and keyboard / independently collapse and restore / pending input retained / fixed header / independent vertical scroll / always-on bottom horizontal bar / zero bottom gap / responsive resize / fourth-level paths / readonly aggregates / TSV paste / enter navigation / saved changes / export / reopen PASS')
if __name__=='__main__':run()

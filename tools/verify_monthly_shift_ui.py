"""月度排班拖入、调班、拖回与工作台只读；所有接口隔离。"""
import json,re,sys
from pathlib import Path
from urllib.request import urlopen
from urllib.parse import urlparse,parse_qs
from datetime import datetime,timezone,timedelta
from playwright.sync_api import sync_playwright,expect
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from monthly_shift import SHIFTS,DEPARTMENTS
BASE='http://localhost:3000'

def run():
    compiled=urlopen(BASE+'/src/components/common/AppForm.vue').read().decode()
    vue=re.search(r'from ["\']([^"\']*/vue\.js[^"\']*)',compiled).group(1)
    html=f'''<!doctype html><meta charset="UTF-8"><link rel="stylesheet" href="/node_modules/element-plus/dist/index.css"><link rel="stylesheet" href="/src/styles/common.css"><div id="app"></div><script type="module">
    import {{createApp,h,ref}} from {json.dumps(vue)};import Management from '/src/views/hr/MonthlyShiftManagement.vue';import Mine from '/src/views/schedule/components/MyMonthlyShift.vue';import AppForm from '/src/components/common/AppForm.vue';
    const app=createApp({{setup(){{const mine=ref(false);return()=>h('div',[h('button',{{onClick:()=>mine.value=!mine.value}},'切换个人排班'),mine.value?h(Mine):h(Management)])}}}});app.component('AppForm',AppForm);app.mount('#app');</script>'''
    people=[{'id':'sales-person','name':'测试销售','username':'sales','active':True,'departments':[{'id':'customer','name':'客户/销售部'}]},
            {'id':'it-person','name':'测试技术','username':'it','active':True,'departments':[{'id':'it','name':'IT部门'}]}]
    plans={};calls=[];errors=[]
    def plan(month):return plans.setdefault(month,{'ready':True,'month':month,'revision':0,'assignments':[],'shifts':SHIFTS,'departments':DEPARTMENTS})
    def api(route):
        request=route.request;path=urlparse(request.url).path;query=parse_qs(urlparse(request.url).query);month=query.get('month',['2026-11'])[0]
        calls.append((request.method,path,month))
        if path=='/api/monthly-shifts/directory':result={'ready':True,'items':[{'id':row['code'],'name':row['label']} for row in DEPARTMENTS],'people':people}
        elif path=='/api/monthly-shifts' and request.method=='PUT':
            result=plan(month);payload=request.post_data_json
            result['revision']+=1;result['assignments']=[{**row,'name':next(person['name'] for person in people if person['id']==row['user_id']),'active':True} for row in payload['assignments']]
        elif path=='/api/monthly-shifts':result=plan(month)
        elif path=='/api/monthly-shifts/mine':result={'ready':True,'month':month,'assignment':{'user_id':'sales-person','name':'测试销售','department':'customer','shift':'customer_remote'},'shifts':SHIFTS,'departments':DEPARTMENTS}
        else:result=[]
        route.fulfill(content_type='application/json',body=json.dumps(result,ensure_ascii=False))
    with sync_playwright() as pw:
        browser=pw.chromium.launch(channel='msedge',headless=True)
        context=browser.new_context(viewport={'width':1800,'height':1050},service_workers='block',timezone_id='America/Los_Angeles')
        context.route(re.compile(r'^http://localhost:3000/api/'),api)
        context.route(BASE+'/monthly-shift-test',lambda route:route.fulfill(content_type='text/html',body=html))
        page=context.new_page();page.clock.set_fixed_time(datetime(2026,10,25,16,tzinfo=timezone(timedelta(hours=8))))
        page.on('pageerror',lambda error:errors.append(str(error)));page.goto(BASE+'/monthly-shift-test')
        expect(page.get_by_role('heading',name='2026年11月班次安排')).to_be_visible()
        expect(page.locator('.monthly-matrix tbody tr')).to_have_count(5)
        page.get_by_role('button',name='本月安排',exact=True).click();expect(page.get_by_role('heading',name='2026年10月班次安排')).to_be_visible()
        page.get_by_role('button',name='上月安排',exact=True).click();expect(page.get_by_role('heading',name='2026年9月班次安排')).to_be_visible()
        page.get_by_role('button',name='下月安排',exact=True).click();expect(page.get_by_role('heading',name='2026年11月班次安排')).to_be_visible()
        page.get_by_role('button',name='晚班（客户部居家）',exact=True).click()
        expect(page.locator('.el-popover:visible')).to_contain_text('21:00–23:00')
        page.get_by_role('heading',name='2026年11月班次安排').click()
        person=page.locator('.person').filter(has_text='测试销售')
        expect(person).to_be_visible()
        def drag(source,target):
            transfer=page.evaluate_handle('new DataTransfer()')
            source.dispatch_event('dragstart',{'dataTransfer':transfer})
            target.dispatch_event('drop',{'dataTransfer':transfer})
            page.wait_for_timeout(150)
        early=page.locator('[data-cell="customer:early"]');late=page.locator('[data-cell="customer:late"]')
        drag(person,early);expect(early.locator('.monthly-person')).to_contain_text('测试销售')
        expect(person).to_have_class(re.compile('is-assigned'));expect(person).to_have_attribute('draggable','false')
        assert len(plan('2026-11')['assignments'])==1
        drag(early.locator('.monthly-person'),late)
        expect(early.locator('.monthly-person')).to_have_count(0);expect(late.locator('.monthly-person')).to_have_count(1)
        drag(late.locator('.monthly-person'),page.locator('.monthly-roster-return'))
        expect(late.locator('.monthly-person')).to_have_count(0);expect(person).to_have_attribute('draggable','true')
        tech=page.locator('.person').filter(has_text='测试技术');it_cell=page.locator('[data-cell="it:early_early"]')
        drag(tech,it_cell);expect(it_cell).to_contain_text('测试技术')
        page.screenshot(path='scratch/monthly-shift-ui.png',full_page=True)
        page.get_by_role('button',name='切换个人排班',exact=True).click()
        expect(page.locator('.my-monthly-shift')).to_contain_text('晚班（客户部居家）')
        expect(page.locator('.my-monthly-shift')).to_contain_text('21:00–23:00')
        expect(page.locator('.my-monthly-shift [draggable="true"]')).to_have_count(0)
        assert not page.locator('.my-monthly-shift button').filter(has_text=re.compile('保存|编辑|安排人员')).count()
        page.get_by_role('button',name='下月',exact=True).click()
        assert any(method=='GET' and path.endswith('/mine') and month=='2026-11' for method,path,month in calls)
        assert not errors,errors
        print(json.dumps({'passed':True,'next_month_default':True,'five_departments':True,'drag_move_return':True,'assigned_person_disabled':True,'workbench_readonly':True,'page_errors':errors}))
        browser.close()
if __name__=='__main__':run()

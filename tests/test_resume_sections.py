"""章节归类回归使用合成简历；不固定真实姓名或文件行号。"""
from tools.resume_sections import extract_sections
from tools.resume_alignment import reconcile_lines,certificate_language

def lines(*values):return [{'id':i+1,'text':s,'location':f'第{i+1}行'} for i,s in enumerate(values)]

def test_section_boundaries_and_campus_events_are_stable():
    source=lines('自我评价','沟通能力强。','教育经历','本科 学校','校内职务','2020-9 至 2021-6','学生会干事','2021-9 至 2022-6','班长','校内奖励','2022-5','奖学金','工作经历','公司任职')
    a=extract_sections(source,'source-hash');b=extract_sections(source,'source-hash')
    assert a==b
    assert a['fields']['self_assessment']=='沟通能力强。'
    assert len(a['fields']['campus_positions'])==2
    assert '公司任职' not in str(a['fields'])
    assert a['evidence']['campus_positions.1']['line_ids']==[8,9]

def test_english_sections_and_oversize_keep_source():
    value=extract_sections(lines('1- About Me','Personal statement','2- Education','School','5- Areas of Expertise','Law - Health','6- Software','Office','7- Contact Details','Email: synthetic@example.test'),'hash')
    assert value['fields']['self_assessment']=='Personal statement'
    assert value['fields']['professional_domains']==['Law','Health']
    assert value['fields']['other_skills']=='Office'
    large=extract_sections(lines('自我评价','字'*20001),'hash')
    assert 'self_assessment' not in large['fields'] and large['review_flags']

def test_mixed_contact_line_does_not_damage_identity_or_unlabelled_values():
    source=lines('证件编号：123456789012345678','手机：12345678901 | 证件编号：123456789012345679')
    text,_=reconcile_lines(source,[('primary_phone','12345678901')])
    assert '123456789012345678' in text and '123456789012345679' in text
    assert '手机：12345678901' not in text

def test_certificate_name_takes_precedence_over_other_certificates_in_quote():
    catalog={'英语':'EN','普通话':'ZH','日语':'JA'}
    assert certificate_language('大学英语四级','英语四级；普通话二甲',catalog)=='EN'
    assert certificate_language('语言证书','英语四级；普通话二甲',catalog) is None

def test_unrecognised_heading_is_not_guessed_from_person_name():
    value=extract_sections(lines('某甲','一些无标题内容'),'hash')
    assert value['fields']=={}

def test_inline_table_field_does_not_swallow_following_education():
    value=extract_sections(lines('擅长领域：商务、合同','本科院校：某学校','兴趣爱好：音乐','姓名：某乙'),'hash')
    assert value['fields']['professional_domains']==['商务、合同']
    assert value['fields']['interests']=='音乐'
    assert value['evidence']['interests']['quote']=='兴趣爱好：音乐'

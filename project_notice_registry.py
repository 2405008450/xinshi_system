"""须知共用行为，各业务独立选择栏目与附件表。"""
PROJECT_NOTICE_MODULES = {'translation','interpretation','recruitment'}
SUPPORTED_NOTICE_MODULES = PROJECT_NOTICE_MODULES | {'development'}


def notice_models(module):
    if module == 'development':
        from development_notice_models import DevelopmentNoticeSection, DevelopmentNoticeAttachment
        return DevelopmentNoticeSection, DevelopmentNoticeAttachment
    if module in PROJECT_NOTICE_MODULES:
        from project_notice_models import ProjectNoticeSection, ProjectNoticeAttachment
        return ProjectNoticeSection, ProjectNoticeAttachment
    from fastapi import HTTPException
    raise HTTPException(404,'须知板块不存在')

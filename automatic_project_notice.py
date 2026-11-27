"""自动登记通知标识，邮件与会话复用正文时不重复追加。"""
MARKER='【登记时自动发送】'


def mark_automatic(content):
    return content if MARKER in content else content+'\n\n'+MARKER

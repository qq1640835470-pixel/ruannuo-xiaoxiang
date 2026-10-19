"""Fixed safe diagnostics; never expose provider bodies or learning content."""
import sqlite3
import urllib.error

MESSAGES={
 'selection_changed':('学习模型选择已变化','请重新预览并明确确认，未自动换模。'),
 'model_request':('模型请求失败，未生成计划或测验','检查连接后，由你决定是否发起新请求。'),
 'auth_quota':('认证、权限或额度不足','在本机核对账号、DPAPI Key和额度，不要把Key贴到聊天。'),
 'parameters':('模型参数或上下文不兼容','核对目录能力与输出预算；不会自动改模型或重试。'),
 'empty_truncated':('模型输出为空、被过滤或截断','核对模型输出限制；推理内容不会被当作题目正文。'),
 'invalid_json':('模型返回无效JSON','未修补缺失内容；可调整范围后主动发起新请求。'),
 'question_schema':('题目结构不合法','题数、选项、答案及解释必须完整；未保存有效测验。'),
 'scope_evidence':('题目范围依据不符','请给出具体知识点；引用必须能够锚定所选范围。'),
 'scope_unclear':('知识点范围不够具体','请补充到具体概念，例如零状态响应、一阶RC电路或电容充放电。'),
 'database':('数据库保存失败','先刷新历史核对；不会再次调用模型。'),
 'pending':('请求正在处理或待核对','核对同一请求或查看历史，不会重复调用模型。'),
}

class LearningError(ValueError):
    def __init__(self,category,*,usage=None,reason=None):
        self.category=category if category in MESSAGES else 'model_request'
        title,advice=MESSAGES[self.category]
        if self.category=='auth_quota' and reason=='budget':title,advice='本机预算剩余不足','请核对本机预算与待核用量；没有调用模型。'
        super().__init__(title+'：'+advice)
        self.usage=usage


def category(exc):
    if isinstance(exc,LearningError):return exc.category
    if isinstance(exc,sqlite3.Error):return 'database'
    code=getattr(exc,'code',None)
    if code in (401,402,403,429):return 'auth_quota'
    if code in (400,404,422):return 'parameters'
    return 'model_request'

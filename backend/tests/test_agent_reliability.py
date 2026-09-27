from uuid import uuid4

from app.agent import ToolGateway, run_agent


def test_safety_red_flag_never_calls_model(app):
    class ExplodingPlanner:
        def complete(self, messages, tools):
            raise AssertionError('planner must not be called for urgent symptoms')

    gateway = ToolGateway(app.state.sessions, 'unused', str(uuid4()), '训练时出现胸痛和呼吸困难', 'chat')
    result = run_agent(ExplodingPlanner(), gateway, [])
    assert result['status'] == 'safety_redirect'
    assert result['evidence_mode'] == 'urgent_referral'
    assert not result['receipts']


def test_normal_reply_marks_evidence_policy(app):
    class Planner:
        def complete(self, messages, tools):
            assert messages[0]['content'].lstrip().startswith('You are FitMind')
            return {'role': 'assistant', 'content': '可以先从轻松散步开始。'}

    gateway = ToolGateway(app.state.sessions, 'unused', str(uuid4()), '今天想轻松活动', 'chat')
    result = run_agent(Planner(), gateway, [])
    assert result['status'] == 'completed'
    assert result['evidence_mode'] == 'reviewed_source_required_for_health_claims'

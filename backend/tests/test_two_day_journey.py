from uuid import uuid4

from fastapi.testclient import TestClient


def _submit(client, auth, operations):
    operation_id = str(uuid4())
    response = client.post('/api/v1/agent-actions/apply', headers={**auth, 'Idempotency-Key': operation_id}, json={
        'operation_id': operation_id, 'operations': operations,
    })
    assert response.status_code == 200, response.text
    return response.json()['data']


def test_two_day_real_user_journey(client, app):
    # Day 1: sign in, talk to the coach, and save an honest activity report.
    session = client.post('/api/v1/auth/dev-session').json()['data']
    auth = {'Authorization': 'Bearer ' + session['access_token']}
    conversation = client.post('/api/v1/conversations', headers=auth).json()['data']['id']
    operation_id = str(uuid4())
    day_one = client.post(
        f'/api/v1/conversations/{conversation}/messages',
        headers={**auth, 'Idempotency-Key': operation_id},
        json={'operation_id': operation_id, 'text': '今天散步二十分钟，腿有点酸。', 'intent': 'chat'},
    )
    assert day_one.status_code == 200
    activity = _submit(client, auth, [{'action': 'create', 'kind': 'activity', 'payload': {
        'text': '今天散步二十分钟，腿有点酸。', 'activity_status': 'reported',
    }}])['objects'][0]

    # Day 2: the same user returns after a miniapp restart; the persisted
    # access token still represents the same account. Logout is tested by the
    # dedicated auth regression test because it intentionally ends the session.
    objects = client.get('/api/v1/objects', headers=auth).json()['data']['items']
    assert any(item['id'] == activity['id'] for item in objects)
    conversation_two = client.post('/api/v1/conversations', headers=auth).json()['data']['id']
    operation_id = str(uuid4())
    response = client.post(
        f'/api/v1/conversations/{conversation_two}/messages',
        headers={**auth, 'Idempotency-Key': operation_id},
        json={'operation_id': operation_id, 'text': '请根据昨天的情况整理一个轻松计划。', 'intent': 'task'},
    )
    assert response.status_code == 200
    plan = _submit(client, auth, [{'action': 'create', 'kind': 'plan', 'payload': {
        'title': '轻松恢复计划', 'text': '今天做舒缓拉伸\n明天散步二十分钟',
        'nodes': [{'id': 'stretch', 'text': '今天做舒缓拉伸', 'status': 'unstarted'},
                  {'id': 'walk', 'text': '明天散步二十分钟', 'status': 'unstarted'}],
    }}])['objects'][0]
    updated = _submit(client, auth, [{'action': 'replace', 'object_id': activity['id'],
                                      'expected_version': activity['version'],
                                      'payload': {**activity['payload'], 'recovery_note': '今晚早点休息'}}])
    assert updated['objects'][0]['version'] == 2
    exported = client.get('/api/v1/me/export', headers=auth).json()['data']
    assert {item['id'] for item in exported['objects']} == {activity['id'], plan['id']}
    assert client.delete('/api/v1/auth/session', headers=auth).status_code == 200

"""Isolated browser verification server. Model responses are controlled fixtures.

Launched only by check-master-ui.mjs; never imported by the application.
No credentials or external network calls are used.
"""
import os
from pathlib import Path

if __name__ == '__main__':
    assert os.environ.get('NEXQORI_MASTER_UI_CHECK') == '1'
    assert 'verification' in Path(os.environ['NEXQORI_LAB_DATA']).parts
    import uvicorn
    from intent_lab import api, workflow_editor as editor, providers
    from intent_lab.flow_engine import REQUIREMENTS, validate_observations

    def no_network(*args, **kwargs):
        raise AssertionError('External provider calls are forbidden in browser verification')
    providers.httpx.Client = no_network

    def fixture(messages):
        content=messages[0]['content']
        return 'incorrect-charge' if '[incorrect]' in content else 'payment-status' if '[payment]' in content else 'app-support' if '[app]' in content else 'service-feedback' if '[human]' in content else 'request-status' if '[query]' in content else 'unrecognized-charge'

    def triage(messages, language, instructions):
        return {'status':'ok','family':'query' if fixture(messages)=='request-status' else 'problem'}, {'source':'controlled_ui_verification'}

    def classify(messages, language, instructions, **kwargs):
        return {'status':'ok','intent':fixture(messages)}, {'source':'controlled_ui_verification'}

    def extract(messages, language, fields, instructions, notes, intent, incident):
        user_indices=[i for i,m in enumerate(messages) if m['role']=='user']
        complete=intent not in ('unrecognized-charge','incorrect-charge','payment-status') or len(user_indices)>1
        index=user_indices[-1]
        value={'assessment':'human_review' if intent=='service-feedback' else 'continue',
               'observations':[{'field':f,'message_index':index,'quote':messages[index]['content']} for f in fields] if complete else []}
        return validate_observations(value, REQUIREMENTS[intent], messages)

    editor.classify_triage=triage
    editor.classify_jev=classify
    editor.extract=extract
    uvicorn.run(api.app, host='127.0.0.1', port=5191, access_log=False, log_level='warning')

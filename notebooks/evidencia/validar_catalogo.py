"""Valida artefactos declarativos locales; no ejecuta acciones ni modelos."""
from pathlib import Path
import ast
import json
from jsonschema import Draft202012Validator

BASE = Path(__file__).resolve().parent
ROOT = BASE.parents[1]

def read(path):
    return json.loads(path.read_text(encoding='utf-8'))

def main():
    catalog = read(BASE / 'reglas_resolucion.json')
    schema = read(BASE / 'reglas_resolucion.schema.json')
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(catalog)
    taxonomy = read(ROOT / 'backend/config/intent-taxonomy.json')
    ids = [r['intent'] for r in catalog['rules']]
    assert len(ids) == len(set(ids))
    assert set(ids) == {r['id'] for r in taxonomy['intents']}
    assert catalog['taxonomy_version'] == taxonomy['version']
    tree = ast.parse((ROOT / 'backend/navigation.py').read_text(encoding='utf-8'))
    routes = ast.literal_eval(next(x.value for x in tree.body if isinstance(x, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == 'ROUTES' for t in x.targets)))
    assert routes == catalog['navigation_routes']
    for value in catalog['messages'].values():
        assert set(value) == {'es', 'en', 'pt'}
    actions = {}
    for rule in catalog['rules']:
        for action in rule['actions']:
            key = (rule['intent'], action['id'])
            assert key not in actions
            actions[key] = action
            assert set(action['requires_all']) <= set(catalog['facts'])
            assert len(action['requires_all']) == len(set(action['requires_all']))
            assert action['capability'] in catalog['capabilities']
            assert action['navigation_destination'] is None or action['navigation_destination'] in routes
            assert action['auto_execute'] is False
    for intent in ['unknown', 'restricted']:
        rule = next(r for r in catalog['rules'] if r['intent'] == intent)
        assert len(rule['actions']) == 1
        assert rule['actions'][0]['navigation_destination'] is None
        assert catalog['capabilities'][rule['actions'][0]['capability']]['effect'] == 'message_only'
    cases = read(BASE / 'casos_validacion.json')['cases']
    for case in cases:
        action = actions[(case['intent'], case['action_id'])]
        valid, missing, conflicts = (set(case[k]) for k in ['valid_facts','missing_facts','conflicting_facts'])
        assert not (valid & missing or valid & conflicts or missing & conflicts)
        assert valid | missing | conflicts == set(action['requires_all'])
        if case['intent'] == 'unknown': decision = 'request_new_requirement'
        elif case['intent'] == 'restricted': decision = 'deny'
        elif 'session' in missing: decision = 'insufficient'
        elif catalog['capabilities'][action['capability']]['status'] not in ['existing','existing_demo']: decision = 'blocked'
        elif conflicts: decision = 'conflict'
        elif missing: decision = 'insufficient'
        else: decision = 'sufficient'
        assert decision == case['expected_outcome'], case['id']
        assert case['execution_authorized'] is False
    labels = {'automatico','supervisado','insatisfecho','humano','desconocido'}
    assert set(catalog['classification_contract']['labels']) == labels
    for action in actions.values():
        assert action['sufficient_class'] in labels
        assert set(action['business_requires_all']) <= set(catalog['facts'])
    five_cases = read(BASE / 'casos_clasificacion_cinco_tipos.json')['cases']
    for case in five_cases:
        action = actions[(case['intent'], case['action_id'])]
        valid = set(case['valid_business_facts'])
        if case['intent'] == 'unknown': evidence_class = 'desconocido'
        elif not set(action['business_requires_all']) <= valid: evidence_class = 'insatisfecho'
        elif case['permission_state'] == 'denied': evidence_class = 'humano'
        else: evidence_class = action['sufficient_class']
        assert evidence_class == case['expected_evidence_class'], case['id']
        assert case['execution_authorized'] is False
    assert {c['expected_evidence_class'] for c in five_cases} == labels
    print(f'OK: {len(ids)} intenciones, {len(actions)} acciones, {len(cases)} casos técnicos y {len(five_cases)} casos de cinco tipos; sin modelos ni operaciones.')

if __name__ == '__main__':
    main()

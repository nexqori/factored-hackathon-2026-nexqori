from datetime import date, timedelta
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, func
from backend.tests.test_api import setup, login, ORIGIN
from backend.models import User, CustomerProfile, Product, AuditEvent
from backend.db import make_sessions
from backend.customer_profile import age_on, today
from backend.security import verify


def payload(**overrides):
    return {"name":"Verificación Cliente", "email":f"verification-{uuid4().hex}@example.com", "identityNumber":uuid4().hex[:20],
            "password":"Verification-only-passphrase!", "birthDate":"1960-03-20", "locale":"es", "textSize":"medium",
            "bankingExperience":"frequent", "digitalExperience":"confident", "assistance":"auto", "confirmed":True, **overrides}


def client_for(app):
    return TestClient(app, headers={"Origin":ORIGIN})


def test_register_creates_customer_profile_session_and_no_financial_product(setup):
    app,engine=setup; client=client_for(app); data=payload(email="  NEW-PROFILE@example.com  ",identityNumber="abc-123 456")
    response=client.post('/api/auth/register',json=data)
    assert response.status_code==201, response.text
    user=response.json()['user']; uid=user['id']
    assert user['email']=='new-profile@example.com' and user['role']=='customer'
    assert user['experience']['ageBand']=='60_plus'
    assert user['experience']['effectiveAssistance']=='standard'  # Age does not prescribe help.
    assert 'birthDate' not in user and 'password' not in response.text and 'HttpOnly' in response.headers['set-cookie']
    assert client.get('/api/session').status_code==200
    assert client.get('/api/admin/overview').status_code==403
    assert client.get('/api/bootstrap').json()['products']==[]
    with make_sessions(engine)() as db:
        row=db.get(User,uid); assert row.identity_number=='ABC123456' and verify(data['password'],row.password_hash)
        assert db.get(CustomerProfile,uid).birth_date==date(1960,3,20)
        assert db.scalar(select(func.count()).select_from(Product).where(Product.user_id==uid))==0
        assert db.scalar(select(AuditEvent.action).where(AuditEvent.user_id==uid))=='registered'
    client.headers['X-CSRF-Token']=response.json()['csrfToken']; client.post('/api/auth/logout',json={})
    assert client.post('/api/auth/login',json={'identifier':'abc-123 456','password':data['password']}).status_code==200


@pytest.mark.parametrize('override',[
    {'role':'admin'}, {'confirmed':False}, {'password':'short'}, {'email':'bad-email'}, {'identityNumber':'$$0000'},
    {'birthDate':'2026-02-30'}, {'birthDate':'2030-01-01'}, {'birthDate':'1890-01-01'}, {'assistance':'force'},
    {'name':'  '}, {'ageBand':'60_plus'},
])
def test_invalid_registration_is_atomic(setup,override):
    app,engine=setup
    response=client_for(app).post('/api/auth/register',json=payload(**override))
    assert response.status_code==422
    with make_sessions(engine)() as db:
        assert db.scalar(select(func.count()).select_from(User))==3
        assert db.scalar(select(func.count()).select_from(CustomerProfile))==0


def test_adult_birthday_boundary_and_age_bands(setup):
    app,_=setup; client=client_for(app); current=today(); eighteenth=date(current.year-18,current.month,current.day)
    assert age_on(eighteenth,current)==18
    assert client.post('/api/auth/register',json=payload(birthDate=(eighteenth+timedelta(days=1)).isoformat())).json()['error']=='adult_required'
    for years,band in [(18,'18_49'),(49,'18_49'),(50,'50_59'),(59,'50_59'),(60,'60_plus')]:
        response=client.post('/api/auth/register',json=payload(birthDate=date(current.year-years,current.month,current.day).isoformat(),digitalExperience='new'))
        assert response.status_code==201
        assert response.json()['user']['experience']['ageBand']==band
        assert response.json()['user']['experience']['effectiveAssistance']=='guided'


def test_duplicates_origin_and_explicit_help_override(setup):
    app,_=setup; client=client_for(app); data=payload(digitalExperience='new',assistance='standard')
    assert TestClient(app).post('/api/auth/register',json=data).status_code==403
    response=client.post('/api/auth/register',json=data); assert response.status_code==201
    assert response.json()['user']['experience']['effectiveAssistance']=='standard'
    for duplicate in [payload(email=data['email'].upper()),payload(identityNumber=data['identityNumber'])]:
        response=client.post('/api/auth/register',json=duplicate)
        assert response.status_code==409 and response.json()=={'error':'registration_unavailable'}


def test_profile_is_private_and_editable_without_changing_permissions(setup):
    app,_=setup; client,response=login(app)
    assert client.get('/api/profile/experience').json()=={'birthDate':'','experience':None}
    form={k:v for k,v in payload().items() if k in ['birthDate','bankingExperience','digitalExperience','assistance']}
    assert client.patch('/api/profile/experience',json=form,headers={'X-CSRF-Token':'bad'}).status_code==403
    updated=client.patch('/api/profile/experience',json={**form,'assistance':'guided'})
    assert updated.status_code==200 and updated.json()['user']['experience']['effectiveAssistance']=='guided'
    assert client.get('/api/session').json()['user']['experience']['effectiveAssistance']=='guided'
    other,_=login(app,'mateo'); assert other.get('/api/profile/experience').json()['birthDate']==''
    admin,_=login(app,'nora'); assert admin.get('/api/profile/experience').status_code==403
    assert other.patch('/api/profile/experience',json={**form,'userId':'andrea'}).status_code==422

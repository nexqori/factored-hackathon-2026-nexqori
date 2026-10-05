from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text, inspect
import pytest


def test_upgrade_preserves_old_messages_passwords_and_custom_accounts(tmp_path, monkeypatch):
    url='sqlite:///'+str(tmp_path/'migration.sqlite')
    monkeypatch.setenv('DATABASE_URL', url)
    config=Config('alembic.ini')
    command.upgrade(config, 'a649a6f7e838')
    engine=create_engine(url)
    with engine.begin() as db:
        for uid, email in [('andrea','andrea@nexqori.local'),('custom','own@gmail.com')]:
            db.execute(text("INSERT INTO users(id,email,name,password_hash,role,locale,created_at) VALUES(:id,:email,'Customer','unchanged-hash','customer','es','2026-09-28 12:00:00')"), {'id':uid,'email':email})
            db.execute(text("INSERT INTO messages(id,user_id,role,content,locale,created_at) VALUES(:id,:uid,'user','Original unchanged message','es','2026-09-28 12:00:00')"), {'id':'message-'+uid,'uid':uid})
        db.execute(text("INSERT INTO requests(id,user_id,request_key,service,reason,details,status,created_at,updated_at) VALUES('old-case','andrea','previous-request-key','general','other','Original case details','received','2026-09-28 12:00:00','2026-09-28 12:00:00')"))
    command.upgrade(config, 'head')
    with engine.connect() as db:
        assert len(inspect(db).get_check_constraints('users')) == 3
        assert len(inspect(db).get_check_constraints('messages')) == 2
        assert len(inspect(db).get_check_constraints('requests')) == 3
        assert len(inspect(db).get_check_constraints('card_profiles')) == 3
        assert len(inspect(db).get_check_constraints('chat_feedback')) == 5
        assert len(inspect(db).get_foreign_keys('attention_reviews')) == 4
        assert any(f['name']=='fk_conversation_transaction_owner' for f in inspect(db).get_foreign_keys('conversations'))
        assert any(f['name']=='fk_audit_transaction_owner' for f in inspect(db).get_foreign_keys('audit_events'))
        assert db.execute(text('SELECT count(*) FROM conversations WHERE transaction_id IS NOT NULL')).scalar()==0
        assert db.execute(text("SELECT details,catalog_service_id,source_product_id,service_data FROM requests WHERE id='old-case'")).one()==('Original case details',None,None,None)
        rows=db.execute(text('SELECT m.id,m.user_id,m.content,c.user_id FROM messages m JOIN conversations c ON c.id=m.conversation_id')).all()
        assert len(rows)==2 and all(row[1]==row[3] and row[2]=='Original unchanged message' for row in rows)
        assert db.execute(text("SELECT email,identity_number,password_hash,text_size FROM users WHERE id='andrea'")).one()==('andrea@nexqori.com','00000001','unchanged-hash','medium')
        assert db.execute(text("SELECT email,identity_number FROM users WHERE id='custom'")).one()==('own@gmail.com',None)
    engine.dispose()


@pytest.mark.parametrize('revision', ['f5a306c829d1', 'b37d1f4c9a20'])
def test_merge_upgrades_both_contributors_without_losing_feedback(tmp_path, monkeypatch, revision):
    url = 'sqlite:///' + str(tmp_path / 'contributors.sqlite')
    monkeypatch.setenv('DATABASE_URL', url)
    config = Config('alembic.ini')
    command.upgrade(config, revision)
    engine = create_engine(url)
    if revision == 'b37d1f4c9a20':
        with engine.begin() as db:
            db.execute(text("INSERT INTO users(id,email,name,password_hash,role,locale,created_at) VALUES('feedback-owner','feedback@example.com','Feedback owner','unchanged','customer','es','2026-10-03 12:00:00')"))
            db.execute(text("INSERT INTO chat_feedback(id,user_id,submission_id,metric,score,locale,form_duration_ms,conversation_duration_ms,created_at) VALUES('old-score','feedback-owner','00000000-0000-0000-0000-000000000001','nps',9,'es',1200,2000,'2026-10-03 12:00:00')"))
    command.upgrade(config, 'head')
    with engine.connect() as db:
        assert db.execute(text('SELECT version_num FROM alembic_version')).scalars().all() == ['fa6107d935b2']
        assert len(inspect(db).get_check_constraints('service_agreements')) == 3
        assert len(inspect(db).get_check_constraints('chat_feedback')) == 5
        if revision == 'b37d1f4c9a20':
            assert db.execute(text("SELECT score,form_duration_ms,conversation_duration_ms FROM chat_feedback WHERE id='old-score'")).one() == (9,1200,2000)
    engine.dispose()

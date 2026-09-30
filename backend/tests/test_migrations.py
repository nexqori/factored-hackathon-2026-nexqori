from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text, inspect


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
        assert db.execute(text("SELECT details,catalog_service_id,source_product_id,service_data FROM requests WHERE id='old-case'")).one()==('Original case details',None,None,None)
        rows=db.execute(text('SELECT m.id,m.user_id,m.content,c.user_id FROM messages m JOIN conversations c ON c.id=m.conversation_id')).all()
        assert len(rows)==2 and all(row[1]==row[3] and row[2]=='Original unchanged message' for row in rows)
        assert db.execute(text("SELECT email,identity_number,password_hash,text_size FROM users WHERE id='andrea'")).one()==('andrea@nexqori.com','00000001','unchanged-hash','medium')
        assert db.execute(text("SELECT email,identity_number FROM users WHERE id='custom'")).one()==('own@gmail.com',None)
    engine.dispose()

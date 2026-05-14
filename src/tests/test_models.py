from app.models import Usuario

def test_usuario_set_password():
    u = Usuario(email='test@tfg.es', username='testuser')
    u.set_password('MiPasswordSeguro123')
    
    assert u.password_hash is not None
    assert u.password_hash != 'MiPasswordSeguro123'
    assert u.check_password('MiPasswordSeguro123') is True
    assert u.check_password('clave_incorrecta') is False
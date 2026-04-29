import bcrypt
from flask_login import UserMixin

class Admin(UserMixin):
    def __init__(self, id):
        self.id = id

class Empleado(UserMixin):
    def __init__(self, id, nombre):
        self.id = id
        self.nombre = nombre

def hash_pin(pin):
    return bcrypt.hashpw(pin.encode(), bcrypt.gensalt()).decode()

def verificar_pin(pin, pin_hash):
    try:
        return bcrypt.checkpw(pin.encode(), pin_hash.encode())
    except:
        return False

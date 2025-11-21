class Config:
    SECRET_KEY = 'B!1weNAt1T^%kvhUI*S^'
    MAIL_SERVER = 'smtp.gmail.com'
    MAIL_PORT = 587
    MAIL_USE_TLS = True
    MAIL_USERNAME = 'carniceria.molino.la.poblanita@gmail.com'
    MAIL_PASSWORD = 'hrqelvfxvcdjvhkw'

class DesarrolloConfig():
    DEBUG = False

config = {
    'desarrollador': DesarrolloConfig
}
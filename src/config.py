class Config:
    SECRET_KEY = 'B!1weNAt1T^%kvhUI*S^'
    MAIL_SERVER = 'smtp.gmail.com'
    MAIL_PORT = 465
    MAIL_USE_SSL = True
    MAIL_USERNAME = 'carniceria.molino.la.poblanita@gmail.com'
    MAIL_PASSWORD = 'hrqelvfxvcdjvhkw'

class DesarrolloConfig():
    DEBUG = False

config = {
    'desarrollador': DesarrolloConfig
}
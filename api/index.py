from mangum import Mangum
from app.web.main import app

handler = Mangum(app)

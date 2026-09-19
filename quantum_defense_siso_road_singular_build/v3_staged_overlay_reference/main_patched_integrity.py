from main import app
from integrity_patch import register_integrity
register_integrity(app)

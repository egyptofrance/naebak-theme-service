from flask import Flask, request, jsonify
from flask_cors import CORS
import redis
import json
from datetime import datetime
import logging
from config import get_config

# إعداد التطبيق
app = Flask(__name__)
config = get_config()
app.config.from_object(config)

# إعداد CORS
CORS(app, origins=app.config["CORS_ALLOWED_ORIGINS"])

# إعداد Redis لتخزين إعدادات الثيمات
try:
    redis_client = redis.from_url(app.config["REDIS_URL"])
    redis_client.ping()
    print("Connected to Redis for theme service successfully!")
except redis.exceptions.ConnectionError as e:
    print(f"Could not connect to Redis for theme service: {e}")
    redis_client = None

# إعداد Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# نموذج لإعدادات ثيم مستخدم (كما هو موضح في LEADER.md)
class UserTheme:
    def __init__(self, user_id, theme_name, last_updated=None):
        self.user_id = str(user_id)
        self.theme_name = theme_name
        self.last_updated = last_updated if last_updated else datetime.utcnow().isoformat()

    def to_dict(self):
        return {
            "user_id": self.user_id,
            "theme_name": self.theme_name,
            "last_updated": self.last_updated
        }

@app.route("/health", methods=["GET"])
def health_check():
    """فحص صحة الخدمة"""
    redis_status = "disconnected"
    if redis_client:
        try:
            redis_client.ping()
            redis_status = "connected"
        except Exception as e:
            redis_status = f"error: {e}"

    return jsonify({"status": "ok", "service": "naebak-theme-service", "version": "1.0.0", "redis_status": redis_status}), 200

@app.route("/api/themes/user/<user_id>", methods=["GET"])
def get_user_theme(user_id):
    """الحصول على الثيم المفضل للمستخدم"""
    if not redis_client:
        return jsonify({"error": "Theme service temporarily unavailable"}), 503

    theme_data = redis_client.get(f"user_theme:{user_id}")
    if theme_data:
        theme = json.loads(theme_data)
        return jsonify(theme), 200
    else:
        # إذا لم يتم العثور على ثيم، ارجع الثيم الافتراضي
        return jsonify({"user_id": user_id, "theme_name": app.config["DEFAULT_THEME"], "last_updated": datetime.utcnow().isoformat()}), 200

@app.route("/api/themes/user/<user_id>", methods=["POST"])
def set_user_theme(user_id):
    """تعيين الثيم المفضل للمستخدم"""
    if not redis_client:
        return jsonify({"error": "Theme service temporarily unavailable"}), 503

    data = request.get_json()
    theme_name = data.get("theme_name")

    if not theme_name or theme_name not in app.config["AVAILABLE_THEMES"]:
        return jsonify({"error": "Invalid or missing theme_name"}), 400

    user_theme = UserTheme(user_id, theme_name)
    redis_client.set(f"user_theme:{user_id}", json.dumps(user_theme.to_dict()))
    logger.info(f"User {user_id} set theme to {theme_name}")
    return jsonify({"message": "Theme updated successfully", "theme": user_theme.to_dict()}), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=config.PORT, debug=config.DEBUG)

